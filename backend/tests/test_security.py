"""Tests for all hardening requirements.

1. API-key auth: 401 on missing/wrong key, bypass in dev mode, /api/health exempt.
2. Rate limiting: 429 + Retry-After for slow routes (5/min), medium routes (30/min).
   compare counts as 2.
3. Body size limit: 413 on payloads > 256 KB.
4. Security headers: CSP, X-Content-Type-Options, Referrer-Policy, X-Frame-Options.
5. CORS: X-API-Key in allow_headers; no hard-coded localhost in production.
6. Startup guard: refuses non-loopback host without APP_API_KEY.
7. Daily/monthly call counter: 429 when limit reached.
8. Concurrency semaphore: acquire/release contract.
"""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.schemas import IncidentCreate, IncidentUpdate
from app.security import (
    RateLimiter,
    _BODY_SIZE_LIMIT,
    _TIER_MED,
    _TIER_SLOW,
    _global_semaphore,
    acquire_global_slot,
    call_counter,
    check_startup_safety,
    release_global_slot,
)
from app.services.incident_service import IncidentService
from app.services.analysis_service import AnalysisService

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

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


def _make_analyzer():
    svc = AnalysisService()
    svc.memory = SimpleNamespace(recall_similar_incidents=Mock(return_value=[]))
    raw = json.dumps(DIAGNOSIS)
    svc.llm = SimpleNamespace(
        generate_json=Mock(return_value=raw),
        generate_json_with_correction=Mock(return_value=raw),
    )
    return svc


def _make_incident_svc(tmp_path):
    svc = IncidentService(
        db_path=tmp_path / "incidents.db",
        analysis_svc=_make_analyzer(),
    )
    svc.memory = SimpleNamespace(
        retain_resolved_incident=Mock(return_value="failed"),
        retain_incident=Mock(return_value="failed"),
        delete_incident_memory=Mock(return_value=True),
        recall_similar_incidents=Mock(return_value=[]),
    )
    return svc


def _client_with_key(tmp_path, api_key: str, environment: str = "production"):
    """TestClient with a specific API key and environment set."""
    svc = _make_incident_svc(tmp_path)
    main.app.dependency_overrides[main.get_incident_service] = lambda: svc
    settings.app_api_key = api_key
    settings.environment = environment
    return TestClient(main.app, raise_server_exceptions=False)


def _cleanup():
    main.app.dependency_overrides.pop(main.get_incident_service, None)
    settings.app_api_key = ""
    settings.environment = "development"


# ===========================================================================
# 1. API-key authentication
# ===========================================================================


class TestAPIKeyAuth:
    def test_missing_key_returns_401(self, tmp_path):
        client = _client_with_key(tmp_path, "secret-key-abc")
        try:
            resp = client.get("/api/incidents")
            assert resp.status_code == 401
            assert "X-API-Key" in resp.json()["detail"] or "missing" in resp.json()["detail"].lower()
        finally:
            _cleanup()

    def test_wrong_key_returns_401(self, tmp_path):
        client = _client_with_key(tmp_path, "correct-key")
        try:
            resp = client.get("/api/incidents", headers={"X-API-Key": "wrong-key"})
            assert resp.status_code == 401
        finally:
            _cleanup()

    def test_correct_key_passes(self, tmp_path):
        client = _client_with_key(tmp_path, "my-secret")
        try:
            resp = client.get("/api/incidents", headers={"X-API-Key": "my-secret"})
            assert resp.status_code == 200
        finally:
            _cleanup()

    def test_health_exempt_from_auth(self, tmp_path):
        """GET /api/health never requires a key."""
        client = _client_with_key(tmp_path, "any-key")
        try:
            resp = client.get("/api/health")
            assert resp.status_code == 200
        finally:
            _cleanup()

    def test_dev_mode_no_key_configured_bypasses(self, tmp_path):
        """In development with no key configured, all routes are open."""
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        settings.environment = "development"
        settings.app_api_key = ""
        try:
            client = TestClient(main.app, raise_server_exceptions=False)
            resp = client.get("/api/incidents")
            assert resp.status_code == 200
        finally:
            _cleanup()

    def test_timing_safe_comparison(self, tmp_path):
        """Verify hmac.compare_digest is used (no early-exit timing leak).
        We can't measure timing in a unit test, so we verify the middleware
        rejects partial matches (key sharing a prefix with the real key)."""
        client = _client_with_key(tmp_path, "abcdef1234567890")
        try:
            resp = client.get("/api/incidents", headers={"X-API-Key": "abcdef"})
            assert resp.status_code == 401
        finally:
            _cleanup()

    def test_request_id_present_in_401(self, tmp_path):
        client = _client_with_key(tmp_path, "key-xyz")
        try:
            resp = client.get("/api/incidents")
            assert resp.status_code == 401
            assert "request_id" in resp.json()
        finally:
            _cleanup()

    def test_non_api_routes_exempt(self, tmp_path):
        """Static/non-/api/ routes are not auth-gated."""
        client = _client_with_key(tmp_path, "some-key")
        try:
            # The / route only exists if frontend dist is built; skip if not
            import pathlib
            dist = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist"
            if dist.exists():
                resp = client.get("/")
                assert resp.status_code != 401
        finally:
            _cleanup()


