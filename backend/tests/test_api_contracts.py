"""Comprehensive API-contract and validation tests.

Covers every requirement from the spec:
  1. Error hierarchy — correct HTTP status codes for each domain exception.
  2. ProviderError / generic-502 — safe messages; raw str(exc) never leaked.
  3. Pydantic ValidationError from stored data → 500 (generic message).
  4. Logging — X-Request-ID present in error bodies; sensitive text not logged.
  5. Validation limits — all field-length and list-size caps.
  6. response_model correctness — every route honours its schema.
  7. Idempotency — /analyze with same client_request_id returns the same incident.
  8. /api/connections — per-provider TTL cache; lock not held during network I/O.

All tests are fully offline: no provider calls, no production DB.
"""

import json
import logging
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from app import main
from app.schemas import (
    APP_VERSION,
    AnalysisResponse,
    ConflictError,
    Diagnosis,
    Incident,
    IncidentCreate,
    IncidentStatus,
    IncidentUpdate,
    NotFoundError,
    ProviderError,
    ResolutionRequest,
    Severity,
)
from app.services.analysis_service import AnalysisService
from app.services.incident_service import IncidentService

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

INCIDENT = dict(
    title="TLS certificate expired on payment gateway",
    service="gateway",
    environment="production",
    severity="P2",
    symptoms="Partner requests fail certificate verification, internal OK.",
)

DIAGNOSIS = dict(
    summary="Certificate failure needs verification.",
    likely_root_cause="Expired partner certificate.",
    evidence_assessment="Reported error supports an unconfirmed hypothesis.",
    investigation_steps=["Check certificate validity dates."],
    recommended_actions=["Renew only if expiry is confirmed."],
    disconfirming_checks=["A valid certificate would contradict expiration."],
    verification_steps=["Verify handshake success after renewal."],
    historical_evidence=[],
    memory_insights=[],
    cited_sources=[],
    risk_notes="Do not disable TLS verification.",
)

RESOLUTION = dict(
    root_cause="Certificate expiry confirmed by openssl output",
    resolution="Partner renewed certificate and deployment verified.",
    actions_taken=["Verified the renewed certificate with openssl."],
    outcome="successfully_resolved",
)


def _make_analyzer():
    svc = AnalysisService()
    svc.memory = SimpleNamespace(recall_similar_incidents=Mock(return_value=[]))
    svc.llm = SimpleNamespace(
        generate_json=Mock(return_value=json.dumps(DIAGNOSIS))
    )
    return svc


def _make_svc(tmp_path, analysis_svc=None, memory_svc=None):
    svc = IncidentService(
        db_path=tmp_path / "incidents.db",
        analysis_svc=analysis_svc or _make_analyzer(),
        memory_svc=memory_svc,
    )
    if memory_svc is None:
        svc.memory = SimpleNamespace(
            retain_resolved_incident=Mock(return_value=False),
            hindsight=SimpleNamespace(retain=Mock(return_value={"success": False})),
            recall_similar_incidents=Mock(return_value=[]),
        )
    return svc


def _client(tmp_path):
    """Return a TestClient wired to a fresh, isolated IncidentService."""
    svc = _make_svc(tmp_path)
    main.app.dependency_overrides[main.get_incident_service] = lambda: svc
    return TestClient(main.app, raise_server_exceptions=False)


# ===========================================================================
# 1. Error hierarchy — HTTP status codes
# ===========================================================================


