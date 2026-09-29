# API Guide — Incident Memory Command Center

Generated from the FastAPI OpenAPI schema (app version **3.1.0**).  
Base URL: `http://localhost:8000`

All `/api/*` routes except `/api/health` require the header `X-API-Key` when
`APP_API_KEY` is set in the environment (required outside `ENVIRONMENT=development`).

---

## Authentication

```
X-API-Key: <your APP_API_KEY>
```

Missing or incorrect key → **401 Unauthorized** with `{ "detail": "...", "request_id": "..." }`.

Every response includes `X-Request-ID` for log correlation.

---

## Error envelope

All errors return JSON:

```json
{ "detail": "Human-readable message", "request_id": "uuid" }
```

| Status | Meaning |
|--------|---------|
| 400 | Request-validation error from the service layer (invalid state transition, etc.) |
| 401 | Missing or invalid API key |
| 404 | Resource not found |
| 409 | Optimistic-concurrency conflict |
| 413 | Request body exceeds 256 KB |
| 422 | Pydantic schema validation failure |
| 429 | Rate limit exceeded — includes `Retry-After` header |
| 500 | Stored-data integrity error (never exposes field detail) |
| 502 | Upstream provider error (Groq / Hindsight) |

---

## Endpoints

### `GET /api/health`

Returns configuration status. **No auth required.**

**Response 200**
```json
{
  "status": "ready | setup_required",
  "groq_status": "configured | not_configured",
  "hindsight_status": "configured | not_configured",
  "bank_id": "incident-agent",
  "model": "openai/gpt-oss-120b",
  "note": "Configuration status only.",
  "version": "3.1.0"
}
```

---

### `GET /api/connections`

Checks live connectivity to Groq and Hindsight with a 6-second timeout each.
Results are cached: 60 s for success, 10 s for failure.

**Response 200**
```json
{ "groq": "connected | unavailable", "hindsight": "connected | unavailable" }
```

---

### `GET /api/incidents`

Returns a paginated list of incidents ordered by creation time, newest first.

**Query parameters**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | integer | 200 | Max records to return |
| `offset` | integer | 0 | Pagination offset |

**Response 200** — array of `IncidentSummary` objects (no `symptoms`, `error_logs`, or `analysis`).

---

### `POST /api/incidents/analyze`

Creates an incident and runs analysis in one call.

**Request body** — `IncidentCreate`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `title` | string | ✓ | 5–500 chars |
| `service` | string | ✓ | 2–100 chars |
| `environment` | `production \| staging \| development` | ✓ | |
| `severity` | `P1 \| P2 \| P3 \| P4` | ✓ | |
| `symptoms` | string | ✓ | 10–12 000 chars |
| `error_logs` | string | | max 20 000 chars |
| `metrics` | object | | max 8 KB serialised |
| `suspected_causes` | string[] | | max 10 items × 300 chars |
| `tags` | string[] | | max 20 items × 50 chars |
| `client_request_id` | string | | max 128 chars — idempotency key |

Sending the same `client_request_id` twice returns the existing incident and
re-runs analysis instead of creating a duplicate.

**Response 200** — `AnalysisResponse`

```json
{
  "incident_id": "INC-XXXXXXXX",
  "summary": "...",
  "likely_root_cause": "...",
  "severity_assessment": "P2",
  "severity_reasoning": "...",
  "evidence_assessment": "...",
  "investigation_steps": ["..."],
  "recommended_actions": ["..."],
  "disconfirming_checks": ["..."],
  "verification_steps": ["..."],
  "next_steps": "...",
  "risk_notes": "...",
  "historical_incidents": [...],
  "historical_evidence": [...],
  "memory_insights": [...],
  "cited_sources": [...],
  "used_memory": true,
  "memory_status": "retrieved | empty | unavailable | disabled",
  "warnings": [],
  "flagged_actions": [],
  "timings_ms": { "recall": 320, "model": 2100, "total": 2420 },
  "analysis_timestamp": "2024-01-01T00:00:00Z"
}
```

**Rate limit:** 5 requests / 60 s per IP.

---

### `POST /api/incidents/compare`

Runs the same incident through two analysis branches simultaneously:
one without historical memory and one with. Both use `temperature=0` for
reproducibility. Results can still vary between runs.

**Request body**
```json
{ "incident": { <same fields as IncidentCreate> } }
```

**Response 200**
```json
{
  "without_memory": { <AnalysisResponse> },
  "with_memory":    { <AnalysisResponse> },
  "differences": {
    "likely_root_cause": {
      "without_memory": "...",
      "with_memory": "..."
    }
  }
}
```

**Rate limit:** 5 requests / 60 s per IP (counts as 2 tokens).

---