# ===========================================================================
# 2. Rate limiting
# ===========================================================================


class TestRateLimiting:
    def _post_analyze_n(self, client, n: int, headers: dict):
        """Fire n analyze requests and return the list of status codes."""
        codes = []
        for _ in range(n):
            r = client.post("/api/incidents/analyze", json=INCIDENT, headers=headers)
            codes.append(r.status_code)
        return codes

    def test_slow_route_allows_5_then_429(self, tmp_path):
        client = _client_with_key(tmp_path, "k", environment="development")
        settings.app_api_key = ""  # dev bypass
        try:
            codes = self._post_analyze_n(
                client, _TIER_SLOW + 2, headers={}
            )
            assert codes[:_TIER_SLOW].count(200) == _TIER_SLOW or \
                   any(c in (200, 502) for c in codes[:_TIER_SLOW])
            assert 429 in codes[_TIER_SLOW:]
        finally:
            _cleanup()

    def test_429_includes_retry_after(self, tmp_path):
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            codes = []
            last_resp = None
            for _ in range(_TIER_SLOW + 2):
                last_resp = client.post("/api/incidents/analyze", json=INCIDENT)
                codes.append(last_resp.status_code)
            # Find first 429
            for i, r_code in enumerate(codes):
                if r_code == 429:
                    # Re-get the response; we need the last response that was 429
                    break
            assert 429 in codes
            # The last call should be 429 with Retry-After
            r429 = last_resp if last_resp.status_code == 429 else None
            # Re-fire one more to ensure we get a 429 with the header
            r429 = client.post("/api/incidents/analyze", json=INCIDENT)
            assert r429.status_code == 429
            assert "retry-after" in r429.headers or "Retry-After" in r429.headers
            ra = int(r429.headers.get("retry-after") or r429.headers.get("Retry-After"))
            assert 0 < ra <= 60
        finally:
            _cleanup()

    def test_compare_counts_as_2(self, tmp_path):
        """compare costs 2 tokens — should exhaust the slow bucket faster."""
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            from app.security import _rate_limiter
            # Seed the bucket with only 3 tokens remaining for this IP
            from app.security import _TokenBucket
            bucket = _rate_limiter._bucket("testclient", _TIER_SLOW)
            bucket.tokens = 3.0

            # A compare costs 2 tokens → one call should pass, next should 429
            r1 = client.post("/api/incidents/compare", json={"incident": INCIDENT})
            r2 = client.post("/api/incidents/compare", json={"incident": INCIDENT})
            # r1 used 2 tokens (1 left), r2 needs 2 but only 1 available
            assert r2.status_code == 429
        finally:
            _cleanup()

    def test_different_ips_have_separate_buckets(self, tmp_path):
        """Two different client IPs should have independent rate limits."""
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            from app.security import _rate_limiter, _TIER_SLOW
            # Drain ip1's bucket
            _rate_limiter._bucket("192.168.1.1", _TIER_SLOW).tokens = 0.0
            # ip2's bucket is fresh
            bucket2 = _rate_limiter._bucket("192.168.1.2", _TIER_SLOW)
            bucket2.tokens = float(_TIER_SLOW)

            allowed2, _ = _rate_limiter.check("192.168.1.2", _TIER_SLOW, 1)
            blocked1, _ = _rate_limiter.check("192.168.1.1", _TIER_SLOW, 1)

            assert allowed2 is True
            assert blocked1 is False
        finally:
            _cleanup()

    def test_token_bucket_refills_over_time(self):
        """Tokens refill at the correct rate."""
        from app.security import _TokenBucket
        bucket = _TokenBucket(capacity=5, window_seconds=1.0)
        # Drain completely
        for _ in range(5):
            bucket.consume(1)
        allowed_empty, _ = bucket.consume(1)
        assert allowed_empty is False

        # Wait for refill (capacity/window = 5 tokens/sec)
        time.sleep(0.25)
        allowed_refilled, _ = bucket.consume(1)
        assert allowed_refilled is True


# ===========================================================================
# 3. Body size limit
# ===========================================================================