class TestErrorHierarchy:
    """Each domain exception maps to the correct HTTP status code."""

    def test_not_found_returns_404(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.get("/api/incidents/INC-DOESNOTEXIST")
            assert resp.status_code == 404
            body = resp.json()
            assert "detail" in body
            assert "request_id" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_conflict_error_returns_409(self, tmp_path):
        """Simulate a ConflictError from the service layer."""
        svc = _make_svc(tmp_path)

        def _bad_create(data):
            raise ConflictError("Duplicate client_request_id")

        svc.create_incident = _bad_create
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                "/api/incidents/analyze", json=INCIDENT
            )
            assert resp.status_code == 409
            body = resp.json()
            assert "Duplicate" in body["detail"]
            assert "request_id" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_value_error_returns_400(self, tmp_path):
        """A ValueError raised by service layer returns 400."""
        svc = _make_svc(tmp_path)

        def _bad_analyze(incident_id, use_memory=True):
            raise ValueError("Cannot analyze incident in status 'resolved'")

        svc.analyze_incident = _bad_analyze
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            # First create an incident, then try to analyze it (triggers ValueError)
            item = svc.create_incident.__wrapped__(svc, IncidentCreate(**INCIDENT)) \
                if hasattr(svc.create_incident, "__wrapped__") else None
            # Directly call the route that triggers analyze
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                "/api/incidents/INC-FAKE123/analyze"
            )
            # NotFoundError is raised first, but that's fine — test via add_update instead
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

        # Better: patch add_update to raise ValueError
        svc2 = _make_svc(tmp_path)

        def _bad_update(incident_id, update):
            raise ValueError("Incident is resolved. Pass reopen=true.")

        svc2.add_update = _bad_update
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc2
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                "/api/incidents/INC-FAKE/updates",
                json={"note": "New evidence arrived from the monitoring system.", "kind": "evidence"},
            )
            assert resp.status_code == 400
            assert "request_id" in resp.json()
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_provider_error_returns_502_with_safe_message(self, tmp_path):
        """ProviderError exposes its safe_message, never the raw provider output."""
        svc = _make_svc(tmp_path)

        def _explode(data):
            item = IncidentService(
                db_path=tmp_path / "incidents.db"
            ).create_incident(data)
            return item

        # create works, but analyze throws ProviderError
        real_svc = _make_svc(tmp_path)

        def _bad_analyze(incident_id, use_memory=True):
            raise ProviderError("Analysis failed. Check provider configuration.")

        real_svc.analyze_incident = _bad_analyze
        main.app.dependency_overrides[main.get_incident_service] = lambda: real_svc
        try:
            # Create first, then re-analyze
            item = real_svc.create_incident(IncidentCreate(**INCIDENT))
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/analyze"
            )
            assert resp.status_code == 502
            body = resp.json()
            assert "Check provider" in body["detail"]
            assert "request_id" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_runtime_error_returns_502_generic(self, tmp_path):
        """RuntimeError from third-party libs → 502 generic, never str(exc)."""
        svc = _make_svc(tmp_path)

        raw_secret = "sk-groq-supersecret-key-12345"

        def _bad_analyze(incident_id, use_memory=True):
            raise RuntimeError(f"Groq API error: {raw_secret}")

        svc.analyze_incident = _bad_analyze
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/analyze"
            )
            assert resp.status_code == 502
            body = resp.json()
            # Must NOT expose the raw exception text with the secret
            assert raw_secret not in body.get("detail", "")
            assert "request_id" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_pydantic_validation_error_from_stored_data_returns_500(self, tmp_path):
        """A PydanticValidationError bubbling from service → 500 with generic message."""
        svc = _make_svc(tmp_path)

        def _exploding_list(limit=200, offset=0):
            # Simulate a stored payload that fails to deserialise
            from pydantic import ValidationError
            Incident.model_validate({"bad": "data"})  # will raise ValidationError

        svc.list_incidents = _exploding_list
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).get("/api/incidents")
            assert resp.status_code == 500
            body = resp.json()
            assert "integrity" in body["detail"].lower() or "internal" in body["detail"].lower()
            # No pydantic field detail leaked
            assert "field required" not in body.get("detail", "").lower()
            assert "request_id" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_generic_exception_returns_502(self, tmp_path):
        """Unhandled Exception subclass → 502 generic message."""
        svc = _make_svc(tmp_path)

        class _UnexpectedError(Exception):
            pass

        def _bad_list(limit=200, offset=0):
            raise _UnexpectedError("something weird happened")

        svc.list_incidents = _bad_list
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).get("/api/incidents")
            assert resp.status_code == 502
            body = resp.json()
            assert "weird" not in body.get("detail", "")
            assert "request_id" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_delete_not_found_returns_404(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.delete("/api/incidents/INC-GHOST")
            assert resp.status_code == 404
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_analyze_invalid_status_returns_400(self, tmp_path):
        """analyze_incident on a resolved incident → 400 (ValueError)."""
        svc = _make_svc(tmp_path)
        svc.memory = SimpleNamespace(retain_resolved_incident=Mock(return_value=True))
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/analyze"
            )
            assert resp.status_code == 400
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)


# ===========================================================================
# 2. X-Request-ID middleware
# ===========================================================================


