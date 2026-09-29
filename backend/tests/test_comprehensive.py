"""Comprehensive backend tests — Phase-finish coverage.

Covers:
  - HTTP status code mapping (404, 409, 422, 400, 500, 502)
  - Concurrency conflicts (optimistic locking)
  - Status transition table
  - Idempotency (client_request_id)
  - Guardrail flags (deny-list)
  - Redaction (PII stripped before retain)
  - Retain result shapes (sync accepted, async pending, failed)
  - Auth (X-API-Key middleware)
  - Rate limits (per-IP token bucket)

All provider calls are mocked.  Tests marked @pytest.mark.live are skipped
by default and must be run explicitly with `pytest -m live`.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.schemas import (
    IncidentCreate,
    IncidentStatus,
    IncidentUpdate,
    NotFoundError,
    ConflictError,
    ResolutionRequest,
    TERMINAL_STATUSES,
)
from app.services.analysis_service import AnalysisService
from app.services.incident_service import IncidentService
from app.services.memory_service import (
    MEMORY_STATUS_ACCEPTED,
    MEMORY_STATUS_FAILED,
    MEMORY_STATUS_NOT_RECORDED,
    MEMORY_STATUS_PENDING,
    MemoryService,
    build_incident_memory_document,
)
from app.guardrails import check_actions
from app.redaction import redact

# ── pytest markers ────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "live: requires real API keys; skipped by default")


# ── shared helpers ────────────────────────────────────────────────────────

INCIDENT = dict(
    title="TLS certificate expired on payment gateway",
    service="gateway",
    environment="production",
    severity="P2",
    symptoms="Partner requests fail certificate verification; internal OK.",
)

DIAGNOSIS = dict(
    summary="Certificate failure needs verification.",
    likely_root_cause="Expired partner certificate.",
    evidence_assessment="Reported error supports an unconfirmed hypothesis.",
    severity_assessment="P2",
    severity_reasoning="P2 — major partner functionality impaired.",
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
    root_cause="Certificate expiry confirmed by openssl output.",
    resolution="Partner renewed certificate and deployment verified.",
    actions_taken=["Verified the renewed certificate with openssl."],
    outcome="successfully_resolved",
)


def _make_analyzer():
    svc = AnalysisService()
    raw = json.dumps(DIAGNOSIS)
    svc.llm = SimpleNamespace(
        generate_json=Mock(return_value=raw),
        generate_json_with_correction=Mock(return_value=raw),
    )
    svc.memory = SimpleNamespace(recall_similar_incidents=Mock(return_value=[]))
    return svc


def _make_svc(tmp_path, analysis_svc=None):
    svc = IncidentService(
        db_path=tmp_path / "incidents.db",
        analysis_svc=analysis_svc or _make_analyzer(),
    )
    svc.memory = SimpleNamespace(
        retain_resolved_incident=Mock(return_value=MEMORY_STATUS_FAILED),
        retain_incident=Mock(return_value=MEMORY_STATUS_FAILED),
        delete_incident_memory=Mock(return_value=True),
        recall_similar_incidents=Mock(return_value=[]),
    )
    return svc


def _api_client(tmp_path, api_key="", env="development"):
    svc = _make_svc(tmp_path)
    main.app.dependency_overrides[main.get_incident_service] = lambda: svc
    settings.app_api_key = api_key
    settings.environment = env
    return TestClient(main.app, raise_server_exceptions=False), svc


def _cleanup():
    main.app.dependency_overrides.pop(main.get_incident_service, None)
    settings.app_api_key = ""
    settings.environment = "development"


# ═══════════════════════════════════════════════════════════════════════════
# 1. HTTP status code mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestStatusCodeMapping:
    """Every domain exception maps to the documented HTTP status code."""

    def test_404_missing_incident(self, tmp_path):
        client, _ = _api_client(tmp_path)
        try:
            r = client.get("/api/incidents/INC-GHOST")
            assert r.status_code == 404
            assert "request_id" in r.json()
        finally:
            _cleanup()

    def test_404_delete_missing_incident(self, tmp_path):
        client, _ = _api_client(tmp_path)
        try:
            r = client.delete("/api/incidents/INC-GHOST")
            assert r.status_code == 404
        finally:
            _cleanup()

    def test_409_concurrent_write(self, tmp_path):
        _, svc = _api_client(tmp_path)
        # Create an incident, then simulate a stale-version save
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        inc, ver = svc._require_with_version(item.incident_id)
        svc._save(inc, ver)  # bumps version to ver+1
        try:
            with pytest.raises(ConflictError):
                svc._save(inc, ver)  # stale → raises
        finally:
            _cleanup()

    def test_422_missing_required_field(self, tmp_path):
        client, _ = _api_client(tmp_path)
        try:
            r = client.post("/api/incidents/analyze", json={"title": "hi"})
            assert r.status_code == 422
        finally:
            _cleanup()

    def test_422_title_too_short(self, tmp_path):
        client, _ = _api_client(tmp_path)
        try:
            r = client.post("/api/incidents/analyze", json={**INCIDENT, "title": "ab"})
            assert r.status_code == 422
        finally:
            _cleanup()

    def test_400_analyze_on_resolved_incident(self, tmp_path):
        client, svc = _api_client(tmp_path)
        svc.memory.retain_resolved_incident.return_value = MEMORY_STATUS_ACCEPTED
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
        try:
            r = client.post(f"/api/incidents/{item.incident_id}/analyze")
            assert r.status_code == 400
            assert "Cannot analyze" in r.json()["detail"]
        finally:
            _cleanup()

    def test_400_update_without_reopen(self, tmp_path):
        client, svc = _api_client(tmp_path)
        svc.memory.retain_resolved_incident.return_value = MEMORY_STATUS_ACCEPTED
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
        try:
            r = client.post(
                f"/api/incidents/{item.incident_id}/updates",
                json={"note": "New evidence arrived from monitoring.", "kind": "evidence"},
            )
            assert r.status_code == 400
            assert "reopen" in r.json()["detail"]
        finally:
            _cleanup()

    def test_500_stored_data_validation_error(self, tmp_path):
        client, svc = _api_client(tmp_path)

        def _exploding_list(limit=200, offset=0):
            from app.schemas import Incident
            Incident.model_validate({"bad": "data"})

        svc.list_incidents = _exploding_list
        try:
            r = client.get("/api/incidents")
            assert r.status_code == 500
            assert "integrity" in r.json()["detail"].lower()
        finally:
            _cleanup()

    def test_502_provider_runtime_error(self, tmp_path):
        _, svc = _api_client(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        svc.analyze_incident = Mock(side_effect=RuntimeError("LLM failed"))
        try:
            r = TestClient(main.app, raise_server_exceptions=False).post(
                f"/api/incidents/{item.incident_id}/analyze"
            )
            assert r.status_code == 502
        finally:
            _cleanup()

    def test_response_contains_request_id_on_all_errors(self, tmp_path):
        client, _ = _api_client(tmp_path)
        try:
            for path in [
                "/api/incidents/GHOST",
                "/api/incidents/GHOST/analyze",
            ]:
                r = client.get(path) if "analyze" not in path else client.post(path)
                assert "request_id" in r.json(), f"Missing request_id for {path}"
        finally:
            _cleanup()


# ═══════════════════════════════════════════════════════════════════════════
# 2. Concurrency conflicts
# ═══════════════════════════════════════════════════════════════════════════


class TestConcurrencyConflicts:
    def test_stale_version_raises_conflict(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        inc, ver = svc._require_with_version(item.incident_id)
        svc._save(inc, ver)  # bump version
        with pytest.raises(ConflictError):
            svc._save(inc, ver)  # stale

    def test_correct_version_succeeds(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        inc, ver = svc._require_with_version(item.incident_id)
        inc.title = "Updated title here for the test"
        svc._save(inc, ver)  # correct version — no exception
        reloaded = svc.get_incident(item.incident_id)
        assert reloaded.title == "Updated title here for the test"

    def test_conflict_409_via_api(self, tmp_path):
        _, svc = _api_client(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT))

        def _bad_create(data):
            raise ConflictError("Concurrent write detected")

        svc.create_incident = _bad_create
        try:
            r = TestClient(main.app, raise_server_exceptions=False).post(
                "/api/incidents/analyze", json=INCIDENT
            )
            assert r.status_code == 409
        finally:
            _cleanup()


# ═══════════════════════════════════════════════════════════════════════════
# 3. Status transition table
# ═══════════════════════════════════════════════════════════════════════════


class TestStatusTransitions:
    @pytest.mark.parametrize("outcome,expected_status", [
        ("successfully_resolved", IncidentStatus.RESOLVED),
        ("partially_resolved", IncidentStatus.MITIGATED),
        ("unresolved_escalated", IncidentStatus.ESCALATED),
    ])
    def test_resolve_maps_outcome_to_status(self, tmp_path, outcome, expected_status):
        svc = _make_svc(tmp_path)
        svc.memory.retain_resolved_incident.return_value = MEMORY_STATUS_ACCEPTED
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        result = svc.resolve_incident(
            item.incident_id, ResolutionRequest(**{**RESOLUTION, "outcome": outcome})
        )
        assert result.status == expected_status

    def test_only_reported_and_investigating_can_be_analyzed(self, tmp_path):
        svc = _make_svc(tmp_path, analysis_svc=_make_analyzer())
        svc.memory.retain_resolved_incident.return_value = MEMORY_STATUS_ACCEPTED
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        # Resolve it → terminal status
        svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
        with pytest.raises(ValueError, match="Cannot analyze"):
            svc.analyze_incident(item.incident_id)

    def test_analyze_transitions_reported_to_investigating(self, tmp_path):
        svc = _make_svc(tmp_path, analysis_svc=_make_analyzer())
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        assert item.status == IncidentStatus.REPORTED
        svc.analyze_incident(item.incident_id)
        updated = svc.get_incident(item.incident_id)
        assert updated.status == IncidentStatus.INVESTIGATING

    def test_reopen_clears_resolution_fields(self, tmp_path):
        svc = _make_svc(tmp_path)
        svc.memory.retain_resolved_incident.return_value = MEMORY_STATUS_ACCEPTED
        svc.memory.retain_incident.return_value = MEMORY_STATUS_ACCEPTED
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
        # Reopen
        result = svc.add_update(
            item.incident_id,
            IncidentUpdate(
                note="New evidence arrived from monitoring system.", kind="evidence", reopen=True
            ),
        )
        assert result.status == IncidentStatus.INVESTIGATING
        assert result.outcome is None
        assert result.resolution is None
        assert result.resolved_at is None

    def test_terminal_statuses_block_update_without_reopen(self, tmp_path):
        svc = _make_svc(tmp_path)
        svc.memory.retain_resolved_incident.return_value = MEMORY_STATUS_ACCEPTED
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        svc.resolve_incident(item.incident_id, ResolutionRequest(**RESOLUTION))
        with pytest.raises(ValueError, match="reopen"):
            svc.add_update(
                item.incident_id,
                IncidentUpdate(note="New evidence from monitoring.", kind="evidence"),
            )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Idempotency
# ═══════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    def test_same_cri_returns_same_incident(self, tmp_path):
        svc = _make_svc(tmp_path)
        a = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id="cri-abc"))
        b = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id="cri-abc"))
        assert a.incident_id == b.incident_id

    def test_different_cri_creates_different_incidents(self, tmp_path):
        svc = _make_svc(tmp_path)
        a = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id="cri-1"))
        b = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id="cri-2"))
        assert a.incident_id != b.incident_id

    def test_no_cri_always_creates_new(self, tmp_path):
        svc = _make_svc(tmp_path)
        a = svc.create_incident(IncidentCreate(**INCIDENT))
        b = svc.create_incident(IncidentCreate(**INCIDENT))
        assert a.incident_id != b.incident_id

    def test_cri_stored_on_incident(self, tmp_path):
        svc = _make_svc(tmp_path)
        item = svc.create_incident(IncidentCreate(**INCIDENT, client_request_id="cri-store"))
        reloaded = svc.get_incident(item.incident_id)
        assert reloaded.client_request_id == "cri-store"

    def test_cri_max_length_422(self, tmp_path):
        client, _ = _api_client(tmp_path)
        try:
            r = client.post("/api/incidents/analyze", json={**INCIDENT, "client_request_id": "x" * 129})
            assert r.status_code == 422
        finally:
            _cleanup()

    def test_analyze_retry_same_cri_returns_same_incident_id(self, tmp_path):
        _, svc = _api_client(tmp_path)
        try:
            c = TestClient(main.app, raise_server_exceptions=False)
            cri = "retry-cri-99"
            r1 = c.post("/api/incidents/analyze", json={**INCIDENT, "client_request_id": cri})
            r2 = c.post("/api/incidents/analyze", json={**INCIDENT, "client_request_id": cri})
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r1.json()["incident_id"] == r2.json()["incident_id"]
        finally:
            _cleanup()


# ═══════════════════════════════════════════════════════════════════════════
# 5. Guardrail flags
# ═══════════════════════════════════════════════════════════════════════════


class TestGuardrailFlags:
    @pytest.mark.parametrize("text,expected_flag", [
        ("Run rm -rf /var/cache to clear space", True),
        ("kubectl delete pod payment-api", True),
        ("Execute FLUSHALL on Redis cluster", True),
        ("Disable TLS verification for testing", True),
        ("DROP TABLE sessions", True),
        ("Use MONITOR on production Redis", True),
        ("Check certificate expiry with openssl", False),
        ("Increase connection pool from 50 to 100", False),
        ("Review logs for error patterns", False),
    ])
    def test_deny_list_pattern_match(self, text, expected_flag):
        warnings = check_actions([text])
        if expected_flag:
            assert warnings, f"Expected flag for: {text!r}"
        else:
            assert not warnings, f"Unexpected flag for: {text!r}"

    def test_multiple_clean_actions_no_flags(self):
        actions = [
            "Check Redis pool metrics during timeout window.",
            "Verify network packet loss between app and Redis.",
            "Increase pool size with rollback plan if Redis shows headroom.",
        ]
        assert check_actions(actions) == []

    def test_single_flagged_action_in_mixed_list(self):
        actions = [
            "Check certificate expiry dates.",
            "kubectl delete deployment old-service",
            "Verify new deployment is healthy.",
        ]
        flags = check_actions(actions)
        assert len(flags) == 1
        assert "kubectl" in flags[0].lower()

    def test_flagged_actions_appear_in_analysis_response(self, tmp_path):
        from app.services.analysis_service import AnalysisService
        flagged_diag = {**DIAGNOSIS, "recommended_actions": ["Run rm -rf /tmp/cache"]}
        svc = AnalysisService()
        raw = json.dumps(flagged_diag)
        svc.llm = SimpleNamespace(
            generate_json=Mock(return_value=raw),
            generate_json_with_correction=Mock(return_value=raw),
        )
        svc.memory = SimpleNamespace(recall_similar_incidents=Mock(return_value=[]))
        result = svc.analyze_incident({"incident_id": "TEST", **INCIDENT})
        assert result.flagged_actions
        assert any("rm" in fa.lower() for fa in result.flagged_actions)
        assert any("Flagged action" in w for w in result.warnings)

    def test_flagged_text_preserved_not_removed(self, tmp_path):
        from app.services.analysis_service import AnalysisService
        flagged_text = "kubectl delete pod payment-api-xyz"
        flagged_diag = {**DIAGNOSIS, "recommended_actions": [flagged_text]}
        svc = AnalysisService()
        raw = json.dumps(flagged_diag)
        svc.llm = SimpleNamespace(
            generate_json=Mock(return_value=raw),
            generate_json_with_correction=Mock(return_value=raw),
        )
        svc.memory = SimpleNamespace(recall_similar_incidents=Mock(return_value=[]))
        result = svc.analyze_incident({"incident_id": "TEST", **INCIDENT})
        assert flagged_text in result.recommended_actions


# ═══════════════════════════════════════════════════════════════════════════
# 6. Redaction
# ═══════════════════════════════════════════════════════════════════════════


class TestRedaction:
    @pytest.mark.parametrize("text,pattern,placeholder", [
        ("Contact user@example.com for access.", "user@example.com", "[REDACTED-EMAIL]"),
        ("Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.abc.xyz", "eyJhbGciOiJSUzI1NiJ9", "[REDACTED-TOKEN]"),
        ("Key: AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE", "[REDACTED-AWS-KEY-ID]"),
    ])
    def test_pii_redacted(self, text, pattern, placeholder):
        result, n = redact(text)
        assert pattern not in result
        assert placeholder in result
        assert n >= 1

    def test_clean_text_unchanged(self):
        text = "Connection pool exhausted; latency spike at 18:00."
        result, n = redact(text)
        assert result == text
        assert n == 0

    def test_redaction_applied_before_retain(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "memory_redaction", True)
        from app.hindsight_client import HindsightClient
        wrapper = HindsightClient()
        fake_sdk = type("SDK", (), {
            "retain": Mock(return_value=SimpleNamespace(
                success=True, var_async=False, operation_id=None, operation_ids=None
            ))
        })()
        wrapper._client = fake_sdk

        from app.services.memory_service import MemoryService
        svc = MemoryService(hindsight=wrapper)
        incident_with_email = {
            "incident_id": "INC-REDACT",
            "title": "Test",
            "service": "svc",
            "environment": "production",
            "severity": "P2",
            "status": "resolved",
            "timestamp": "2024-01-01T00:00:00Z",
            "symptoms": "Contact admin@secret.io for access.",
            "root_cause": "DB connection pool exhausted.",
            "actions_taken": ["Increased pool size."],
            "resolution": "Pool size increased.",
            "outcome": "successfully_resolved",
            "updates": [],
        }
        svc.retain_incident(incident_with_email)
        content = fake_sdk.retain.call_args[1]["content"]
        assert "admin@secret.io" not in content
        assert "[REDACTED-EMAIL]" in content

    def test_redaction_skipped_when_disabled(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "memory_redaction", False)
        from app.hindsight_client import HindsightClient
        wrapper = HindsightClient()
        fake_sdk = type("SDK", (), {
            "retain": Mock(return_value=SimpleNamespace(
                success=True, var_async=False, operation_id=None, operation_ids=None
            ))
        })()
        wrapper._client = fake_sdk

        from app.services.memory_service import MemoryService
        svc = MemoryService(hindsight=wrapper)
        incident = {
            "incident_id": "INC-NOREDACT",
            "title": "Test",
            "service": "svc",
            "environment": "production",
            "severity": "P2",
            "status": "resolved",
            "timestamp": "2024-01-01T00:00:00Z",
            "symptoms": "Contact admin@secret.io for access.",
            "root_cause": "Pool exhausted.",
            "actions_taken": ["Fixed it."],
            "resolution": "Fixed.",
            "outcome": "successfully_resolved",
            "updates": [],
        }
        svc.retain_incident(incident)
        content = fake_sdk.retain.call_args[1]["content"]
        assert "admin@secret.io" in content


# ═══════════════════════════════════════════════════════════════════════════
# 7. Retain result shapes (sync / async / failed)
# ═══════════════════════════════════════════════════════════════════════════


class TestRetainResultShapes:
    def _fake_client(self, success=True, var_async=False, op_id=None):
        from app.hindsight_client import HindsightClient
        from types import SimpleNamespace as NS
        wrapper = HindsightClient()
        fake_sdk = type("SDK", (), {
            "retain": Mock(return_value=NS(
                success=success, var_async=var_async,
                operation_id=op_id, operation_ids=None,
            ))
        })()
        wrapper._client = fake_sdk
        return wrapper, fake_sdk

    def test_sync_accepted_returns_accepted_status(self):
        wrapper, _ = self._fake_client(success=True, var_async=False)
        result = wrapper.retain("content", document_id="doc1")
        assert result == {"accepted": True, "async": False, "operation_id": None}

    def test_async_accepted_returns_pending_status(self):
        wrapper, _ = self._fake_client(success=True, var_async=True, op_id="op-xyz")
        result = wrapper.retain("content", document_id="doc1")
        assert result == {"accepted": True, "async": True, "operation_id": "op-xyz"}

    def test_failed_returns_not_accepted(self):
        wrapper, _ = self._fake_client(success=False, var_async=False)
        result = wrapper.retain("content", document_id="doc1")
        assert result["accepted"] is False

    def test_memory_retained_true_for_pending(self, tmp_path):
        """memory_retained=True when retain returns pending (queued)."""
        svc = IncidentService(db_path=tmp_path / "db.sqlite3")
        svc.memory = SimpleNamespace(
            retain_incident=Mock(return_value=MEMORY_STATUS_PENDING),
            delete_incident_memory=Mock(return_value=True),
        )
        from app.services.incident_service import _utcnow
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        inc, ver = svc._require_with_version(item.incident_id)
        inc.updates.append({"note": "evidence", "kind": "evidence", "timestamp": _utcnow()})
        svc._save(inc, ver)
        result = svc.retry_memory(item.incident_id)
        assert result.memory_retained is True  # pending counts as retained

    def test_memory_retained_false_for_failed(self, tmp_path):
        svc = IncidentService(db_path=tmp_path / "db.sqlite3")
        svc.memory = SimpleNamespace(
            retain_incident=Mock(return_value=MEMORY_STATUS_FAILED),
            delete_incident_memory=Mock(return_value=False),
        )
        from app.services.incident_service import _utcnow
        item = svc.create_incident(IncidentCreate(**INCIDENT))
        inc, ver = svc._require_with_version(item.incident_id)
        inc.updates.append({"note": "evidence", "kind": "evidence", "timestamp": _utcnow()})
        svc._save(inc, ver)
        result = svc.retry_memory(item.incident_id)
        assert result.memory_retained is False

    def test_not_recorded_for_non_production(self, monkeypatch):
        monkeypatch.setattr(settings, "retain_non_production", False)
        from app.hindsight_client import HindsightClient
        wrapper = HindsightClient()
        wrapper._client = Mock()
        from app.services.memory_service import MemoryService
        svc = MemoryService(hindsight=wrapper)
        staging_incident = {
            "incident_id": "INC-STG", "title": "Test", "service": "svc",
            "environment": "staging", "severity": "P3", "status": "resolved",
            "timestamp": "2024-01-01T00:00:00Z",
            "symptoms": "Test", "root_cause": "Test", "actions_taken": ["Test."],
            "resolution": "Fixed.", "outcome": "successfully_resolved", "updates": [],
        }
        status = svc.retain_incident(staging_incident)
        assert status == MEMORY_STATUS_NOT_RECORDED
        wrapper._client.retain.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# 8. Auth — X-API-Key middleware
# ═══════════════════════════════════════════════════════════════════════════


class TestAuth:
    def test_missing_key_returns_401(self, tmp_path):
        client, _ = _api_client(tmp_path, api_key="secret", env="production")
        try:
            r = client.get("/api/incidents")
            assert r.status_code == 401
        finally:
            _cleanup()

    def test_wrong_key_returns_401(self, tmp_path):
        client, _ = _api_client(tmp_path, api_key="correct", env="production")
        try:
            r = client.get("/api/incidents", headers={"X-API-Key": "wrong"})
            assert r.status_code == 401
        finally:
            _cleanup()

    def test_correct_key_passes(self, tmp_path):
        client, _ = _api_client(tmp_path, api_key="my-key", env="production")
        try:
            r = client.get("/api/incidents", headers={"X-API-Key": "my-key"})
            assert r.status_code == 200
        finally:
            _cleanup()

    def test_health_always_exempt(self, tmp_path):
        client, _ = _api_client(tmp_path, api_key="some-key", env="production")
        try:
            r = client.get("/api/health")
            assert r.status_code == 200
        finally:
            _cleanup()

    def test_dev_mode_no_key_bypasses(self, tmp_path):
        client, _ = _api_client(tmp_path, api_key="", env="development")
        try:
            r = client.get("/api/incidents")
            assert r.status_code == 200
        finally:
            _cleanup()

    def test_401_contains_request_id(self, tmp_path):
        client, _ = _api_client(tmp_path, api_key="key", env="production")
        try:
            r = client.get("/api/incidents")
            assert r.status_code == 401
            assert "request_id" in r.json()
        finally:
            _cleanup()


# ═══════════════════════════════════════════════════════════════════════════
# 9. Rate limits
# ═══════════════════════════════════════════════════════════════════════════


class TestRateLimits:
    def test_slow_route_429_after_exhaustion(self, tmp_path):
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            from app.security import _rate_limiter, _TIER_SLOW
            # Force bucket to 1 token so next call passes but one after that fails
            bucket = _rate_limiter._bucket("testclient", _TIER_SLOW)
            bucket.tokens = 1.0
            r1 = client.post("/api/incidents/analyze", json=INCIDENT)
            r2 = client.post("/api/incidents/analyze", json=INCIDENT)
            assert r1.status_code != 429
            assert r2.status_code == 429
        finally:
            _cleanup()

    def test_429_has_retry_after_header(self, tmp_path):
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            from app.security import _rate_limiter, _TIER_SLOW
            bucket = _rate_limiter._bucket("testclient", _TIER_SLOW)
            bucket.tokens = 0.0
            r = client.post("/api/incidents/analyze", json=INCIDENT)
            assert r.status_code == 429
            assert "retry-after" in {k.lower() for k in r.headers}
            ra = int(r.headers.get("retry-after", 0))
            assert ra > 0
        finally:
            _cleanup()

    def test_get_routes_not_rate_limited_aggressively(self, tmp_path):
        """GET /incidents should allow many more requests than slow POST routes."""
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            from app.security import _rate_limiter, _TIER_FAST
            # GET routes use TIER_FAST (120/min); drain to 10 remaining
            bucket = _rate_limiter._bucket("testclient", _TIER_FAST)
            bucket.tokens = 10.0
            # 10 GET requests should all succeed
            for _ in range(10):
                r = client.get("/api/incidents")
                assert r.status_code == 200
        finally:
            _cleanup()

    def test_body_size_limit_413(self, tmp_path):
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            from app.security import _BODY_SIZE_LIMIT
            big = json.dumps({**INCIDENT, "symptoms": "s" * (_BODY_SIZE_LIMIT + 1)})
            r = client.post(
                "/api/incidents/analyze",
                content=big,
                headers={"Content-Type": "application/json"},
            )
            assert r.status_code == 413
        finally:
            _cleanup()


# ═══════════════════════════════════════════════════════════════════════════
# 10. Live / manual tests (skipped by default)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.live
@pytest.mark.skip(reason="Requires real API keys. Run with: pytest -m live")
class TestLive:
    """Integration tests that make real calls to Groq and Hindsight.
    Run manually: pytest -m live --no-header -rN
    """

    def test_groq_health_check(self):
        from app.llm import llm_client
        assert llm_client.health_check()

    def test_hindsight_health_check(self):
        from app.hindsight_client import hindsight_client
        assert hindsight_client.health_check()

    def test_full_analyze_round_trip(self):
        """Create an incident and analyze it end-to-end with live providers."""
        import tempfile, pathlib
        from app.services.incident_service import IncidentService
        with tempfile.TemporaryDirectory() as d:
            svc = IncidentService(db_path=pathlib.Path(d) / "test.db")
            item = svc.create_incident(IncidentCreate(**INCIDENT))
            analysis = svc.analyze_incident(item.incident_id)
            assert analysis.likely_root_cause
            assert analysis.incident_id == item.incident_id
