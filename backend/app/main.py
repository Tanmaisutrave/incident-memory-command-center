"""Main FastAPI application for Incident Memory Agent."""

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas import (
    HealthResponse, IncidentCreate, AnalysisResponse,
    ResolutionRequest, ResolutionResponse, IncidentStatus,
    MemoryRecallRequest, MemoryRecallResponse, HistoricalIncident,
    MemoryReflectRequest, MemoryReflectResponse, MemoryStats,
    ComparisonRequest
)
from app.services.incident_service import incident_service
from app.services.memory_service import memory_service
from app.hindsight_client import hindsight_client
from app.llm import llm_client
from app.prompts import build_reflection_query

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Incident Memory Agent")
    logger.info(f"Hindsight Bank: {settings.hindsight_bank_id}")
    logger.info(f"Groq Model: {settings.groq_model}")
    yield
    logger.info("Shutting down Incident Memory Agent")


# Create FastAPI app
app = FastAPI(
    title="Incident Memory Agent",
    description="AI-powered incident response with operational memory",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred"}
    )


# Health endpoint
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns system health status.
    """
    try:
        # Check Hindsight
        hindsight_healthy = hindsight_client.health_check()
        hindsight_status = "healthy" if hindsight_healthy else "unhealthy"
        
        # Check Groq
        groq_healthy = llm_client.health_check()
        groq_status = "healthy" if groq_healthy else "unhealthy"
        
        # Overall status
        overall_status = "healthy" if (hindsight_healthy and groq_healthy) else "degraded"
        
        return HealthResponse(
            status=overall_status,
            hindsight_status=hindsight_status,
            groq_status=groq_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check failed"
        )


# Incident endpoints
@app.post("/api/incidents/analyze", response_model=AnalysisResponse)
async def analyze_incident(incident_data: IncidentCreate):
    """
    Analyze a new incident.
    
    This endpoint:
    1. Creates an incident record
    2. Recalls similar historical incidents from Hindsight
    3. Analyzes the incident using AI with historical context
    4. Returns structured diagnosis and recommendations
    """
    try:
        logger.info(f"Analyzing new incident: {incident_data.title}")
        
        # Create incident
        incident = incident_service.create_incident(incident_data)
        
        # Analyze with memory
        analysis = incident_service.analyze_incident(
            incident_id=incident.incident_id,
            use_memory=True
        )
        
        return analysis
        
    except Exception as e:
        logger.error(f"Incident analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@app.post("/api/incidents/{incident_id}/resolve", response_model=ResolutionResponse)
async def resolve_incident(incident_id: str, resolution: ResolutionRequest):
    """
    Resolve an incident and store it in memory.
    
    This endpoint:
    1. Updates the incident with resolution details
    2. Retains the incident and outcome to Hindsight
    3. Makes the incident available for future analysis
    """
    try:
        logger.info(f"Resolving incident: {incident_id}")
        
        # Resolve incident
        incident = incident_service.resolve_incident(
            incident_id=incident_id,
            resolution=resolution
        )
        
        return ResolutionResponse(
            incident_id=incident_id,
            status=incident.status,
            memory_retained=True,
            message=f"Incident {incident_id} resolved and retained to memory"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Resolution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resolution failed: {str(e)}"
        )


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """
    Get an incident by ID.
    
    Returns the complete incident record.
    """
    try:
        incident = incident_service.get_incident(incident_id)
        
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident {incident_id} not found"
            )
        
        return incident
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get incident: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve incident"
        )


@app.get("/api/incidents/{incident_id}/memories")
async def get_incident_memories(incident_id: str):
    """
    Get historical memories related to an incident.
    
    Returns similar incidents from Hindsight memory.
    """
    try:
        memories = incident_service.get_incident_memories(incident_id)
        return memories
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memories"
        )


# Memory endpoints
@app.post("/api/memory/recall", response_model=MemoryRecallResponse)
async def recall_memory(request: MemoryRecallRequest):
    """
    Manually recall memories from Hindsight.
    
    Useful for testing and exploring the memory bank.
    """
    try:
        logger.info(f"Manual recall: {request.query[:50]}...")
        
        # Run blocking Hindsight call in executor
        loop = asyncio.get_event_loop()
        memories = await loop.run_in_executor(
            executor,
            lambda: hindsight_client.recall(
                query=request.query,
                max_tokens=request.max_tokens,
                budget=request.budget
            )
        )
        
        historical_incidents = [
            HistoricalIncident(
                memory_text=mem.get('text', ''),
                memory_type=mem.get('type')
            )
            for mem in memories
        ]
        
        return MemoryRecallResponse(
            query=request.query,
            memories=historical_incidents,
            count=len(historical_incidents)
        )
        
    except Exception as e:
        logger.error(f"Recall failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recall failed: {str(e)}"
        )


@app.post("/api/memory/reflect", response_model=MemoryReflectResponse)
async def reflect_memory(request: MemoryReflectRequest):
    """
    Perform reflection to discover patterns across memories.
    
    Analyzes historical incidents to identify trends and insights.
    """
    try:
        logger.info(f"Reflection: {request.query[:50]}...")
        
        # Run blocking reflection in executor
        loop = asyncio.get_event_loop()
        reflection = await loop.run_in_executor(
            executor,
            lambda: memory_service.reflect_on_patterns(
                query=request.query,
                budget=request.budget
            )
        )
        
        return MemoryReflectResponse(
            query=request.query,
            reflection=reflection
        )
        
    except Exception as e:
        logger.error(f"Reflection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reflection failed: {str(e)}"
        )


@app.get("/api/memory/stats", response_model=MemoryStats)
async def get_memory_stats():
    """
    Get memory service statistics.
    
    Returns usage statistics for the memory bank.
    """
    try:
        stats = memory_service.get_stats()
        return MemoryStats(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@app.post("/api/incidents/compare")
async def compare_analysis(request: ComparisonRequest):
    """
    Compare incident analysis with and without memory.
    
    Demonstrates the value of historical memory.
    """
    try:
        logger.info("Comparing analysis with/without memory")
        
        comparison = incident_service.compare_analysis(request.incident)
        
        return comparison
        
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {str(e)}"
        )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Incident Memory Agent",
        "version": "2.0.0",
        "description": "AI-powered incident response with operational memory",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