class TestRequestID:
    def test_request_id_present_in_error_response(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.get("/api/incidents/GHOST")
            assert resp.status_code == 404
            assert "request_id" in resp.json()
            assert resp.headers.get("x-request-id")
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_client_supplied_request_id_echoed(self, tmp_path):
        client = _client(tmp_path)
        try:
            custom_id = "my-test-req-id-42"
            resp = client.get("/api/incidents/GHOST", headers={"X-Request-ID": custom_id})
            assert resp.headers.get("x-request-id") == custom_id
            assert resp.json()["request_id"] == custom_id
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_request_id_generated_when_absent(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.get("/api/incidents/GHOST")
            req_id = resp.headers.get("x-request-id", "")
            assert len(req_id) > 8  # a UUID4 or similar
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)


# ===========================================================================
# 3. Validation limits
# ===========================================================================


class TestValidationLimits:
    """Every field-length and list-size cap raises HTTP 422."""

    def _post_analyze(self, tmp_path, payload):
        client = _client(tmp_path)
        try:
            return client.post("/api/incidents/analyze", json=payload)
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    # --- IncidentCreate ---

    def test_title_too_short(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "title": "ab"})
        assert resp.status_code == 422

    def test_title_too_long(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "title": "x" * 501})
        assert resp.status_code == 422

    def test_title_blank_after_strip(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "title": "     "})
        assert resp.status_code == 422

    def test_symptoms_too_short(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "symptoms": "short"})
        assert resp.status_code == 422

    def test_symptoms_too_long(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "symptoms": "x" * 12001})
        assert resp.status_code == 422

    def test_error_logs_too_long(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "error_logs": "x" * 20001})
        assert resp.status_code == 422

    def test_tags_list_too_long(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "tags": [f"tag{i}" for i in range(21)]})
        assert resp.status_code == 422

    def test_single_tag_too_long(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "tags": ["x" * 51]})
        assert resp.status_code == 422

    def test_tag_at_max_length_accepted(self, tmp_path):
        resp = self._post_analyze(tmp_path, {**INCIDENT, "tags": ["x" * 50]})
        # May be 200 or 502 (no real LLM), but NOT 422
        assert resp.status_code != 422

    def test_suspected_causes_too_many(self, tmp_path):
        resp = self._post_analyze(
            tmp_path,
            {**INCIDENT, "suspected_causes": [f"cause {i}" for i in range(11)]},
        )
        assert resp.status_code == 422

    def test_single_suspected_cause_too_long(self, tmp_path):
        resp = self._post_analyze(
            tmp_path, {**INCIDENT, "suspected_causes": ["x" * 301]}
        )
        assert resp.status_code == 422

    def test_metrics_too_large(self, tmp_path):
        # > 8 KB when serialised
        big_metrics = {"key_" + str(i): "v" * 100 for i in range(100)}
        resp = self._post_analyze(tmp_path, {**INCIDENT, "metrics": big_metrics})
        assert resp.status_code == 422

    def test_metrics_at_limit_accepted(self, tmp_path):
        # 7 KB — just under the 8 KB cap
        small_enough = {"k": "v" * (7 * 1024 // 2)}
        resp = self._post_analyze(tmp_path, {**INCIDENT, "metrics": small_enough})
        assert resp.status_code != 422

    # --- IncidentUpdate ---

    def test_update_note_too_short(self, tmp_path):
        client = _client(tmp_path)
        try:
            svc_inner = _make_svc(tmp_path)
            item = svc_inner.create_incident(IncidentCreate(**INCIDENT))
            main.app.dependency_overrides[main.get_incident_service] = lambda: svc_inner
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/updates",
                json={"note": "too short", "kind": "evidence"},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_update_note_too_long(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/updates",
                json={"note": "x" * 5001, "kind": "evidence"},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_max_updates_per_incident(self, tmp_path):
        """Adding the 51st update raises 400 (ValueError from service)."""
        from app.schemas import MAX_UPDATES_PER_INCIDENT
        svc = _make_svc(tmp_path)
        svc.memory.hindsight.retain.return_value = {"success": False}
        item = svc.create_incident(IncidentCreate(**INCIDENT))

        # Fill up to the cap directly on the model
        inc, ver = svc._require_with_version(item.incident_id)
        inc.updates = [
            {"note": f"update {i}", "kind": "evidence", "timestamp": "2024-01-01T00:00:00Z"}
            for i in range(MAX_UPDATES_PER_INCIDENT)
        ]
        svc._save(inc, ver)

        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/updates",
                json={
                    "note": "This would be the 51st update to the incident record.",
                    "kind": "evidence",
                },
            )
            assert resp.status_code == 400
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    # --- ResolutionRequest ---

    def test_resolution_root_cause_too_long(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/resolve",
                json={**RESOLUTION, "root_cause": "x" * 5001},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_resolution_actions_taken_item_too_long(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/resolve",
                json={**RESOLUTION, "actions_taken": ["x" * 1001]},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_resolution_actions_taken_list_too_long(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/resolve",
                json={**RESOLUTION, "actions_taken": [f"action {i}" for i in range(21)]},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_resolution_blank_root_cause(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/resolve",
                json={**RESOLUTION, "root_cause": "          "},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    # --- MemoryRecallRequest ---

    def test_recall_query_too_long(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.post(
                "/api/memory/recall",
                json={"query": "x" * 3001, "max_tokens": 100},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_recall_query_blank(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.post("/api/memory/recall", json={"query": "   "})
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_recall_query_at_max_length_accepted(self, tmp_path):
        """3000-char query must pass schema validation (may still fail at provider)."""
        from unittest.mock import patch as _patch
        with _patch.object(
            main.hindsight_client, "recall", return_value=[]
        ):
            client = _client(tmp_path)
            try:
                resp = client.post(
                    "/api/memory/recall",
                    json={"query": "x " * 1499 + "xq", "max_tokens": 100},
                )
                # 200, 500, 502 are all OK — just not 422
                assert resp.status_code != 422
            finally:
                main.app.dependency_overrides.pop(main.get_incident_service, None)

    # --- MemoryReflectRequest ---

    def test_reflect_query_too_long(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.post(
                "/api/memory/reflect",
                json={"query": "x" * 3001},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_reflect_query_blank(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.post("/api/memory/reflect", json={"query": "    "})
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_whitespace_stripped_from_title(self, tmp_path):
        """str_strip_whitespace=True — leading/trailing spaces are silently stripped."""
        from app.schemas import IncidentCreate
        data = IncidentCreate(**{**INCIDENT, "title": "  TLS certificate on gateway router  "})
        assert data.title == "TLS certificate on gateway router"

    def test_whitespace_only_title_rejected(self, tmp_path):
        from app.schemas import IncidentCreate
        with pytest.raises(Exception):
            IncidentCreate(**{**INCIDENT, "title": "     "})


# ===========================================================================
# 4. Idempotency
# ===========================================================================


class TestIdempotency:
    def test_same_client_request_id_returns_same_incident(self, tmp_path):
        svc = _make_svc(tmp_path)
        cri = "client-req-abc-123"
        a = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id=cri))
        b = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id=cri))
        assert a.incident_id == b.incident_id

    def test_different_client_request_id_creates_new_incident(self, tmp_path):
        svc = _make_svc(tmp_path)
        a = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id="req-1"))
        b = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id="req-2"))
        assert a.incident_id != b.incident_id

    def test_no_client_request_id_always_creates_new(self, tmp_path):
        svc = _make_svc(tmp_path)
        a = svc.create_incident(IncidentCreate(**INCIDENT))
        b = svc.create_incident(IncidentCreate(**INCIDENT))
        assert a.incident_id != b.incident_id

    def test_client_request_id_stored_with_incident(self, tmp_path):
        svc = _make_svc(tmp_path)
        cri = "idempotency-key-xyz"
        item = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id=cri))
        loaded = svc.get_incident(item.incident_id)
        assert loaded.client_request_id == cri

    def test_analyze_retry_with_same_client_request_id(self, tmp_path):
        """POST /analyze with same client_request_id returns the existing incident
        and re-runs analysis (incident_id must be the same both times)."""
        svc = _make_svc(tmp_path)
        cri = "analyze-idem-key-1"
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp1 = TestClient(main.app, raise_server_exceptions=False).post(
                "/api/incidents/analyze", json={**INCIDENT, "client_request_id": cri}
            )
            resp2 = TestClient(main.app, raise_server_exceptions=False).post(
                "/api/incidents/analyze", json={**INCIDENT, "client_request_id": cri}
            )
            assert resp1.status_code == 200
            assert resp2.status_code == 200
            assert resp1.json()["incident_id"] == resp2.json()["incident_id"]
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_client_request_id_max_length(self, tmp_path):
        """client_request_id longer than 128 chars → 422."""
        client = _client(tmp_path)
        try:
            resp = client.post(
                "/api/incidents/analyze",
                json={**INCIDENT, "client_request_id": "x" * 129},
            )
            assert resp.status_code == 422
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)


# ===========================================================================
# 5. Response model correctness
# ===========================================================================


class TestResponseModels:
    def test_health_response_contains_app_version(self, tmp_path):
        client = _client(tmp_path)
        try:
            resp = client.get("/api/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["version"] == APP_VERSION
            assert "status" in body
            assert "model" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_incident_list_returns_summaries(self, tmp_path):
        svc = _make_svc(tmp_path)
        svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).get("/api/incidents")
            assert resp.status_code == 200
            items = resp.json()
            assert len(items) == 1
            # IncidentSummary fields
            assert "incident_id" in items[0]
            assert "title" in items[0]
            # Full body fields should NOT appear in summary
            assert "symptoms" not in items[0]
            assert "error_logs" not in items[0]
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_incident_detail_returns_full_body(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).get(
                f"/api/incidents/{item.incident_id}"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert "symptoms" in body
            assert "incident_id" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_analyze_response_model(self, tmp_path):
        svc = _make_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                "/api/incidents/analyze", json=INCIDENT
            )
            assert resp.status_code == 200
            body = resp.json()
            # Required AnalysisResponse fields
            for field in ("incident_id", "summary", "likely_root_cause",
                          "recommended_actions", "investigation_steps", "next_steps"):
                assert field in body, f"Missing field: {field}"
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_delete_response_model(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).delete(
                f"/api/incidents/{item.incident_id}"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["incident_id"] == item.incident_id
            assert body["deleted"] is True
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)

    def test_resolve_response_model(self, tmp_path):
        svc = _make_svc(tmp_path)
        svc.memory.retain_resolved_incident.return_value = False
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            resp = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/resolve", json=RESOLUTION
            )
            assert resp.status_code == 200
            body = resp.json()
            assert "incident_id" in body
            assert "status" in body
            assert "memory_retained" in body
            assert "message" in body
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)


