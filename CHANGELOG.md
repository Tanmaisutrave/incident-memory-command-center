# Changelog

All notable changes to Recall — Incident Memory Command Center.

Version numbers come from a single constant: `backend/app/schemas.py → APP_VERSION`.

---

## [3.1.0] — Phase 7: Hardening, frontend polish, docs

### Added
- **API-key authentication** (`X-API-Key`, `hmac.compare_digest`). Bypassed in
  `ENVIRONMENT=development` with no key configured. Startup refuses to bind
  a non-loopback host without `APP_API_KEY`.
- **Rate limiting** — in-memory token bucket per client IP: 5/min for
  analyze/compare/reflect (compare costs 2), 30/min for other POSTs,
  120/min for GETs. Returns 429 with `Retry-After`.
- **Global concurrency semaphore** (`MAX_CONCURRENT_CALLS`, default 4) around
  LLM and Hindsight calls. Daily/monthly call counters
  (`MAX_DAILY_CALLS`, `MAX_MONTHLY_CALLS`).
- **Security headers middleware**: `Content-Security-Policy` (self-only),
  `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options DENY`.
- **Body size limit** (256 KB) via raw ASGI middleware.
- **CORS** now comes from `settings.frontend_url` only; no hard-coded localhost
  in production. `X-API-Key` added to `allow_headers`.
- **`scripts/setup.ps1`** rewritten: `Read-Host -AsSecureString`, string-literal
  line replacement (no regex), optional `APP_API_KEY` generation.
- **`scripts/setup.sh`** — bash equivalent of `setup.ps1`.
- **`scripts/run.sh`** — bash equivalent of `run.ps1`.
- **`Makefile`** with `setup / dev / test / build / lint / audit / docker-*` targets.
- **`Dockerfile`** — multi-stage (Node build → Python runtime), non-root user,
  `HEALTHCHECK` on `/api/health`.
- **`docker-compose.yml`** with named volume for SQLite.
- **GitHub Actions** (`ci.yml`): backend pytest + ruff + pip-audit; frontend
  Vitest + build + npm audit.
- **`pytest.ini`** registers the `live` marker; live tests skip by default.
- **Comprehensive test suite** (`test_comprehensive.py`): 61 tests covering
  HTTP status codes, concurrency conflicts, transition table, idempotency,
  guardrail flags, redaction, retain shapes, auth, rate limits.
- **Frontend Vitest setup** with `@testing-library/react`; 29 tests covering
  `api.js` error handling (401/429/413/non-JSON/timeout) and `Outcome`
  `actions_taken` parsing.
- **`docs/API_GUIDE.md`** — complete API reference generated from OpenAPI schema.
- **README** — accurate quickstart, architecture diagram, full configuration
  table, data-retention and privacy notes, known limitations.

### Changed
- `seed_incidents.py` requires `--confirm`; prints target bank ID before writing.
- `requirements.txt` bumps: `fastapi 0.115.12` (starlette ≥1.3.1 fixes 8+ CVEs),
  `python-dotenv 1.2.2` (CVE-2026-28684), `python-multipart 0.0.31` (5+ DoS CVEs),
  `groq 1.7.0`, `uvicorn 0.34.3`, `pydantic 2.11.7`.
- Frontend `vite` bumped from 5.x to 8.3.1 (fixes GHSA-67mh-4wv8-2f99).

---

## [3.0.0] — Phase 6: Memory pipeline hardening

### Added
- **Single serialiser** `build_incident_memory_document(incident)` for all
  retain paths; never stores raw JSON dump; labels unresolved content explicitly.
- **Explicit retain result** `{'accepted', 'async', 'operation_id'}`; memory
  status lifecycle: `not_recorded | pending | accepted | failed`.
- **Contamination control**: environment tags on every retain (`env:`, `svc:`,
  `status:`, `outcome:`); SDK-native tag filtering on recall; staging/dev
  incidents blocked unless `RETAIN_NON_PRODUCTION=true`.
- **`delete_incident_memory(incident_id)`** — wired into `DELETE /incidents/{id}`;
  `DeleteResponse` gains `memory_deleted` and `memory_note`.
- **Stable source IDs**: SDK's real UUID used; sha1[:12] fallback (never `M{i}`).
- **Shared Hindsight SDK client** — one instance, explicit `close()` in lifespan.
- **`MEMORY_REDACTION=true`** — regex pass over content before retain/LLM;
  covers emails, Bearer tokens, AWS key IDs, PEM blocks.