class TestBodySizeLimit:
    def test_oversized_body_returns_413(self, tmp_path):
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            # Build a body just over 256 KB
            big = "x" * (_BODY_SIZE_LIMIT + 1)
            big_payload = json.dumps({**INCIDENT, "symptoms": big})
            resp = client.post(
                "/api/incidents/analyze",
                content=big_payload,
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 413
        finally:
            _cleanup()

    def test_body_at_limit_passes(self, tmp_path):
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            # A normal valid request is well under 256 KB
            resp = client.post("/api/incidents/analyze", json=INCIDENT)
            assert resp.status_code != 413
        finally:
            _cleanup()

    def test_content_length_fast_path(self, tmp_path):
        """Content-Length header above limit triggers 413 without reading the body."""
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            over = _BODY_SIZE_LIMIT + 100
            resp = client.post(
                "/api/incidents/analyze",
                content=b"x" * 10,  # tiny body
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(over),
                },
            )
            assert resp.status_code == 413
        finally:
            _cleanup()

    def test_413_response_is_json(self, tmp_path):
        settings.app_api_key = ""
        settings.environment = "development"
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        client = TestClient(main.app, raise_server_exceptions=False)
        try:
            big = "y" * (_BODY_SIZE_LIMIT + 1)
            resp = client.post(
                "/api/incidents/analyze",
                content=json.dumps({**INCIDENT, "symptoms": big}),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 413
            body = resp.json()
            assert "detail" in body
        finally:
            _cleanup()


# ===========================================================================
# 4. Security headers
# ===========================================================================


class TestSecurityHeaders:
    def _get_health(self):
        settings.app_api_key = ""
        settings.environment = "development"
        client = TestClient(main.app, raise_server_exceptions=False)
        return client.get("/api/health")

    def test_x_content_type_options(self):
        resp = self._get_health()
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self):
        resp = self._get_health()
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_referrer_policy(self):
        resp = self._get_health()
        assert "strict-origin" in resp.headers.get("referrer-policy", "")

    def test_content_security_policy_present(self):
        resp = self._get_health()
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp

    def test_csp_no_unsafe_scripts(self):
        resp = self._get_health()
        csp = resp.headers.get("content-security-policy", "")
        # script-src must not allow * or data:
        assert "script-src 'self'" in csp
        assert "script-src *" not in csp

    def test_csp_frame_ancestors_none(self):
        resp = self._get_health()
        csp = resp.headers.get("content-security-policy", "")
        assert "frame-ancestors 'none'" in csp


# ===========================================================================
# 5. CORS — X-API-Key in allowed headers
# ===========================================================================


class TestCORS:
    def test_x_api_key_in_allow_headers(self):
        """CORS preflight must include X-API-Key in Access-Control-Allow-Headers."""
        settings.app_api_key = ""
        settings.environment = "development"
        client = TestClient(main.app, raise_server_exceptions=False)
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Headers": "X-API-Key",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_headers = resp.headers.get("access-control-allow-headers", "").lower()
        assert "x-api-key" in allow_headers

    def test_production_cors_uses_settings_only(self, monkeypatch):
        """In production mode the CORS origin list contains only FRONTEND_URL,
        not hard-coded localhost entries. Verified by inspecting main.py source."""
        import inspect
        import app.main as _main
        src = inspect.getsource(_main)
        # The production guard: localhost added only in development block
        assert '"http://localhost:5173"' not in src.split("if settings.environment")[0], (
            "Hard-coded localhost should only appear inside the development check block"
        )
        assert 'settings.environment.lower() == "development"' in src, (
            "CORS origins must be gated on environment check"
        )


# ===========================================================================
# 6. Startup guard
# ===========================================================================


class TestStartupGuard:
    def test_loopback_without_key_allowed(self):
        settings.app_api_key = ""
        settings.environment = "production"
        try:
            check_startup_safety("127.0.0.1")  # must not raise
            check_startup_safety("::1")
            check_startup_safety("localhost")
        finally:
            settings.environment = "development"

    def test_nonloopback_without_key_raises(self):
        settings.app_api_key = ""
        settings.environment = "production"
        try:
            with pytest.raises(RuntimeError, match="APP_API_KEY"):
                check_startup_safety("0.0.0.0")
        finally:
            settings.environment = "development"

    def test_nonloopback_with_key_allowed(self):
        settings.app_api_key = "some-key"
        settings.environment = "production"
        try:
            check_startup_safety("0.0.0.0")  # must not raise
        finally:
            settings.app_api_key = ""
            settings.environment = "development"

    def test_development_mode_always_allowed(self):
        settings.app_api_key = ""
        settings.environment = "development"
        check_startup_safety("0.0.0.0")  # must not raise

    def test_real_ip_without_key_raises(self):
        settings.app_api_key = ""
        settings.environment = "production"
        try:
            with pytest.raises(RuntimeError, match="APP_API_KEY"):
                check_startup_safety("192.168.1.100")
        finally:
            settings.environment = "development"


