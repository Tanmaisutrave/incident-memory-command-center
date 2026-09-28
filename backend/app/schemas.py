"""Pydantic schemas for incident management and analysis."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Incident severity levels."""
    P1 = "P1"  # Critical - Production down
    P2 = "P2"  # High - Major functionality impaired
    P3 = "P3"  # Medium - Partial functionality impaired
    P4 = "P4"  # Low - Minor issue


class Environment(str, Enum):
    """Deployment environments."""
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"


class IncidentStatus(str, Enum):
    """Incident lifecycle status."""
    REPORTED = "reported"
    INVESTIGATING = "investigating"
    DIAGNOSED = "diagnosed"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentCreate(BaseModel):
    """Schema for creating a new incident."""
    title: str = Field(..., min_length=5, max_length=500)
    service: str = Field(..., min_length=2, max_length=100)
    environment: Environment
    severity: Severity
    symptoms: str = Field(..., min_length=10)
    error_logs: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    suspected_causes: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class Incident(BaseModel):
    """Complete incident model."""
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
    
    # Diagnosis (filled after analysis)
    root_cause: Optional[str] = None
    actions_taken: Optional[List[str]] = None
    resolution: Optional[str] = None
    
    # Outcome (filled after resolution)
    outcome: Optional[str] = None
    downtime: Optional[float] = None  # in minutes
    affected_users: Optional[int] = None
    lessons_learned: Optional[str] = None
    before_metrics: Optional[Dict[str, Any]] = None
    after_metrics: Optional[Dict[str, Any]] = None
    resolved_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "incident_id": "INC-1001",
                "title": "Payment API High Latency",
                "service": "payment-api",
                "environment": "production",
                "severity": "P1",
                "symptoms": "API latency increased to 8.2 seconds, Redis timeout errors",
                "error_logs": "RedisTimeoutError: Timeout connecting to Redis",
                "metrics": {"latency_p99": 8200, "error_rate": 0.23}
            }
        }


class HistoricalIncident(BaseModel):
    """Historical incident from memory."""
    memory_text: str
    relevance_score: Optional[float] = None
    memory_type: Optional[str] = None


class AnalysisResponse(BaseModel):
    """AI analysis response for an incident."""
    incident_id: str
    summary: str
    likely_root_cause: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity_assessment: Severity
    
    # Historical context
    historical_incidents: List[HistoricalIncident] = Field(default_factory=list)
    historical_evidence: List[str] = Field(default_factory=list)
    memory_insights: List[str] = Field(default_factory=list)
    
    # Recommendations
    recommended_actions: List[str]
    investigation_steps: List[str]
    next_steps: str
    risk_notes: Optional[str] = None
    
    # Metadata
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    used_memory: bool = True


class ResolutionRequest(BaseModel):
    """Request to resolve an incident."""
    root_cause: str = Field(..., min_length=10)
    actions_taken: List[str] = Field(..., min_length=1)
    resolution: str = Field(..., min_length=10)
    outcome: str = Field(..., min_length=10)
    before_metrics: Optional[Dict[str, Any]] = None
    after_metrics: Optional[Dict[str, Any]] = None
    downtime: Optional[float] = None
    affected_users: Optional[int] = None
    lessons_learned: Optional[str] = None
    preventive_actions: Optional[List[str]] = None


class ResolutionResponse(BaseModel):
    """Response after resolving an incident."""
    incident_id: str
    status: IncidentStatus
    memory_retained: bool
    message: str


class MemoryRecallRequest(BaseModel):
    """Request for manual memory recall."""
    query: str = Field(..., min_length=5)
    max_tokens: int = Field(default=4096, ge=100, le=10000)
    budget: str = Field(default="mid", pattern="^(low|mid|high)$")


class MemoryRecallResponse(BaseModel):
    """Response from memory recall."""
    query: str
    memories: List[HistoricalIncident]
    count: int


class MemoryReflectRequest(BaseModel):
    """Request for memory reflection."""
    query: str = Field(..., min_length=10)
    budget: str = Field(default="mid", pattern="^(low|mid|high)$")


class MemoryReflectResponse(BaseModel):
    """Response from memory reflection."""
    query: str
    reflection: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MemoryStats(BaseModel):
    """Memory bank statistics."""
    bank_id: str
    total_recalls: int
    total_retains: int
    last_retain: Optional[datetime] = None
    last_recall: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    hindsight_status: str
    groq_status: str
    version: str = "2.0.0"


class ComparisonRequest(BaseModel):
    """Request for before/after memory comparison."""
    incident: IncidentCreate
    use_memory: bool = True
