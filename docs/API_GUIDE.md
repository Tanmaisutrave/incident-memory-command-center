# API Guide - Incident Memory Agent

Complete guide to using the Incident Memory Agent API.

---

## Base URL

```
http://localhost:8000
```

---

## Quick Start

### 1. Health Check

Verify the system is healthy:

```bash
curl http://localhost:8000/api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-09-27T...",
  "hindsight_status": "healthy",
  "groq_status": "healthy",
  "version": "2.0.0"
}
```

---

## Core Workflows

### Workflow 1: Analyze a New Incident

**Endpoint:** `POST /api/incidents/analyze`

**Request:**
```json
{
  "title": "Payment API High Latency",
  "service": "payment-api",
  "environment": "production",
  "severity": "P1",
  "symptoms": "API latency at 8 seconds, Redis timeout errors, 502 responses",
  "error_logs": "RedisTimeoutError: timeout after 5000ms",
  "metrics": {
    "latency_p99": 8200,
    "error_rate": 0.23
  },
  "suspected_causes": ["Redis connection pool exhaustion"],
  "tags": ["redis", "performance"]
}
```

**Response:**
```json
{
  "incident_id": "INC-1013",
  "summary": "Payment API experiencing severe latency...",
  "likely_root_cause": "Redis connection pool exhaustion...",
  "confidence": 0.92,
  "severity_assessment": "P1",
  "historical_incidents": [
    {
      "memory_text": "INCIDENT: INC-1001 - Payment API Redis Timeout...",
      "memory_type": "world"
    }
  ],
  "historical_evidence": [
    "INC-1001: Redis pool exhaustion (100→250 connections)",
    "INC-1006: Similar pattern during flash sale (250→400)"
  ],
  "memory_insights": [
    "Two previous incidents with identical symptoms...",
    "Both resolved by increasing connection pool size"
  ],
  "recommended_actions": [
    "Check current Redis connection pool utilization",
    "Verify connection pool is not at capacity",
    "Consider increasing pool size based on usage"
  ],
  "investigation_steps": [
    "1. Check Redis metrics and connection count",
    "2. Review connection pool configuration",
    "3. Analyze traffic patterns"
  ],
  "next_steps": "Start with: Check Redis connection pool utilization",
  "risk_notes": "Similar to INC-1001 and INC-1006...",
  "analysis_timestamp": "2026-09-27T...",
  "used_memory": true
}
```

**Key Points:**
- Historical incidents are automatically recalled from Hindsight
- Analysis includes evidence from similar past incidents
- Recommendations are informed by previous resolutions
- Confidence score based on historical data quality

---

### Workflow 2: Resolve an Incident

**Endpoint:** `POST /api/incidents/{incident_id}/resolve`

**Request:**
```json
{
  "root_cause": "Redis connection pool exhausted at peak load",
  "actions_taken": [
    "Verified Redis health",
    "Checked pool metrics - 100/100 in use",
    "Increased pool from 100 to 250",
    "Restarted application"
  ],
  "resolution": "Increased Redis connection pool size from 100 to 250",
  "outcome": "Latency reduced from 8.2s to 1.1s, error rate dropped to 0%",
  "before_metrics": {
    "latency_p99": 8200,
    "error_rate": 0.23,
    "connections_used": 100
  },
  "after_metrics": {
    "latency_p99": 1100,
    "error_rate": 0,
    "connections_used": 65
  },
  "downtime": 18,
  "affected_users": 3500,
  "lessons_learned": "Monitor connection pool proactively. Set alerts at 80% capacity.",
  "preventive_actions": [
    "Add connection pool monitoring",
    "Set alerts at 80% utilization",
    "Regular capacity planning"
  ]
}
```

**Response:**
```json
{
  "incident_id": "INC-1013",
  "status": "resolved",
  "memory_retained": true,
  "message": "Incident INC-1013 resolved and retained to memory"
}
```

**What Happens:**
1. Incident is marked as resolved
2. Resolution details are stored
3. Complete incident + resolution is retained to Hindsight
4. Future incidents can now learn from this resolution

---

### Workflow 3: Compare With/Without Memory

**Endpoint:** `POST /api/incidents/compare`

**Request:**
```json
{
  "incident": {
    "title": "Database Connection Timeout",
    "service": "order-service",
    "environment": "production",
    "severity": "P1",
    "symptoms": "Database queries timing out, connection pool exhausted"
  }
}
```

**Response:**
```json
{
  "incident_id": "INC-1014",
  "without_memory": {
    "incident_id": "INC-1014",
    "summary": "Generic database troubleshooting...",
    "likely_root_cause": "Possible connection pool or network issues",
    "confidence": 0.65,
    "historical_incidents": [],
    "recommended_actions": [
      "Check database connectivity",
      "Review network latency",
      "Verify database health"
    ]
  },
  "with_memory": {
    "incident_id": "INC-1014",
    "summary": "Similar to INC-1002 which was caused by...",
    "likely_root_cause": "Connection pool exhaustion due to slow queries",
    "confidence": 0.88,
    "historical_incidents": [
      { "memory_text": "INC-1002: Order Service Connection Exhaustion..." }
    ],
    "historical_evidence": [
      "INC-1002: Slow queries holding connections",
      "Resolution: Added index, increased pool size"
    ],
    "recommended_actions": [
      "Identify slow queries holding connections",
      "Review connection pool configuration",
      "Check for missing database indexes"
    ]
  }
}
```