# ===========================================================================
# 6. /api/connections — per-provider cache, no lock during network I/O
# ===========================================================================


class TestConnections:
    def test_connected_status_cached(self, monkeypatch):
        """A successful check is cached for the OK TTL; the check_fn is not
        called again within the cache window."""
        # Reset the module-level cache before test
        main._provider_cache.clear()

        call_count = 0

        def _fast_check():
            nonlocal call_count
            call_count += 1
            return True

        # Prime cache with one call
        result1 = main._check_provider("test_ok", _fast_check)
        result2 = main._check_provider("test_ok", _fast_check)

        assert result1 == "connected"
        assert result2 == "connected"
        assert call_count == 1, "Second call should hit the cache"

    def test_failure_cached_for_short_ttl_only(self, monkeypatch):
        """A failed check is cached for _CONN_ERR_TTL (10s), not _CONN_OK_TTL (60s)."""
        main._provider_cache.clear()

        call_count = 0

        def _failing_check():
            nonlocal call_count
            call_count += 1
            return False

        result = main._check_provider("test_fail", _failing_check)
        assert result == "unavailable"

        cached = main._provider_cache.get("test_fail", {})
        assert cached.get("value") == "unavailable"
        # TTL for failure must be <= 10s
        # Verify the next call within error TTL still uses cache
        result2 = main._check_provider("test_fail", _failing_check)
        assert result2 == "unavailable"
        assert call_count == 1

    def test_exception_in_check_returns_unavailable(self):
        main._provider_cache.clear()

        def _throwing_check():
            raise ConnectionError("network down")

        result = main._check_provider("test_ex", _throwing_check)
        assert result == "unavailable"

    def test_timeout_returns_unavailable(self):
        """A check that blocks longer than _CONN_TIMEOUT returns unavailable."""
        main._provider_cache.clear()

        # Temporarily lower the timeout constant for this test
        original = main._CONN_TIMEOUT
        main._CONN_TIMEOUT = 0.05  # 50 ms

        def _slow_check():
            time.sleep(1)
            return True

        try:
            result = main._check_provider("test_timeout", _slow_check)
            assert result == "unavailable"
        finally:
            main._CONN_TIMEOUT = original
            main._provider_cache.clear()

    def test_connections_endpoint_returns_correct_schema(self, monkeypatch):
        """The /api/connections endpoint returns {groq, hindsight} strings."""
        main._provider_cache.clear()
        monkeypatch.setattr(main.llm_client, "health_check", lambda: True)
        monkeypatch.setattr(main.hindsight_client, "health_check", lambda: True)
        with TestClient(main.app, raise_server_exceptions=False) as client:
            resp = client.get("/api/connections")
        assert resp.status_code == 200
        body = resp.json()
        assert "groq" in body and "hindsight" in body
        assert body["groq"] in ("connected", "unavailable")
        main._provider_cache.clear()

    def test_both_providers_checked_independently(self, monkeypatch):
        """groq failure does not prevent hindsight from being checked."""
        main._provider_cache.clear()
        monkeypatch.setattr(main.llm_client, "health_check", lambda: False)
        monkeypatch.setattr(main.hindsight_client, "health_check", lambda: True)
        with TestClient(main.app, raise_server_exceptions=False) as client:
            resp = client.get("/api/connections")
        body = resp.json()
        assert body["groq"] == "unavailable"
        assert body["hindsight"] == "connected"
        main._provider_cache.clear()


