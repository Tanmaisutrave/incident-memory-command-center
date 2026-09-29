"""Durable local incidents, analysis snapshots and memory delivery status.

Design notes
------------
* _db() is a @contextmanager: always commits or rolls back, always closes the
  connection.  WAL mode, 10 s busy-timeout and foreign_keys are set on every
  connection so the file is safe for concurrent FastAPI worker threads.

* Optimistic concurrency: every row carries a `version` integer.  _save()
  issues UPDATE … WHERE id=? AND version=? and raises ConflictError on 0 rows.
  New rows go through an INSERT … ON CONFLICT DO NOTHING.

* Slow-call isolation: analyze_incident / resolve_incident / add_update /
  retry_memory re-read the row *after* the slow provider call and merge only
  the fields they own, so a concurrent write to a different field is never
  silently discarded.

* Legacy import runs once, guarded by a `meta` table flag, so deleted records
  never reappear.

* Memory status lifecycle:
      not_recorded → failed / pending (async) / accepted (sync)
  ``memory_retained`` (bool) is kept for backward compatibility with older
  stored payloads and the summary list; it is True only when memory_status
  is accepted or pending.

* delete_incident also attempts to delete the remote memory document.  A
  failure there is logged and returned to the caller but does NOT prevent the
  local record from being deleted.
"""

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
from uuid import uuid4
import sqlite3

from app.schemas import (
    ConflictError,
    Incident,
    IncidentCreate,
    IncidentStatus,
    IncidentSummary,
    IncidentUpdate,
    NotFoundError,
    ResolutionRequest,
    TERMINAL_STATUSES,
    MAX_UPDATES_PER_INCIDENT,
)
from app.services.analysis_service import analysis_service
from app.services.memory_service import (
    MemoryService,
    MEMORY_STATUS_NOT_RECORDED,
    MEMORY_STATUS_ACCEPTED,
    MEMORY_STATUS_PENDING,
    MEMORY_STATUS_FAILED,
    memory_service,
)

logger = logging.getLogger(__name__)

_ANALYZE_ALLOWED_FROM = frozenset({IncidentStatus.REPORTED, IncidentStatus.INVESTIGATING})

_OUTCOME_TO_STATUS = {
    "successfully_resolved": IncidentStatus.RESOLVED,
    "partially_resolved": IncidentStatus.MITIGATED,
    "unresolved_escalated": IncidentStatus.ESCALATED,
}

# memory_retained is True when memory was accepted (sync or async/pending)
_RETAINED_STATUSES = frozenset({MEMORY_STATUS_ACCEPTED, MEMORY_STATUS_PENDING})


