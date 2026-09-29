# Recall — Incident Memory Command Center

**Version 3.1.0** · FastAPI · React · Groq · Hindsight

Turn your team's resolved incidents into a searchable, retrievable operational
memory. When a new incident arrives, recall similar past events, reason with
the model, and retain the outcome for the next engineer.

---

## Quick start (local)

### Prerequisites

- Python 3.11+
- Node.js 20+

### 1. Clone and configure

```bash
git clone https://github.com/your-org/incident-memory-command-center
cd incident-memory-command-center
bash scripts/setup.sh        # Linux/macOS
# — or —
.\scripts\setup.ps1          # Windows PowerShell
```

`setup.sh / setup.ps1` copies `.env.example` to `backend/.env` and prompts for
your Groq and Hindsight API keys (input is hidden).

### 2. Create the virtual environment and install deps

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

### 3. Build the frontend

```bash
cd frontend
npm ci --legacy-peer-deps
node build.mjs
cd ..
```

### 4. Start

```bash
bash scripts/run.sh           # Linux/macOS
.\run.ps1                     # Windows PowerShell
```

Open <http://127.0.0.1:8000>.  
Use `bash scripts/run.sh --rebuild` (or `.\run.ps1 -Rebuild`) after frontend changes.

### Docker (alternative)

```bash
cp backend/.env.example backend/.env   # fill in API keys
docker-compose up -d
```

The SQLite database is persisted in a named volume (`incident_data`).

### make / just

```bash
make setup    # create venv and install all deps
make dev      # run backend with --reload
make test     # pytest + vitest
make build    # frontend build
make lint     # ruff
make audit    # pip-audit + npm audit
```

---

## Architecture

```
┌─────────────┐  HTTP   ┌──────────────────────────────────────────────┐
│  Browser    │────────▶│              FastAPI (uvicorn)                │
│  React SPA  │◀────────│                                              │
└─────────────┘         │  Middleware stack (outermost → innermost):   │
                        │   RequestID → Security headers →              │
                        │   Body size limit (256 KB) →                  │
                        │   Rate limiter (token bucket, per-IP) →       │
                        │   API-key auth (X-API-Key, hmac) →            │
                        │   CORS                                        │
                        │                                              │
                        │  Routes                                      │
                        │   /api/incidents  ──▶ IncidentService        │
                        │   /api/memory     ──▶ MemoryService          │
                        │                                              │
                        │  Services                                    │
                        │   IncidentService  SQLite (WAL, optimistic   │
                        │                   concurrency v=int)         │
                        │   AnalysisService  → LLMClient               │
                        │   MemoryService    → HindsightClient         │
                        │                                              │
                        │  Safety layers                               │
                        │   Guardrails   deny-list post-generation     │
                        │   Redaction    PII strip before retain/LLM   │
                        └──────────────────────────────────────────────┘
                                   │                    │
                            ┌──────▼──────┐    ┌───────▼───────┐
                            │  Groq API   │    │  Hindsight API │
                            │  (LLM)      │    │  (memory bank) │
                            └─────────────┘    └───────────────┘
```

Data flow for a new incident:

1. `POST /api/incidents/analyze` → `IncidentService.create_incident` → SQLite
2. `AnalysisService.analyze_incident`:
   - `MemoryService.recall_similar_incidents` → Hindsight (optional)
   - `build_llm_payload` (24 k char budget, bounded slices)
   - Optional redaction pass (email, tokens, AWS keys, PEM blocks)
   - `LLMClient.generate_json` → Groq (schema-validated, with retry)
   - `Guardrails.check_actions` → deny-list post-generation
3. Analysis stored back to SQLite
4. On resolution: `MemoryService.retain_resolved_incident` → Hindsight

---

## Configuration

All settings are read from `backend/.env` (or environment variables).
`pydantic-settings` merges `.env` → environment variables → defaults.

### Required for live AI

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | `""` | Your Groq API key. Get one at <https://console.groq.com>. |
| `HINDSIGHT_API_KEY` | `""` | Your Hindsight API key. Get one at <https://hindsight.vectorize.io>. |
| `HINDSIGHT_BANK_ID` | `incident-agent` | The memory bank to read from and write to. |
| `HINDSIGHT_BASE_URL` | `https://api.hindsight.vectorize.io` | Override for self-hosted Hindsight. |

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development \| staging \| production`. Affects CORS and auth bypass. |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Any chat-completion model available on your Groq account. |
| `GROQ_MAX_TOKENS` | `4000` | Maximum tokens per LLM response. |
| `GROQ_REASONING_EFFORT` | `false` | Set `true` to pass `reasoning_effort=low` on r1-family models. |
| `FRONTEND_URL` | `http://localhost:5173` | Origin allowed by CORS. Set to your deployed frontend URL in production. |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_API_KEY` | `""` | Required when `ENVIRONMENT != development` and host is non-loopback. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `MAX_CONCURRENT_CALLS` | `4` | Global semaphore capacity for simultaneous LLM/Hindsight calls. |
| `MAX_DAILY_CALLS` | `0` | Daily cap for expensive calls (analyze/compare/reflect). 0 = disabled. |
| `MAX_MONTHLY_CALLS` | `0` | Monthly cap. 0 = disabled. |