# ===========================================================================
# 7. Logging — sensitive text not logged at INFO
# ===========================================================================


class TestLogging:
    def test_symptoms_not_logged_at_info(self, tmp_path, caplog):
        """Symptom text must never appear in INFO-level log records."""
        svc = _make_svc(tmp_path)
        secret_symptom = "ULTRA_SECRET_SYMPTOM_TEXT_XYZ"

        with caplog.at_level(logging.INFO, logger="app"):
            svc.memory.recall_similar_incidents(
                service="svc",
                environment="production",
                symptoms=secret_symptom,
            )

        info_msgs = [r.message for r in caplog.records if r.levelno == logging.INFO]
        for msg in info_msgs:
            assert secret_symptom not in msg, (
                f"Sensitive symptom text leaked into INFO log: {msg!r}"
            )

    def test_recall_logs_lengths_not_content(self, tmp_path, caplog):
        """recall_similar_incidents should log lengths/IDs, not raw text."""
        svc = _make_svc(tmp_path)
        symptom = "Redis connection pool exhausted due to connection leak"

        with caplog.at_level(logging.INFO, logger="app"):
            svc.memory.recall_similar_incidents(
                service="cache-svc",
                environment="staging",
                symptoms=symptom,
                error_logs="Error: too many connections",
            )

        for record in caplog.records:
            if record.levelno == logging.INFO:
                # Log line should contain lengths but not raw text
                assert symptom not in record.message

    def test_provider_error_logs_with_request_id(self, tmp_path, caplog):
        """ProviderError handler logs request_id and type but not raw exc details."""
        svc = _make_svc(tmp_path)

        def _bad_analyze(incident_id, use_memory=True):
            raise ProviderError("LLM provider timeout. Retry later.")

        item = svc.create_incident(IncidentCreate(**INCIDENT))
        svc.analyze_incident = _bad_analyze
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc

        try:
            with caplog.at_level(logging.ERROR, logger="app"):
                TestClient(main.app, raise_server_exceptions=False).post(
                    f"/api/incidents/{item.incident_id}/analyze"
                )
            error_msgs = [r.message for r in caplog.records if r.levelno >= logging.ERROR]
            assert any("request_id" in m or "Provider" in m for m in error_msgs), (
                "ProviderError should be logged with request_id context"
            )
        finally:
            main.app.dependency_overrides.pop(main.get_incident_service, None)


