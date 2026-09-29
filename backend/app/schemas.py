"""Pydantic schemas and domain exceptions for incident management and analysis."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Application version — single source of truth for HealthResponse and the
# FastAPI app title.
# ---------------------------------------------------------------------------
APP_VERSION = "3.1.0"

# ---------------------------------------------------------------------------
# Domain exceptions — raised by services, mapped to HTTP status codes in
# main.py exception handlers.
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Raised when a requested resource does not exist (→ HTTP 404)."""


class ConflictError(Exception):
    """Raised on optimistic-concurrency conflict or duplicate idempotency key (→ HTTP 409)."""


class ProviderError(Exception):
    """
    Raised when an upstream provider (LLM, memory) returns an error that
    should be surfaced to the caller with a safe, pre-approved message.
    Never include raw provider text or credentials (→ HTTP 502).
    """

    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    P1 = "P1"  # Critical - Production down
    P2 = "P2"  # High - Major functionality impaired
    P3 = "P3"  # Medium - Partial functionality impaired
    P4 = "P4"  # Low - Minor issue


class Environment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"


class IncidentStatus(str, Enum):
    REPORTED = "reported"
    INVESTIGATING = "investigating"
    DIAGNOSED = "diagnosed"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    CLOSED = "closed"
    MITIGATED = "mitigated"
    ESCALATED = "escalated"


# Statuses that are considered terminal (no automatic transition away from them).
TERMINAL_STATUSES = frozenset({
    IncidentStatus.RESOLVED,
    IncidentStatus.CLOSED,
    IncidentStatus.MITIGATED,
    IncidentStatus.ESCALATED,
})

# Maximum number of updates allowed per incident.
MAX_UPDATES_PER_INCIDENT = 50

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_METRICS_MAX_BYTES = 8 * 1024  # 8 KB


