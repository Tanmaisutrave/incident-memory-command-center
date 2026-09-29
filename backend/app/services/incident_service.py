"""Durable local incidents, analysis snapshots and memory delivery status."""
import json
import sqlite3
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from app.schemas import Incident, IncidentStatus
from app.services.analysis_service import analysis_service
from app.services.memory_service import memory_service


class IncidentService:
    def __init__(self, db_path=None):
        self.analysis = analysis_service
        self.memory = memory_service
        self.path = Path(db_path) if db_path else Path(__file__).resolve().parents[2] / 'data' / 'incidents.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        # Import the original checkout's JSON once, without modifying it.
        legacy = Path(__file__).resolve().parents[2] / 'backend/data/incidents/incidents.json'
        if db_path is None and legacy.exists():
            records = json.loads(legacy.read_text(encoding='utf-8')).get('incidents', [])
            with self._db() as db:
                for record in records:
                    item = Incident(**record)
                    db.execute('INSERT OR IGNORE INTO incidents VALUES (?, ?)', (item.incident_id, item.model_dump_json()))

    def _db(self):
        return sqlite3.connect(self.path, timeout=10)

    def _save(self, incident):
        with self._db() as db:
            db.execute('INSERT OR REPLACE INTO incidents VALUES (?, ?)', (incident.incident_id, incident.model_dump_json()))

    def get_incident(self, incident_id):
        with self._db() as db:
            row = db.execute('SELECT payload FROM incidents WHERE id=?', (incident_id,)).fetchone()
        return Incident.model_validate_json(row[0]) if row else None

    def list_incidents(self):
        with self._db() as db:
            rows = db.execute('SELECT payload FROM incidents ORDER BY rowid DESC').fetchall()
        return [Incident.model_validate_json(row[0]) for row in rows]

    def require(self, incident_id):
        incident = self.get_incident(incident_id)
        if incident is None:
            raise ValueError('Incident not found')
        return incident

    def create_incident(self, incident_data):
        incident = Incident(incident_id='INC-' + uuid4().hex[:8].upper(), **incident_data.model_dump())
        self._save(incident)
        return incident

    def analyze_incident(self, incident_id, use_memory=True):
        incident = self.require(incident_id)
        analysis = self.analysis.analyze_incident(incident.model_dump(mode='json'), use_memory)
        incident.analysis = analysis.model_dump(mode='json')
        if incident.status not in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
            incident.status = IncidentStatus.INVESTIGATING
        self._save(incident)
        return analysis

    def resolve_incident(self, incident_id, resolution):
        incident = self.require(incident_id)
        for name, value in resolution.model_dump().items():
            if name in Incident.model_fields:
                setattr(incident, name, value)
        incident.status = {'successfully_resolved': IncidentStatus.RESOLVED,
            'partially_resolved': IncidentStatus.MITIGATED,
            'unresolved_escalated': IncidentStatus.ESCALATED}[resolution.outcome]
        incident.resolved_at = datetime.utcnow() if incident.status == IncidentStatus.RESOLVED else None
        incident.memory_retained = False
        self._save(incident)  # Keep outcome even if remote memory is unavailable.
        incident.memory_retained = self.memory.retain_resolved_incident(
            incident.model_dump(mode='json'), resolution.model_dump(mode='json'))
        self._save(incident)
        return incident

    def add_update(self, incident_id, update):
        incident = self.require(incident_id)
        incident.updates.append({**update.model_dump(), 'timestamp': datetime.utcnow().isoformat()})
        incident.memory_retained = False
        incident.status = IncidentStatus.INVESTIGATING
        incident.analysis = None  # New evidence invalidates the displayed recommendation.
        incident.resolved_at = None
        self._save(incident)
        return self.retry_memory(incident_id)

    def retry_memory(self, incident_id):
        incident = self.require(incident_id)
        if not incident.updates and not incident.outcome:
            raise ValueError('Record evidence or an outcome before saving memory')
        incident.memory_retained = False
        self._save(incident)
        try:
            result = self.memory.hindsight.retain(
                content='INCIDENT RECORD (human-reported evidence; status may be unresolved):\n' + incident.model_dump_json(exclude={'analysis'}),
                metadata={'incident_id': incident.incident_id, 'service': incident.service},
                context=f'Incident updates for {incident.service}', document_id=incident.incident_id)
            incident.memory_retained = bool(result.get('success'))
        except Exception:
            incident.memory_retained = False
        self._save(incident)
        return incident

    def get_incident_memories(self, incident_id):
        item = self.require(incident_id)
        memories = self.memory.recall_similar_incidents(item.service, item.environment.value, item.symptoms)
        return {'incident_id': incident_id, 'memories': memories, 'count': len(memories)}

    def compare_analysis(self, incident_data):
        incident = {'incident_id': 'COMPARISON', **incident_data.model_dump(mode='json')}
        with ThreadPoolExecutor(max_workers=2) as pool:
            without = pool.submit(self.analysis.analyze_incident, incident, False)
            with_memory = pool.submit(self.analysis.analyze_incident, incident, True)
            return {'without_memory': without.result(), 'with_memory': with_memory.result()}


incident_service = IncidentService()