### `GET /api/incidents/{incident_id}`

Returns the full `Incident` object including `symptoms`, `error_logs`, and `analysis`.

**Response 404** when the incident does not exist.

---

### `DELETE /api/incidents/{incident_id}`

Deletes the local record and attempts to delete the remote memory document.
The local delete always succeeds; remote failure is reported in the response.

**Response 200**
```json
{
  "incident_id": "INC-XXXXXXXX",
  "deleted": true,
  "memory_deleted": true,
  "memory_note": "Memory document deleted."
}
```

---

### `POST /api/incidents/{incident_id}/analyze`

Re-runs analysis on an existing incident. Only allowed when `status` is
`reported` or `investigating`.

**Response 200** — `AnalysisResponse`  
**Response 400** — if in a terminal status  
**Response 404** — incident not found

**Rate limit:** 5 requests / 60 s per IP.

---

### `POST /api/incidents/{incident_id}/updates`

Adds a human-reported update (evidence or failed attempt) to an incident.

**Request body** — `IncidentUpdate`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `note` | string | ✓ | 10–5 000 chars |
| `kind` | `evidence \| failed_attempt` | | default `evidence` |
| `reopen` | boolean | | default `false` — required to update a resolved incident |

Max 50 updates per incident.

**Response 200** — full `Incident` with `memory_retained` updated.

---

### `POST /api/incidents/{incident_id}/resolve`

Records an outcome and attempts to retain the incident in Hindsight memory.

**Request body** — `ResolutionRequest`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `root_cause` | string | ✓ | 10–5 000 chars |
| `resolution` | string | ✓ | 10–5 000 chars |
| `actions_taken` | string[] | ✓ | 1–20 items × 1 000 chars |
| `outcome` | `successfully_resolved \| partially_resolved \| unresolved_escalated` | ✓ | |
| `lessons_learned` | string | | max 5 000 chars |
| `preventive_actions` | string[] | | max 20 items |
| `downtime` | float | | minutes |
| `affected_users` | integer | | |
| `before_metrics` | object | | max 8 KB |
| `after_metrics` | object | | max 8 KB |

**Response 200**
```json
{
  "incident_id": "INC-XXXXXXXX",
  "status": "resolved",
  "memory_retained": true,
  "message": "Outcome saved and memory retained."
}
```

---

### `POST /api/incidents/{incident_id}/retry-memory`

Retries delivering the incident record to Hindsight memory.
Requires at least one update or an outcome to be recorded.

**Response 200** — full `Incident`

---

### `GET /api/incidents/{incident_id}/memories`

Recalls historical incidents similar to this one from Hindsight.

**Response 200**
```json
{
  "incident_id": "INC-XXXXXXXX",
  "memories": [ { "text": "...", "type": "world", "source_id": "uuid" } ],
  "count": 3
}
```

---

### `POST /api/memory/recall`

Manual memory recall against a free-form query.

**Request body**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `query` | string | ✓ | 5–3 000 chars |
| `max_tokens` | integer | | 100–10 000, default 4 096 |
| `budget` | `low \| mid \| high` | | default `mid` |

**Response 200**
```json
{ "query": "...", "memories": [...], "count": 2 }
```

---

### `POST /api/memory/reflect`

Asks Hindsight to synthesise patterns across all retained incidents.

**Request body**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `query` | string | ✓ | 10–3 000 chars |
| `budget` | `low \| mid \| high` | | default `mid` |

**Response 200**
```json
{ "query": "...", "reflection": "...", "timestamp": "..." }
```

**Rate limit:** 5 requests / 60 s per IP.

---

### `GET /api/memory/stats`

Returns aggregate counters for the current session and the workspace.

**Response 200**
```json
{
  "bank_id": "incident-agent",
  "total_recalls": 12,
  "total_retains": 4,
  "last_retain": "2024-01-01T00:00:00",
  "last_recall": "2024-01-01T00:00:00",
  "total_incidents": 8,
  "retained_incidents": 4,
  "active_incidents": 2,
  "scope": "Local incident records..."
}
```

---

## Rate limits

| Route pattern | Limit | Cost |
|---------------|-------|------|
| `*/analyze`, `*/compare`, `*/reflect` | 5 / min | compare costs 2 |
| All other POSTs | 30 / min | 1 |
| GETs | 120 / min | 1 |

Exceeded limits return **429** with `Retry-After` (seconds).

---

## Memory status lifecycle

| Value | Meaning |
|-------|---------|
| `not_recorded` | Retain was not attempted (e.g. non-production env blocked) |
| `pending` | Accepted async (queued) — shown as "Queued" in the UI |
| `accepted` | Accepted synchronously — shown as "Saved" |
| `failed` | SDK returned failure or raised an exception |