- `app/redaction.py` with `redact()` and `redact_dict_values()`.
- New settings: `recall_same_env_only`, `retain_non_production`, `memory_redaction`.
- 60-test `test_memory_pipeline.py` suite.

### Changed
- `retry_memory` guarded: exceptions become `memory_status=failed`, never raised.
- `delete_incident` returns `{'deleted', 'memory_deleted', 'memory_note'}`.

---

## [2.5.0] — Phase 5: Analysis pipeline hardening

### Added
- **`build_llm_payload()`** — 24 k char budget; drops oldest updates first,
  truncates logs; `warnings` entry on trim.
- **`build_memory_query()`** — bounded slices: symptoms 1 500 chars, logs 300,
  last 3 updates × 300 chars.
- **Recall failure logging** via `logger.exception` (no incident text);
  exception class appended to `warnings`.
- **LLM retry** on `finish_reason=length` (1.5× tokens) and on
  validation/unknown-citation (one correction attempt with error appended).
- **Schema sanitisation** — strips `minLength/maxLength/minItems/maxItems`
  before sending to Groq; Pydantic still enforces locally.
- **`severity_assessment`** now model-authored (added to `Diagnosis`);
  `severity_reasoning` field added.
- **Post-generation guardrail** (`app/guardrails.py`) deny-list over
  `recommended_actions` + `investigation_steps`; matched actions collected in
  `flagged_actions`.
- **Comparison fairness** — `temperature=0` and fixed `seed` for both branches;
  `differences` summary returned.
- **Prompt-injection guard** — memories wrapped as `{source_id, text, type}` only.
- `app/guardrails.py`, 61-test `test_analysis_pipeline.py`.
- `Diagnosis` gains `severity_assessment: Severity` and `severity_reasoning`.
- `AnalysisResponse` gains `severity_reasoning`, `flagged_actions`.
- `ComparisonResponse` gains `differences`.

### Changed
- SYSTEM prompt max-actions limit aligned with schema `max_length=3`.
- `compare_analysis` delegates to `analysis_service.compare_analysis`.

---

## [2.0.0] — Phase 4: API hardening

### Added
- **`NotFoundError`** → 404, **`ConflictError`** → 409,
  **`ProviderError`** → 502, raw `RuntimeError` → 502 (generic).
- **`RequestIDMiddleware`** — `X-Request-ID` on every request/response.
- **Logging** — level from `LOG_LEVEL`; `logger.exception` in all error paths;
  symptom text never logged at INFO.
- **Validation** — `str_strip_whitespace=True`; non-empty checks; field limits:
  symptoms 12 k, logs 20 k, tags 20×50, suspected_causes 10×300, metrics 8 KB,
  actions 20×1000, resolution fields 5 k, recall/reflect query 3 k.
- **`client_request_id`** idempotency on `POST /incidents/analyze`.
- **`response_model`** on every route.
- **`HealthResponse.version`** from `APP_VERSION` constant.
- **`/api/connections`** per-provider TTL cache (60 s ok, 10 s err);
  6 s timeout in threads; no lock held during I/O.
- **50-update cap** per incident.
- 71-test `test_api_contracts.py` suite.

---

## [1.5.0] — Phase 3: Durable storage

### Added
- **SQLite persistence** — WAL mode, 10 s busy-timeout, `PRAGMA foreign_keys`.
- **Optimistic concurrency** — `version` integer column; `_save()` raises
  `ConflictError` on stale write.
- **Slow-call isolation** — `analyze/resolve/add_update/retry_memory` re-read
  after the slow provider call.
- **Legacy seed import** — guarded by `meta` table flag.
- `IncidentService`, `AnalysisService`, `MemoryService`.
- Regression test suite (`test_regressions.py`).

---

## [1.0.0] — Phase 2: Memory integration

### Added
- Hindsight recall wired into `AnalysisService`.
- Hindsight retain on incident resolution.
- `retry-memory` endpoint.
- `memory_retained` field on `Incident`.
- Sample walkthrough in the UI.

---

## [0.5.0] — Phase 1: MVP

### Added
- FastAPI backend with `POST /incidents/analyze`.
- React frontend — incident form, analysis view, evidence panel.
- Groq LLM integration (`generate_json` with strict schema).
- `Diagnosis` Pydantic model with citation integrity checks.
- Basic error handling.

---

## [0.1.0] — Phase 0: Scaffold

### Added
- Project skeleton: FastAPI + React + Vite.
- `.env.example`, `run.ps1`, README.
- Initial `requirements.txt` and `package.json`.