### Memory / privacy

| Variable | Default | Description |
|----------|---------|-------------|
| `RECALL_SAME_ENV_ONLY` | `true` | Filter recall results to the same environment tag (production stays production). |
| `RETAIN_NON_PRODUCTION` | `false` | Allow staging/development incidents to be written to the shared memory bank. |
| `MEMORY_REDACTION` | `true` | Redact emails, Bearer tokens, AWS key IDs, and PEM private-key blocks from content before it is sent to Groq or Hindsight. |

---

## Data retention and privacy

### What is sent to Groq

Each analysis call sends a JSON payload containing:

- `incident.title`, `service`, `environment`, `severity`, `status`
- `incident.symptoms` (truncated to 6 000 chars)
- `incident.error_logs` (truncated to 4 000 chars, if present)
- The last N updates (oldest dropped first to fit a 24 k char budget)
- Up to 5 recalled memory fragments from Hindsight (`{source_id, text, type}` only)

**What is NOT sent to Groq:**

- Raw `metrics` object (not included in the LLM payload)
- `client_request_id`
- `analysis` (previous analysis result)

With `MEMORY_REDACTION=true` (default), a regex pass strips emails, Bearer
tokens, AWS key IDs, and PEM private-key blocks from the content before it
reaches Groq.

Groq's data processing is governed by [Groq's privacy policy](https://groq.com/privacy-policy).

### What is sent to Hindsight

On resolution or retry-memory:

- A human-readable document built by `build_incident_memory_document()`:
  `title`, `service`, `environment`, `severity`, `status`, `symptoms`,
  first 500 chars of `error_logs`, `root_cause`, `actions_taken`,
  `resolution`, `outcome`, `lessons_learned`, `updates`.
- Metadata tags: `env:<env>`, `svc:<service>`, `status:<status>`, `outcome:<outcome>`.

With `MEMORY_REDACTION=true`, the same regex pass is applied to the document
before it is sent.

### How to delete data

**Local records:** `DELETE /api/incidents/{incident_id}` removes the SQLite
row and attempts to delete the Hindsight document for that `incident_id`.

**Hindsight bank:** Use the Hindsight dashboard or API to delete individual
documents or entire banks. The backend never deletes records on your behalf
except through the explicit `DELETE` route.

---

## Known limitations

- **Single-user / single-team:** No user authentication beyond the `APP_API_KEY`
  shared secret. All engineers with the key have equal access.
- **SQLite concurrency:** Suitable for one or a few concurrent users. For
  team-wide deployment, migrate to PostgreSQL.
- **Rate limits are in-process:** The token-bucket rate limiter resets when the
  server restarts and is not shared across workers or instances.
- **Memory status is eventual:** When `var_async=true` is returned by Hindsight,
  `memory_retained=true` is set immediately (status: `pending`). There is
  no webhook or polling to confirm the async operation completed.
- **LLM non-determinism:** Even with `temperature=0`, model outputs can vary
  between API calls. The comparison tool uses temperature 0 but notes this
  limitation in the UI.
- **Redaction is best-effort:** The regex-based redaction catches common PII
  patterns but is not exhaustive. Do not paste unredacted secrets into logs
  or symptoms fields.
- **Groq model availability:** The default model (`openai/gpt-oss-120b`) must be
  available on your Groq account. Change `GROQ_MODEL` if needed.

---

## Running tests

```bash
# Backend (all non-live tests)
cd backend
pytest tests/ -q -m "not live"

# Backend (live — requires real API keys)
pytest tests/ -m live

# Frontend
cd frontend
npm run test:run
```

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── config.py          # All settings (pydantic-settings)
│   │   ├── guardrails.py      # Post-generation deny-list
│   │   ├── hindsight_client.py # Shared Hindsight SDK wrapper
│   │   ├── llm.py             # Groq wrapper with retry + schema sanitisation
│   │   ├── main.py            # FastAPI app + all middleware
│   │   ├── prompts.py         # build_memory_query, build_llm_payload
│   │   ├── redaction.py       # PII redaction pass
│   │   ├── schemas.py         # Pydantic models + APP_VERSION
│   │   └── services/
│   │       ├── analysis_service.py
│   │       ├── incident_service.py
│   │       └── memory_service.py
│   ├── data/                  # SQLite database (git-ignored)
│   ├── seed/                  # Legacy incident seed data
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # All UI components
│   │   ├── scenarios.js       # Demo scenarios (form fields only)
│   │   └── services/api.js    # Typed fetch wrapper
│   └── package.json
├── scripts/
│   ├── setup.ps1 / setup.sh   # First-run configuration
│   ├── run.sh                 # Bash start script
│   └── seed_incidents.py      # One-time memory bank seeding
├── docs/
│   └── API_GUIDE.md           # Full API reference
├── Dockerfile                 # Multi-stage: node build → python runtime
├── docker-compose.yml
├── Makefile
└── CHANGELOG.md
```

---

## License

MIT — see `LICENSE` if present.
