"""Incident API.

Sync routes run in FastAPI's worker pool, never block its event loop.

Error hierarchy
---------------
NotFoundError          → 404
ConflictError          → 409
ValueError             → 400  (request-validation errors from service layer)
pydantic.ValidationError → 500  (stored data failed to deserialise – never expose detail)
ProviderError          → 502  (safe pre-approved message from service layer)
Everything else        → 502  (generic message; full traceback logged with request_id)
"""

import logging
import uuid
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from time import monotonic
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError as PydanticValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.schemas import (
    APP_VERSION,
    AnalysisResponse,
    ComparisonRequest,
    ComparisonResponse,
    ConflictError,
    ConnectionStatus,
    DeleteResponse,
    HealthResponse,
    Incident,
    IncidentCreate,
    IncidentSummary,
    IncidentUpdate,
    MemoryRecallRequest,
    MemoryRecallResponse,
    MemoryReflectRequest,
    MemoryReflectResponse,
    MemoryStats,
    NotFoundError,
    ProviderError,
    ResolutionRequest,
    ResolutionResponse,
)
from app.services.incident_service import IncidentService
from app.services.memory_service import memory_service
from app.hindsight_client import hindsight_client
from app.llm import llm_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------
_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request; return it in responses."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers[_REQUEST_ID_HEADER] = req_id
        return response


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


# ---------------------------------------------------------------------------
# Application-level singleton – created in lifespan, not at import time.
# ---------------------------------------------------------------------------
_incident_service: Optional[IncidentService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _incident_service

    # Configure logging from environment
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    _incident_service = IncidentService()
    _incident_service.import_legacy_once()
    yield
    # Close the shared Hindsight SDK connection on shutdown.
    hindsight_client.close()


def get_incident_service() -> IncidentService:
    """FastAPI dependency that returns the live service instance."""
    if _incident_service is None:  # pragma: no cover
        raise RuntimeError("IncidentService not initialised. Use the lifespan handler.")
    return _incident_service


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Incident Memory Command Center",
    version=APP_VERSION,
    lifespan=lifespan,
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", _REQUEST_ID_HEADER],
    expose_headers=[_REQUEST_ID_HEADER],
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "request_id": _req_id(request)},
        headers={_REQUEST_ID_HEADER: _req_id(request)},
    )


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc), "request_id": _req_id(request)},
        headers={_REQUEST_ID_HEADER: _req_id(request)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    # Only request-validation errors from the service layer reach here.
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "request_id": _req_id(request)},
        headers={_REQUEST_ID_HEADER: _req_id(request)},
    )


@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError):
    logger.exception(
        "Provider error [request_id=%s]: %s", _req_id(request), exc.safe_message
    )
    return JSONResponse(
        status_code=502,
        content={"detail": exc.safe_message, "request_id": _req_id(request)},
        headers={_REQUEST_ID_HEADER: _req_id(request)},
    )


