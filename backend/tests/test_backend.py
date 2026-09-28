"""Tests for the Incident Memory Agent backend."""

import pytest
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# These tests can be run without API keys
# Integration tests requiring APIs are separate


def test_incident_schema():
    """Test incident schema validation."""
    from app.schemas import Incident, IncidentStatus, Severity, Environment
    
    incident = Incident(
        incident_id="INC-TEST-001",
        title="Test Incident",
        service="test-service",
        environment=Environment.PRODUCTION,
        severity=Severity.P2,
        status=IncidentStatus.REPORTED,
        symptoms="Test symptoms",
        timestamp=datetime.utcnow()
    )
    
    assert incident.incident_id == "INC-TEST-001"
    assert incident.severity == Severity.P2
    assert incident.status == IncidentStatus.REPORTED


def test_incident_create_schema():
    """Test incident creation schema validation."""
    from app.schemas import IncidentCreate, Environment, Severity
    
    incident_data = IncidentCreate(
        title="Test API Latency",
        service="api-service",
        environment=Environment.PRODUCTION,
        severity=Severity.P1,
        symptoms="High latency and timeout errors",
        error_logs="Connection timeout after 5000ms",
        tags=["timeout", "performance"]
    )
    
    assert incident_data.service == "api-service"
    assert incident_data.severity == Severity.P1


def test_analysis_response_schema():
    """Test analysis response schema."""
    from app.schemas import AnalysisResponse, Severity
    
    analysis = AnalysisResponse(
        incident_id="INC-TEST-001",
        summary="Test summary",
        likely_root_cause="Connection pool exhaustion",
        confidence=0.85,
        severity_assessment=Severity.P1,
        recommended_actions=["Increase connection pool"],
        investigation_steps=["Check pool metrics"],
        next_steps="Verify connection pool size",
        used_memory=True
    )
    
    assert analysis.confidence == 0.85
    assert len(analysis.recommended_actions) > 0


def test_memory_query_builder():
    """Test memory query building."""
    from app.prompts import build_memory_query
    
    query = build_memory_query(
        service="payment-api",
        environment="production",
        symptoms="Redis timeout and high latency",
        error_logs="RedisTimeoutError: timeout after 5000ms"
    )
    
    assert "payment-api" in query
    assert "production" in query
    assert "Redis" in query or "redis" in query


def test_resolution_memory_content():
    """Test resolution memory content generation."""
    from app.prompts import build_resolution_memory_content
    
    incident = {
        "incident_id": "INC-TEST-001",
        "title": "Test Incident",
        "service": "test-service",
        "environment": "production",
        "severity": "P2",
        "symptoms": "High latency"
    }
    
    resolution = {
        "root_cause": "Connection pool exhaustion",
        "actions_taken": ["Increased pool size"],
        "resolution": "Pool increased from 100 to 200",
        "outcome": "Latency normalized"
    }
    
    content = build_resolution_memory_content(incident, resolution)
    
    assert "INC-TEST-001" in content
    assert "Connection pool exhaustion" in content
    assert "test-service" in content


def test_category_extraction():
    """Test root cause category extraction."""
    from app.services.memory_service import memory_service
    
    assert memory_service._extract_category("Redis connection pool exhausted") == "cache"
    assert memory_service._extract_category("PostgreSQL slow query") == "database"
    assert memory_service._extract_category("Network latency spike") == "network"
    assert memory_service._extract_category("Memory leak OOMKilled") == "memory"
    assert memory_service._extract_category("CPU saturation") == "cpu"


def test_config_loading():
    """Test configuration loading."""
    from app.config import settings
    
    # These should be set from .env
    assert settings.hindsight_bank_id == "incident-agent"
    assert settings.hindsight_base_url
    assert settings.groq_model


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