**Use Case:** Demonstrates the value of memory to stakeholders and judges.

---

## Memory Operations

### Manual Memory Search

**Endpoint:** `POST /api/memory/recall`

**Request:**
```json
{
  "query": "Redis connection pool exhaustion and timeouts",
  "max_tokens": 4096,
  "budget": "mid"
}
```

**Response:**
```json
{
  "query": "Redis connection pool exhaustion and timeouts",
  "memories": [
    {
      "memory_text": "INCIDENT: INC-1001 - Payment API Redis Timeout...",
      "memory_type": "world"
    },
    {
      "memory_text": "INCIDENT: INC-1006 - Payment API Redis Timeout During Flash Sale...",
      "memory_type": "world"
    }
  ],
  "count": 2
}
```

**Parameters:**
- `budget`: "low", "mid", "high" - controls search depth/quality
- `max_tokens`: maximum context size (100-10000)

---

### Pattern Discovery (Reflection)

**Endpoint:** `POST /api/memory/reflect`

**Request:**
```json
{
  "query": "What are the most common incident patterns and resolutions?",
  "budget": "high"
}
```

**Response:**
```json
{
  "query": "What are the most common incident patterns and resolutions?",
  "reflection": "Analysis of historical incidents reveals...\n\n1. Connection Pool Exhaustion (40% of incidents):\n   - Most common in Redis and PostgreSQL\n   - Resolution: Increase pool size + monitoring\n   - Services affected: payment-api, order-service\n\n2. Resource Saturation (25%):\n   - CPU, Memory, Disk issues\n   - Resolution: Optimization + scaling\n\n3. Network Issues (20%):\n   - Timeouts, latency spikes\n   - Resolution: Infrastructure fixes, fallbacks\n\n...",
  "timestamp": "2026-09-27T..."
}
```

**Use Cases:**
- Identifying recurring patterns
- Finding common root causes
- Discovering successful resolution strategies
- Generating operational insights

---

## Information Retrieval

### Get Incident Details

**Endpoint:** `GET /api/incidents/{incident_id}`

**Response:**
```json
{
  "incident_id": "INC-1013",
  "title": "Payment API High Latency",
  "service": "payment-api",
  "environment": "production",
  "severity": "P1",
  "status": "resolved",
  "symptoms": "...",
  "root_cause": "...",
  "resolution": "...",
  "outcome": "...",
  "timestamp": "...",
  "resolved_at": "..."
}
```

---

### Get Related Memories

**Endpoint:** `GET /api/incidents/{incident_id}/memories`

**Response:**
```json
{
  "incident_id": "INC-1013",
  "memories": [
    {
      "text": "INCIDENT: INC-1001...",
      "type": "world"
    }
  ],
  "count": 2
}
```

Shows which historical incidents are related to this incident.

---

### Memory Statistics

**Endpoint:** `GET /api/memory/stats`

**Response:**
```json
{
  "bank_id": "incident-agent",
  "total_recalls": 42,
  "total_retains": 15,
  "last_retain": "2026-09-27T...",
  "last_recall": "2026-09-27T..."
}
```

---

## Data Models

### Severity Levels
- `P1` - Critical (production down)
- `P2` - High (major functionality impaired)
- `P3` - Medium (partial functionality impaired)
- `P4` - Low (minor issue)

### Environments
- `production`
- `staging`
- `development`

### Incident Status
- `reported` - Initial state
- `investigating` - Being analyzed
- `diagnosed` - Root cause identified
- `resolving` - Fix being applied
- `resolved` - Fixed and retained to memory
- `closed` - Archived

---

## Error Responses

### 404 Not Found
```json
{
  "detail": "Incident INC-9999 not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Analysis failed: Connection timeout"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "severity"],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    }
  ]
}
```

---

## Best Practices

### 1. Always Use Memory
```json
{
  "use_memory": true  // Default and recommended
}
```

Memory-informed analysis is the core value proposition.

### 2. Provide Rich Context
Include symptoms, error logs, metrics, and suspected causes for best results.

### 3. Document Resolutions Thoroughly
The more detail in resolutions, the more valuable the memory becomes for future incidents.

### 4. Use Reflection Periodically
Run reflection queries monthly to discover operational insights.

### 5. Monitor Memory Statistics
Track recall/retain counts to verify the agent is learning.

---

## Interactive Documentation

Visit http://localhost:8000/docs for interactive Swagger documentation where you can:
- Try all endpoints
- See request/response schemas
- Test with your own data
- Download OpenAPI spec

---

## Python SDK Example

```python
import requests

# Analyze incident
response = requests.post(
    "http://localhost:8000/api/incidents/analyze",
    json={
        "title": "API Timeout",
        "service": "payment-api",
        "environment": "production",
        "severity": "P1",
        "symptoms": "Timeout errors"
    }
)

analysis = response.json()
print(f"Root cause: {analysis['likely_root_cause']}")
print(f"Confidence: {analysis['confidence']}")
```

---

## Support

For issues or questions:
- Check logs: Application logs show detailed information
- Health check: Verify Hindsight and Groq connectivity
- Documentation: See docs/ folder
- Tests: Run scripts/test_agent.py

---

**API Version:** 2.0.0  
**Last Updated:** 2026-09-27