@app.exception_handler(PydanticValidationError)
async def stored_data_validation_handler(request: Request, exc: PydanticValidationError):
    # A stored payload failed to deserialise – data-integrity issue, never
    # expose field details to the client.
    logger.exception(
        "Stored-data validation error [request_id=%s]", _req_id(request)
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal data integrity error. Contact support.",
            "request_id": _req_id(request),
        },
        headers={_REQUEST_ID_HEADER: _req_id(request)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    # RuntimeError from third-party libraries: log with traceback, return generic 502.
    logger.exception(
        "RuntimeError [request_id=%s] %s", _req_id(request), type(exc).__name__
    )
    return JSONResponse(
        status_code=502,
        content={
            "detail": (
                "The service could not complete this request. "
                "Check backend configuration or retry. "
                "No substitute diagnosis was generated."
            ),
            "request_id": _req_id(request),
        },
        headers={_REQUEST_ID_HEADER: _req_id(request)},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception [request_id=%s] %s", _req_id(request), type(exc).__name__
    )
    return JSONResponse(
        status_code=502,
        content={
            "detail": (
                "The service could not complete this request. "
                "Check backend configuration or retry. "
                "No substitute diagnosis was generated."
            ),
            "request_id": _req_id(request),
        },
        headers={_REQUEST_ID_HEADER: _req_id(request)},
    )


# ---------------------------------------------------------------------------
# /api/connections — per-provider cache, lock-free during network calls
# ---------------------------------------------------------------------------
_CONN_OK_TTL = 60.0    # cache a successful check for 60 s
_CONN_ERR_TTL = 10.0   # cache a failed check for only 10 s
_CONN_TIMEOUT = 6.0    # individual provider timeout

_provider_cache: Dict[str, dict] = {}   # {name: {time, value}}


def _check_provider(name: str, check_fn) -> str:
    """Run check_fn with a 6 s timeout; update per-provider cache."""
    now = monotonic()
    cached = _provider_cache.get(name, {})
    ttl = _CONN_OK_TTL if cached.get("value") == "connected" else _CONN_ERR_TTL
    if now - cached.get("time", -1000) < ttl:
        return cached["value"]

    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(check_fn)
        try:
            ok = future.result(timeout=_CONN_TIMEOUT)
            result = "connected" if ok else "unavailable"
        except Exception:
            result = "unavailable"

    _provider_cache[name] = {"time": monotonic(), "value": result}
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
def health():
    configured = lambda key: bool(key and not key.startswith("your_"))
    return HealthResponse(
        status=(
            "ready"
            if configured(settings.groq_api_key) and configured(settings.hindsight_api_key)
            else "setup_required"
        ),
        groq_status="configured" if configured(settings.groq_api_key) else "not_configured",
        hindsight_status="configured" if configured(settings.hindsight_api_key) else "not_configured",
        bank_id=settings.hindsight_bank_id,
        model=settings.groq_model,
        note="Configuration status only. Use Check connections to verify connectivity.",
    )


@app.get("/api/connections", response_model=ConnectionStatus)
def connections():
    # Both checks run independently; no shared lock held during network I/O.
    with ThreadPoolExecutor(max_workers=2) as ex:
        groq_f = ex.submit(_check_provider, "groq", llm_client.health_check)
        hd_f = ex.submit(_check_provider, "hindsight", hindsight_client.health_check)
        groq_status = groq_f.result()
        hd_status = hd_f.result()
    return ConnectionStatus(groq=groq_status, hindsight=hd_status)


@app.get("/api/incidents", response_model=List[IncidentSummary])
def incidents(
    limit: int = 200,
    offset: int = 0,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.list_incidents(limit=limit, offset=offset)


@app.post("/api/incidents/analyze", response_model=AnalysisResponse)
def analyze(
    request: Request,
    data: IncidentCreate,
    svc: IncidentService = Depends(get_incident_service),
):
    incident = svc.create_incident(data)
    try:
        return svc.analyze_incident(incident.incident_id)
    except (NotFoundError, ValueError, ConflictError):
        raise  # Let the typed handlers deal with these.
    except Exception as exc:
        logger.exception(
            "Analysis failed [request_id=%s] incident_id=%s",
            _req_id(request),
            incident.incident_id,
        )
        raise ProviderError(
            f"Analysis failed. Incident {incident.incident_id} is saved; "
            "open it from Overview to retry. "
            "Check provider configuration and connectivity."
        ) from exc


@app.post("/api/incidents/compare", response_model=ComparisonResponse)
def compare(
    data: ComparisonRequest,
    svc: IncidentService = Depends(get_incident_service),
):
    result = svc.compare_analysis(data.incident)
    return ComparisonResponse(
        without_memory=result["without_memory"],
        with_memory=result["with_memory"],
        differences=result.get("differences", {}),
    )


@app.get("/api/incidents/{incident_id}", response_model=Incident)
def incident(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    item = svc.get_incident(incident_id)
    if not item:
        raise NotFoundError(f"Incident {incident_id!r} not found")
    return item


@app.post("/api/incidents/{incident_id}/analyze", response_model=AnalysisResponse)
def reanalyze(
    incident_id: str,
    request: Request,
    svc: IncidentService = Depends(get_incident_service),
):
    try:
        return svc.analyze_incident(incident_id)
    except (NotFoundError, ValueError, ConflictError):
        raise
    except Exception as exc:
        logger.exception(
            "Re-analysis failed [request_id=%s] incident_id=%s",
            _req_id(request),
            incident_id,
        )
        raise ProviderError(
            f"Analysis failed. Incident {incident_id} is saved; "
            "open it from Overview to retry. "
            "Check provider configuration and connectivity."
        ) from exc


@app.post("/api/incidents/{incident_id}/updates", response_model=Incident)
def update(
    incident_id: str,
    data: IncidentUpdate,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.add_update(incident_id, data)


@app.post("/api/incidents/{incident_id}/resolve", response_model=ResolutionResponse)
def resolve(
    incident_id: str,
    data: ResolutionRequest,
    svc: IncidentService = Depends(get_incident_service),
):
    item = svc.resolve_incident(incident_id, data)
    return ResolutionResponse(
        incident_id=incident_id,
        status=item.status,
        memory_retained=item.memory_retained,
        message=(
            "Outcome saved and memory retained."
            if item.memory_retained
            else "Outcome saved locally. Memory delivery failed; retry from this incident."
        ),
    )


@app.post("/api/incidents/{incident_id}/retry-memory", response_model=Incident)
def retry_memory(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.retry_memory(incident_id)


@app.get("/api/incidents/{incident_id}/memories")
def memories(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.get_incident_memories(incident_id)


@app.delete("/api/incidents/{incident_id}", response_model=DeleteResponse)
def delete_incident(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    result = svc.delete_incident(incident_id)
    return DeleteResponse(
        incident_id=incident_id,
        deleted=result["deleted"],
        memory_deleted=result["memory_deleted"],
        memory_note=result["memory_note"],
    )


@app.post("/api/memory/recall", response_model=MemoryRecallResponse)
def recall(data: MemoryRecallRequest):
    rows = hindsight_client.recall(data.query, data.max_tokens, data.budget)
    return MemoryRecallResponse(
        query=data.query,
        memories=[
            {"memory_text": m["text"], "source_id": m["source_id"], "memory_type": m["type"]}
            for m in rows
        ],
        count=len(rows),
    )


@app.post("/api/memory/reflect", response_model=MemoryReflectResponse)
def reflect(data: MemoryReflectRequest):
    return MemoryReflectResponse(
        query=data.query,
        reflection=memory_service.reflect_on_patterns(data.query, data.budget),
    )


@app.get("/api/memory/stats", response_model=MemoryStats)
def stats(svc: IncidentService = Depends(get_incident_service)):
    rows = svc.list_incidents()
    return MemoryStats(
        **memory_service.get_stats(),
        total_incidents=len(rows),
        retained_incidents=sum(i.memory_retained for i in rows),
        active_incidents=sum(
            i.status.value not in ("resolved", "closed") for i in rows
        ),
        scope="Local incident records. Recall counters cover this server session only.",
    )


# ---------------------------------------------------------------------------
# Static frontend (production build served from same process)
# ---------------------------------------------------------------------------
dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(dist / "index.html")