def _check_metrics_size(v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if v is None:
        return v
    if len(json.dumps(v)) > _METRICS_MAX_BYTES:
        raise ValueError(f"metrics object must not exceed {_METRICS_MAX_BYTES} bytes when serialised")
    return v


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class IncidentCreate(BaseModel):
    """Schema for creating a new incident."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=5, max_length=500)
    service: str = Field(..., min_length=2, max_length=100)
    environment: Environment
    severity: Severity
    symptoms: str = Field(..., min_length=10, max_length=12000)
    error_logs: Optional[str] = Field(default=None, max_length=20000)
    metrics: Optional[Dict[str, Any]] = None
    suspected_causes: Optional[List[str]] = Field(default=None, max_length=10)
    tags: Optional[List[str]] = Field(default=None, max_length=20)

    # Optional idempotency key — a retry with the same key returns the
    # existing incident instead of creating a duplicate.
    client_request_id: Optional[str] = Field(default=None, max_length=128)

    @field_validator("title", "service", "symptoms", mode="after")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v

    @field_validator("suspected_causes", mode="after")
    @classmethod
    def validate_suspected_causes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        for item in v:
            if len(item) > 300:
                raise ValueError("Each suspected_causes entry must not exceed 300 characters")
        return v

    @field_validator("tags", mode="after")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        for tag in v:
            if len(tag) > 50:
                raise ValueError("Each tag must not exceed 50 characters")
        return v

    @field_validator("metrics", mode="after")
    @classmethod
    def validate_metrics_size(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return _check_metrics_size(v)


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    note: str = Field(..., min_length=10, max_length=5000)
    kind: Literal["evidence", "failed_attempt"] = "evidence"
    reopen: bool = False

    @field_validator("note", mode="after")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("note must not be blank")
        return v


class ResolutionRequest(BaseModel):
    """Request to resolve an incident."""

    model_config = ConfigDict(str_strip_whitespace=True)

    root_cause: str = Field(..., min_length=10, max_length=5000)
    actions_taken: List[str] = Field(..., min_length=1, max_length=20)
    resolution: str = Field(..., min_length=10, max_length=5000)
    outcome: Literal["successfully_resolved", "partially_resolved", "unresolved_escalated"]
    before_metrics: Optional[Dict[str, Any]] = None
    after_metrics: Optional[Dict[str, Any]] = None
    downtime: Optional[float] = None
    affected_users: Optional[int] = None
    lessons_learned: Optional[str] = Field(default=None, max_length=5000)
    preventive_actions: Optional[List[str]] = Field(default=None, max_length=20)

    @field_validator("root_cause", "resolution", mode="after")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v

    @field_validator("actions_taken", mode="after")
    @classmethod
    def validate_actions_taken(cls, v: List[str]) -> List[str]:
        for action in v:
            if len(action) > 1000:
                raise ValueError("Each actions_taken entry must not exceed 1000 characters")
        return v

    @field_validator("before_metrics", "after_metrics", mode="after")
    @classmethod
    def validate_metrics_size(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return _check_metrics_size(v)


class MemoryRecallRequest(BaseModel):
    """Request for manual memory recall."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(..., min_length=5, max_length=3000)
    max_tokens: int = Field(default=4096, ge=100, le=10000)
    budget: str = Field(default="mid", pattern="^(low|mid|high)$")

    @field_validator("query", mode="after")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v


class MemoryReflectRequest(BaseModel):
    """Request for memory reflection."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(..., min_length=10, max_length=3000)
    budget: str = Field(default="mid", pattern="^(low|mid|high)$")

    @field_validator("query", mode="after")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v


class ComparisonRequest(BaseModel):
    incident: IncidentCreate
    use_memory: bool = True


# ---------------------------------------------------------------------------
# Domain / storage models
# ---------------------------------------------------------------------------


class Incident(BaseModel):
    """Complete incident model (stored as JSON payload in SQLite)."""

    incident_id: str
    title: str
    service: str
    environment: Environment
    severity: Severity
    status: IncidentStatus = IncidentStatus.REPORTED
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Initial information
    symptoms: str
    error_logs: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    suspected_causes: Optional[List[str]] = None
    tags: Optional[List[str]] = None

    # Idempotency
    client_request_id: Optional[str] = None

    # Diagnosis (filled after analysis)
    root_cause: Optional[str] = None
    actions_taken: Optional[List[str]] = None
    resolution: Optional[str] = None

    # Outcome (filled after resolution)
    outcome: Optional[str] = None
    downtime: Optional[float] = None
    affected_users: Optional[int] = None
    lessons_learned: Optional[str] = None
    preventive_actions: Optional[List[str]] = None
    before_metrics: Optional[Dict[str, Any]] = None
    after_metrics: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None
    memory_retained: bool = False
    analysis: Optional[Dict[str, Any]] = None
    updates: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class IncidentSummary(BaseModel):
    """Lightweight projection used in list endpoints (omits analysis and error_logs)."""

    incident_id: str
    title: str
    service: str
    environment: Environment
    severity: Severity
    status: IncidentStatus
    timestamp: datetime
    resolved_at: Optional[datetime] = None
    memory_retained: bool = False
    outcome: Optional[str] = None
    updates: List[Dict[str, Any]] = Field(default_factory=list)
    tags: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class HistoricalIncident(BaseModel):
    memory_text: str
    relevance_score: Optional[float] = None
    memory_type: Optional[str] = None
    source_id: Optional[str] = None


class AnalysisResponse(BaseModel):
    incident_id: str
    summary: str
    likely_root_cause: str
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    severity_assessment: Severity

    historical_incidents: List[HistoricalIncident] = Field(default_factory=list)
    historical_evidence: List[str] = Field(default_factory=list)
    memory_insights: List[str] = Field(default_factory=list)

    recommended_actions: List[str]
    investigation_steps: List[str]
    next_steps: str
    risk_notes: Optional[str] = None

    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    used_memory: bool = True
    memory_status: str = "disabled"
    warnings: List[str] = Field(default_factory=list)
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    evidence_assessment: str = "Unconfirmed hypothesis"
    disconfirming_checks: List[str] = Field(default_factory=list)
    verification_steps: List[str] = Field(default_factory=list)
    cited_sources: List[str] = Field(default_factory=list)


class ResolutionResponse(BaseModel):
    incident_id: str
    status: IncidentStatus
    memory_retained: bool
    message: str


class DeleteResponse(BaseModel):
    incident_id: str
    deleted: bool


class MemoryRecallResponse(BaseModel):
    query: str
    memories: List[HistoricalIncident]
    count: int


class MemoryReflectResponse(BaseModel):
    query: str
    reflection: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MemoryStats(BaseModel):
    bank_id: str
    total_recalls: int
    total_retains: int
    last_retain: Optional[datetime] = None
    last_recall: Optional[datetime] = None
    total_incidents: int = 0
    retained_incidents: int = 0
    active_incidents: int = 0
    scope: str = ""


class HealthResponse(BaseModel):
    status: str
    groq_status: str
    hindsight_status: str
    bank_id: str
    model: str
    note: str
    version: str = APP_VERSION


class ConnectionStatus(BaseModel):
    groq: str
    hindsight: str


class ComparisonResponse(BaseModel):
    without_memory: AnalysisResponse
    with_memory: AnalysisResponse


# ---------------------------------------------------------------------------
# Internal LLM model
# ---------------------------------------------------------------------------


class Diagnosis(BaseModel):
    """Only model-authored fields. All claims remain hypotheses until verified."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1500)
    likely_root_cause: str = Field(min_length=1, max_length=1500)
    evidence_assessment: str
    investigation_steps: List[str] = Field(min_length=1, max_length=5)
    recommended_actions: List[str] = Field(max_length=5)
    disconfirming_checks: List[str] = Field(min_length=1, max_length=4)
    verification_steps: List[str] = Field(min_length=1, max_length=4)
    historical_evidence: List[str] = Field(max_length=5)
    memory_insights: List[str] = Field(max_length=4)
    cited_sources: List[str] = Field(max_length=5)
    risk_notes: str