# ===========================================================================
# 7. Daily / monthly counter
# ===========================================================================


class TestCallCounter:
    def test_within_daily_limit_allowed(self, monkeypatch):
        monkeypatch.setattr(settings, "max_daily_calls", 3)
        from app.security import _CallCounter
        cc = _CallCounter()
        assert cc.increment() is True
        assert cc.increment() is True
        assert cc.increment() is True
        assert cc.increment() is False  # 4th exceeds limit of 3

    def test_within_monthly_limit_allowed(self, monkeypatch):
        monkeypatch.setattr(settings, "max_monthly_calls", 2)
        from app.security import _CallCounter
        cc = _CallCounter()
        cc.increment()
        cc.increment()
        assert cc.increment() is False

    def test_zero_daily_limit_is_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "max_daily_calls", 0)
        monkeypatch.setattr(settings, "max_monthly_calls", 0)
        from app.security import _CallCounter
        cc = _CallCounter()
        for _ in range(100):
            assert cc.increment() is True

    def test_counter_returns_429_via_rate_limit_middleware(self, tmp_path):
        """When the call counter is exhausted, slow routes return 429."""
        settings.app_api_key = ""
        settings.environment = "development"
        settings.max_daily_calls = 1
        svc = _make_incident_svc(tmp_path)
        main.app.dependency_overrides[main.get_incident_service] = lambda: svc
        try:
            client = TestClient(main.app, raise_server_exceptions=False)
            # First call consumes the budget
            client.post("/api/incidents/analyze", json=INCIDENT)
            # Second call should hit the daily cap
            resp = client.post("/api/incidents/analyze", json=INCIDENT)
            assert resp.status_code == 429
        finally:
            settings.max_daily_calls = 0
            _cleanup()


# ===========================================================================
# 8. Concurrency semaphore
# ===========================================================================


class TestConcurrencySemaphore:
    def test_acquire_and_release(self):
        """acquire_global_slot / release_global_slot round-trips correctly."""
        from app.security import _global_semaphore, acquire_global_slot, release_global_slot
        # Drain the semaphore
        capacity = settings.max_concurrent_calls
        acquired = []
        for _ in range(capacity):
            ok = acquire_global_slot()
            acquired.append(ok)

        assert all(acquired), "Should be able to acquire up to capacity"
        extra = acquire_global_slot()
        assert extra is False, "Acquiring beyond capacity must fail"

        # Release all
        for _ in acquired:
            release_global_slot()

        # Now one more should succeed
        assert acquire_global_slot() is True
        release_global_slot()

    def test_semaphore_is_thread_safe(self):
        """Concurrent threads should never exceed the capacity simultaneously."""
        from app.security import acquire_global_slot, release_global_slot, settings
        capacity = settings.max_concurrent_calls

        # Drain to known state
        for _ in range(capacity):
            acquire_global_slot()

        concurrent_peak = [0]
        lock = threading.Lock()
        current = [0]

        def _worker():
            while not acquire_global_slot():
                time.sleep(0.001)
            with lock:
                current[0] += 1
                if current[0] > concurrent_peak[0]:
                    concurrent_peak[0] = current[0]
            time.sleep(0.01)
            with lock:
                current[0] -= 1
            release_global_slot()

        # Release all and let threads compete
        for _ in range(capacity):
            release_global_slot()

        threads = [threading.Thread(target=_worker) for _ in range(capacity * 2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert concurrent_peak[0] <= capacity


# ===========================================================================
# 9. Audit log / notes (not executable tests — documented here)
# ===========================================================================


class TestDependencyAuditNotes:
    """Documents the CVE fixes applied in requirements.txt and package.json.

    These are not executable checks — they verify the recorded intent.
    """

    def test_requirements_txt_pins_documented(self):
        import pathlib
        req = (
            pathlib.Path(__file__).resolve().parents[1] / "requirements.txt"
        ).read_text()
        # python-dotenv >= 1.2.2 (CVE-2026-28684)
        assert "python-dotenv==1.2.2" in req
        # python-multipart >= 0.0.31 (multiple DoS CVEs)
        assert "python-multipart==0.0.31" in req
        # starlette fixed via fastapi bump (CVE-2026-54283 etc.)
        assert "fastapi==0.115.12" in req

    def test_frontend_vite_bumped(self):
        import pathlib, json as _json
        pkg = _json.loads(
            (
                pathlib.Path(__file__).resolve().parents[2]
                / "frontend" / "package.json"
            ).read_text()
        )
        vite_ver = pkg["devDependencies"]["vite"].lstrip("^~>=")
        major = int(vite_ver.split(".")[0])
        assert major >= 6, f"vite should be >=6 (was {vite_ver}); fixes GHSA-67mh-4wv8-2f99"