class IncidentService:
    def __init__(
        self,
        db_path=None,
        analysis_svc=None,
        memory_svc=None,
    ):
        self.analysis = analysis_svc or analysis_service
        self.memory: MemoryService = memory_svc or memory_service
        self.path = Path(db_path) if db_path else (
            Path(__file__).resolve().parents[2] / "data" / "incidents.sqlite3"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection context manager
    # ------------------------------------------------------------------

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema bootstrap & migration
    # ------------------------------------------------------------------

    def _init_schema(self):
        with self._db() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id         TEXT PRIMARY KEY,
                    payload    TEXT NOT NULL,
                    version    INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            existing = {row[1] for row in db.execute("PRAGMA table_info(incidents)").fetchall()}
            if "version" not in existing:
                db.execute("ALTER TABLE incidents ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
            if "created_at" not in existing:
                db.execute(
                    "ALTER TABLE incidents ADD COLUMN created_at TEXT NOT NULL "
                    "DEFAULT '1970-01-01T00:00:00.000000Z'"
                )
            if "updated_at" not in existing:
                db.execute(
                    "ALTER TABLE incidents ADD COLUMN updated_at TEXT NOT NULL "
                    "DEFAULT '1970-01-01T00:00:00.000000Z'"
                )

    # ------------------------------------------------------------------
    # Legacy seed import
    # ------------------------------------------------------------------

    def import_legacy_once(self):
        legacy = Path(__file__).resolve().parents[2] / "seed" / "legacy_incidents.json"
        if not legacy.exists():
            return
        with self._db() as db:
            if db.execute("SELECT value FROM meta WHERE key='legacy_imported'").fetchone():
                return
            records = json.loads(legacy.read_text(encoding="utf-8")).get("incidents", [])
            now = _utcnow()
            for record in records:
                try:
                    item = Incident(**record)
                except Exception as exc:
                    logger.warning(
                        "Skipping malformed legacy record %s: %s",
                        record.get("incident_id", "?"), exc,
                    )
                    continue
                db.execute(
                    "INSERT OR IGNORE INTO incidents (id, payload, version, created_at, updated_at) "
                    "VALUES (?, ?, 0, ?, ?)",
                    (item.incident_id, item.model_dump_json(), now, now),
                )
            db.execute("INSERT INTO meta (key, value) VALUES ('legacy_imported', '1')")

    # ------------------------------------------------------------------
    # Low-level persistence
    # ------------------------------------------------------------------

    def _save(self, incident: Incident, expected_version: int) -> Incident:
        now = _utcnow()
        payload = incident.model_dump_json()
        with self._db() as db:
            if expected_version == -1:
                db.execute(
                    "INSERT INTO incidents (id, payload, version, created_at, updated_at) "
                    "VALUES (?, ?, 0, ?, ?) ON CONFLICT(id) DO NOTHING",
                    (incident.incident_id, payload, now, now),
                )
                row = db.execute(
                    "SELECT version FROM incidents WHERE id=?", (incident.incident_id,)
                ).fetchone()
                if row is None:
                    raise ConflictError(
                        f"Insert of {incident.incident_id} was blocked by a concurrent write."
                    )
            else:
                cur = db.execute(
                    "UPDATE incidents SET payload=?, version=version+1, updated_at=? "
                    "WHERE id=? AND version=?",
                    (payload, now, incident.incident_id, expected_version),
                )
                if cur.rowcount == 0:
                    raise ConflictError(
                        f"Concurrent modification detected for {incident.incident_id} "
                        f"(expected version {expected_version})."
                    )
        return incident

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def _load_row(self, db, incident_id: str):
        row = db.execute(
            "SELECT payload, version FROM incidents WHERE id=?", (incident_id,)
        ).fetchone()
        if row is None:
            return None, None
        return Incident.model_validate_json(row["payload"]), row["version"]

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with self._db() as db:
            incident, _ = self._load_row(db, incident_id)
        return incident

    def _get_with_version(self, incident_id: str) -> Tuple[Optional[Incident], Optional[int]]:
        with self._db() as db:
            return self._load_row(db, incident_id)

    def list_incidents(self, limit: int = 200, offset: int = 0):
        with self._db() as db:
            rows = db.execute(
                "SELECT payload FROM incidents ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        results = []
        for row in rows:
            try:
                inc = Incident.model_validate_json(row["payload"])
                results.append(IncidentSummary(
                    incident_id=inc.incident_id,
                    title=inc.title,
                    service=inc.service,
                    environment=inc.environment,
                    severity=inc.severity,
                    status=inc.status,
                    timestamp=inc.timestamp,
                    resolved_at=inc.resolved_at,
                    memory_retained=inc.memory_retained,
                    outcome=inc.outcome,
                    updates=inc.updates,
                    tags=inc.tags,
                ))
            except Exception as exc:
                logger.warning("Skipping corrupted incident row: %s", exc)
        return results

    def require(self, incident_id: str) -> Incident:
        incident = self.get_incident(incident_id)
        if incident is None:
            raise NotFoundError(f"Incident {incident_id!r} not found")
        return incident

    def _require_with_version(self, incident_id: str):
        incident, version = self._get_with_version(incident_id)
        if incident is None:
            raise NotFoundError(f"Incident {incident_id!r} not found")
        return incident, version

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def _find_by_client_request_id(self, client_request_id: str) -> Optional[Incident]:
        with self._db() as db:
            row = db.execute(
                "SELECT payload FROM incidents "
                "WHERE json_extract(payload, '$.client_request_id') = ?",
                (client_request_id,),
            ).fetchone()
        if row is None:
            return None
        return Incident.model_validate_json(row["payload"])

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create_incident(self, incident_data: IncidentCreate) -> Incident:
        if incident_data.client_request_id:
            existing = self._find_by_client_request_id(incident_data.client_request_id)
            if existing is not None:
                return existing
        incident = Incident(
            incident_id="INC-" + uuid4().hex[:8].upper(),
            **incident_data.model_dump(),
        )
        self._save(incident, expected_version=-1)
        return incident

    def analyze_incident(self, incident_id: str, use_memory: bool = True):
        pre, _ = self._require_with_version(incident_id)
        if pre.status not in _ANALYZE_ALLOWED_FROM:
            raise ValueError(
                f"Cannot analyze incident in status {pre.status.value!r}. "
                f"Only {[s.value for s in _ANALYZE_ALLOWED_FROM]} are allowed."
            )
        analysis = self.analysis.analyze_incident(pre.model_dump(mode="json"), use_memory)
        fresh, ver = self._require_with_version(incident_id)
        fresh.analysis = analysis.model_dump(mode="json")
        if fresh.status in _ANALYZE_ALLOWED_FROM:
            fresh.status = IncidentStatus.INVESTIGATING
        self._save(fresh, ver)
        return analysis

    def resolve_incident(self, incident_id: str, resolution: ResolutionRequest) -> Incident:
        incident, ver = self._require_with_version(incident_id)
        for name, value in resolution.model_dump().items():
            if name in Incident.model_fields:
                setattr(incident, name, value)
        incident.status = _OUTCOME_TO_STATUS[resolution.outcome]
        incident.resolved_at = (
            datetime.now(timezone.utc) if incident.status == IncidentStatus.RESOLVED else None
        )
        incident.memory_retained = False
        self._save(incident, ver)

        # ---- SLOW CALL ----
        mem_status = self.memory.retain_resolved_incident(
            incident.model_dump(mode="json"), resolution.model_dump(mode="json")
        )
        # -------------------

        fresh, ver2 = self._require_with_version(incident_id)
        fresh.memory_retained = mem_status in _RETAINED_STATUSES
        self._save(fresh, ver2)
        return fresh

    def add_update(self, incident_id: str, update: IncidentUpdate) -> Incident:
        incident, ver = self._require_with_version(incident_id)
        if incident.status in TERMINAL_STATUSES and not update.reopen:
            raise ValueError(
                f"Incident {incident_id} is {incident.status.value!r}. "
                f"Pass reopen=true to add an update and reopen it."
            )
        if len(incident.updates) >= MAX_UPDATES_PER_INCIDENT:
            raise ValueError(
                f"Incident {incident_id} has reached the maximum of "
                f"{MAX_UPDATES_PER_INCIDENT} updates."
            )
        if update.reopen and incident.status in TERMINAL_STATUSES:
            incident.outcome = None
            incident.resolution = None
            incident.resolved_at = None
        incident.updates.append({
            "note": update.note,
            "kind": update.kind,
            "timestamp": _utcnow(),
        })
        incident.memory_retained = False
        incident.status = IncidentStatus.INVESTIGATING
        incident.analysis = None
        self._save(incident, ver)
        return self.retry_memory(incident_id)

    def retry_memory(self, incident_id: str) -> Incident:
        incident, ver = self._require_with_version(incident_id)
        if not incident.updates and not incident.outcome:
            raise ValueError("Record evidence or an outcome before saving memory")
        incident.memory_retained = False
        self._save(incident, ver)

        # ---- SLOW CALL — never raises; failures become memory_status=failed ----
        try:
            mem_status = self.memory.retain_incident(incident.model_dump(mode="json"))
        except Exception:
            logger.exception(
                "retain_incident raised unexpectedly for %s", incident_id
            )
            mem_status = MEMORY_STATUS_FAILED
        # -----------------------------------------------------------------------

        fresh, ver2 = self._require_with_version(incident_id)
        fresh.memory_retained = mem_status in _RETAINED_STATUSES
        self._save(fresh, ver2)
        return fresh

    def get_incident_memories(self, incident_id: str):
        item = self.require(incident_id)
        memories = self.memory.recall_similar_incidents(
            item.service, item.environment.value, item.symptoms
        )
        return {"incident_id": incident_id, "memories": memories, "count": len(memories)}

    def compare_analysis(self, incident_data: IncidentCreate):
        incident = {"incident_id": "COMPARISON", **incident_data.model_dump(mode="json")}
        return self.analysis.compare_analysis(incident)

    def delete_incident(self, incident_id: str) -> Dict[str, object]:
        """Delete the local incident record and attempt to delete the remote memory.

        Returns:
            {'deleted': True, 'memory_deleted': bool, 'memory_note': str}
        """
        with self._db() as db:
            cur = db.execute("DELETE FROM incidents WHERE id=?", (incident_id,))
        if cur.rowcount == 0:
            raise NotFoundError(f"Incident {incident_id!r} not found")

        # Best-effort remote delete — never raises; failure is surfaced to caller.
        memory_deleted = self.memory.delete_incident_memory(incident_id)
        memory_note = (
            "Memory document deleted."
            if memory_deleted
            else "Local record deleted. Remote memory document could not be deleted; "
                 "it will expire or can be removed manually."
        )
        return {"deleted": True, "memory_deleted": memory_deleted, "memory_note": memory_note}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