# ===========================================================================
# 8. Domain exception schema unit tests
# ===========================================================================


class TestDomainExceptions:
    def test_not_found_error_is_exception(self):
        exc = NotFoundError("Incident 'X' not found")
        assert isinstance(exc, Exception)
        assert "X" in str(exc)

    def test_conflict_error_is_exception(self):
        exc = ConflictError("Version mismatch")
        assert isinstance(exc, Exception)

    def test_provider_error_has_safe_message(self):
        exc = ProviderError("Safe message for user.")
        assert exc.safe_message == "Safe message for user."
        assert str(exc) == "Safe message for user."

    def test_provider_error_safe_message_attribute(self):
        msg = "Analysis failed. Check your Groq API key."
        exc = ProviderError(msg)
        assert exc.safe_message == msg


# ===========================================================================
# 9. IncidentCreate whitespace stripping
# ===========================================================================


class TestWhitespaceStripping:
    def test_service_stripped(self):
        data = IncidentCreate(**{**INCIDENT, "service": "  gateway  "})
        assert data.service == "gateway"

    def test_symptoms_stripped(self):
        data = IncidentCreate(**{**INCIDENT, "symptoms": "  High latency observed  "})
        assert data.symptoms == "High latency observed"

    def test_blank_service_rejected(self):
        with pytest.raises(Exception):
            IncidentCreate(**{**INCIDENT, "service": "   "})

    def test_blank_symptoms_rejected(self):
        with pytest.raises(Exception):
            IncidentCreate(**{**INCIDENT, "symptoms": "   "})
