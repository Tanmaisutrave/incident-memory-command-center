"""Incident API. Sync routes run in FastAPI's worker pool, never block its event loop."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas import (
    IncidentCreate, ResolutionRequest, IncidentUpdate,
    ComparisonRequest, MemoryRecallRequest, MemoryReflectRequest,
)
from app.services.incident_service import IncidentService
from app.services.memory_service import memory_service
from app.hindsight_client import hindsight_client
from app.llm import llm_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application-level singleton – created in lifespan, not at import time.
# ---------------------------------------------------------------------------
_incident_service: IncidentService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _incident_service
    _incident_service = IncidentService()
    _incident_service.import_legacy_once()
    yield
    # Nothing to tear down for SQLite; connections are closed per-request.


def get_incident_service() -> IncidentService:
    """FastAPI dependency that returns the live service instance."""
    if _incident_service is None:  # pragma: no cover – only during mis-wired tests
        raise RuntimeError('IncidentService not initialised. Use the lifespan handler.')
    return _incident_service


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title='Incident Memory Command Center', version='3.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, 'http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_methods=['GET', 'POST', 'DELETE'],
    allow_headers=['Content-Type'],
)


@app.exception_handler(Exception)
async def failure(request, exc):
    logger.error('Request failed: %s', type(exc).__name__)
    # Never expose upstream errors or credentials to the browser.
    return JSONResponse(status_code=502, content={
        'detail': (
            'The service could not complete this request. '
            'Check backend configuration or retry. '
            'No substitute diagnosis was generated.'
        )
    })


@app.exception_handler(RuntimeError)
async def invalid_response(request, exc):
    return JSONResponse(status_code=502, content={'detail': str(exc)})


@app.exception_handler(ValueError)
async def invalid_request(request, exc):
    return JSONResponse(status_code=400, content={'detail': str(exc)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get('/api/health')
def health():
    configured = lambda key: bool(key and not key.startswith('your_'))
    return {
        'status': (
            'ready'
            if configured(settings.groq_api_key) and configured(settings.hindsight_api_key)
            else 'setup_required'
        ),
        'groq_status': 'configured' if configured(settings.groq_api_key) else 'not_configured',
        'hindsight_status': 'configured' if configured(settings.hindsight_api_key) else 'not_configured',
        'bank_id': settings.hindsight_bank_id,
        'model': settings.groq_model,
        'note': 'Configuration status only. Use Check connections to verify connectivity.',
    }


_health_cache: dict = {}
_health_lock = Lock()


@app.get('/api/connections')
def connections():
    with _health_lock:
        if monotonic() - _health_cache.get('time', -100) < 60:
            return _health_cache['value']
        result = {}
        for name, check in [('groq', llm_client.health_check), ('hindsight', hindsight_client.health_check)]:
            try:
                result[name] = 'connected' if check() else 'unavailable'
            except Exception:
                result[name] = 'unavailable'
        _health_cache.update(time=monotonic(), value=result)
        return result


@app.get('/api/incidents')
def incidents(
    limit: int = 200,
    offset: int = 0,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.list_incidents(limit=limit, offset=offset)


@app.post('/api/incidents/analyze')
def analyze(
    data: IncidentCreate,
    svc: IncidentService = Depends(get_incident_service),
):
    incident = svc.create_incident(data)
    try:
        return svc.analyze_incident(incident.incident_id)
    except Exception as exc:
        raise HTTPException(
            502,
            f'Analysis failed. Incident {incident.incident_id} is saved; '
            f'open it from Overview to retry. '
            f'Check provider configuration and connectivity.',
        ) from exc


@app.post('/api/incidents/compare')
def compare(
    data: ComparisonRequest,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.compare_analysis(data.incident)


@app.get('/api/incidents/{incident_id}')
def incident(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    item = svc.get_incident(incident_id)
    if not item:
        raise HTTPException(404, 'Incident not found')
    return item


@app.post('/api/incidents/{incident_id}/analyze')
def reanalyze(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.analyze_incident(incident_id)


@app.post('/api/incidents/{incident_id}/updates')
def update(
    incident_id: str,
    data: IncidentUpdate,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.add_update(incident_id, data)


@app.post('/api/incidents/{incident_id}/resolve')
def resolve(
    incident_id: str,
    data: ResolutionRequest,
    svc: IncidentService = Depends(get_incident_service),
):
    item = svc.resolve_incident(incident_id, data)
    return {
        'incident_id': incident_id,
        'status': item.status,
        'memory_retained': item.memory_retained,
        'message': (
            'Outcome saved and memory retained.'
            if item.memory_retained
            else 'Outcome saved locally. Memory delivery failed; retry from this incident.'
        ),
    }


@app.post('/api/incidents/{incident_id}/retry-memory')
def retry_memory(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.retry_memory(incident_id)


@app.get('/api/incidents/{incident_id}/memories')
def memories(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    return svc.get_incident_memories(incident_id)


@app.delete('/api/incidents/{incident_id}')
def delete_incident(
    incident_id: str,
    svc: IncidentService = Depends(get_incident_service),
):
    svc.delete_incident(incident_id)
    return {'incident_id': incident_id, 'deleted': True}


@app.post('/api/memory/recall')
def recall(data: MemoryRecallRequest):
    rows = hindsight_client.recall(data.query, data.max_tokens, data.budget)
    return {
        'query': data.query,
        'memories': [
            {'memory_text': m['text'], 'source_id': m['source_id'], 'memory_type': m['type']}
            for m in rows
        ],
        'count': len(rows),
    }


@app.post('/api/memory/reflect')
def reflect(data: MemoryReflectRequest):
    return {'query': data.query, 'reflection': memory_service.reflect_on_patterns(data.query, data.budget)}


@app.get('/api/memory/stats')
def stats(svc: IncidentService = Depends(get_incident_service)):
    rows = svc.list_incidents()
    return {
        **memory_service.get_stats(),
        'total_incidents': len(rows),
        'retained_incidents': sum(i.memory_retained for i in rows),
        'active_incidents': sum(
            i.status.value not in ('resolved', 'closed') for i in rows
        ),
        'scope': 'Local incident records. Recall counters cover this server session only.',
    }


# ---------------------------------------------------------------------------
# Static frontend (production build served from same process)
# ---------------------------------------------------------------------------
dist = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if dist.exists():
    app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/')
    def index():
        return FileResponse(dist / 'index.html')


# ---------------------------------------------------------------------------
# Backwards-compat shim for tests that monkeypatch main.incident_service
# (tests should migrate to Depends, but we keep the name for now).
# ---------------------------------------------------------------------------
@property  # type: ignore[misc]
def incident_service():  # noqa: F811
    return _incident_service
