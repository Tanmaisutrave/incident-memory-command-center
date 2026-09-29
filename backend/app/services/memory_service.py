"""Memory service — incident serialisation, retain/recall, redaction and stats.

Key design decisions
--------------------
* ``build_incident_memory_document(incident)`` is the **single serialiser** used
  for both resolve-retain and retry-retain.  The document_id is always the
  incident_id, so a re-retain is a replace (``update_mode="replace"``).

* Never retain the raw JSON dump.  The document is a human-readable, labelled
  text block that clearly marks unresolved/unverified content.

* Retain result is the explicit dict ``{'accepted', 'async', 'operation_id'}``
  returned by HindsightClient.  We map it to a ``MemoryStatus`` string:
      not_recorded  – not attempted
      pending       – accepted async (queued)
      accepted      – accepted sync
      failed        – SDK returned success=False or raised

* Environment contamination control:
  - Staging/development incidents are not retained unless
    ``settings.retain_non_production`` is True.
  - Recall passes the incident's environment to HindsightClient.recall()
    which applies native SDK tag filtering plus post-filtering.

* Tags on retain: ``env:<env>``, ``svc:<service>``, ``status:<status>``,
  ``outcome:<outcome>`` — these enable server-side filtering in recall.

* Redaction: when ``settings.memory_redaction`` is True, content and metadata
  values are redacted before being sent to the provider or the LLM.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings
from app.hindsight_client import (
    HindsightClient,
    _TAG_ENV_PREFIX,
    _TAG_OUTCOME_PREFIX,
    _TAG_STATUS_PREFIX,
    _TAG_SVC_PREFIX,
    hindsight_client,
)
from app.prompts import build_memory_query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Memory status values stored on the Incident
# ---------------------------------------------------------------------------
MEMORY_STATUS_NOT_RECORDED = "not_recorded"
MEMORY_STATUS_PENDING = "pending"       # accepted async / queued
MEMORY_STATUS_ACCEPTED = "accepted"     # accepted sync
MEMORY_STATUS_FAILED = "failed"


# ---------------------------------------------------------------------------
# Single document serialiser
# ---------------------------------------------------------------------------

def build_incident_memory_document(incident: Dict[str, Any]) -> str:
    """Build the canonical human-readable document for a given incident dict.

    This is the **only** function that produces the text stored in Hindsight.
    Both ``retain_resolved_incident`` and ``retry_retain`` use it, so the
    document structure is always identical for the same ``document_id``.

    Unresolved or unverified content is explicitly labelled.
    """
    iid = incident.get("incident_id", "?")
    status = incident.get("status", "unknown")
    outcome = incident.get("outcome")
    is_resolved = status in ("resolved", "mitigated", "escalated", "closed")

    lines: List[str] = [
        f"INCIDENT RECORD: {iid}",
        f"Title: {incident.get('title', 'N/A')}",
        f"Service: {incident.get('service', 'N/A')}",
        f"Environment: {incident.get('environment', 'N/A')}",
        f"Severity: {incident.get('severity', 'N/A')}",
        f"Status: {status}",
    ]

    if outcome:
        lines.append(f"Outcome: {outcome}")
    else:
        lines.append("Outcome: NOT YET RECORDED")

    lines.append(f"Reported at: {incident.get('timestamp', 'N/A')}")

    if incident.get("resolved_at"):
        lines.append(f"Resolved at: {incident['resolved_at']}")

    # Symptoms — always present; label unverified when unresolved
    lines.append("")
    label = "SYMPTOMS" if is_resolved else "REPORTED SYMPTOMS (NOT VERIFIED)"
    lines.append(f"{label}:")
    lines.append(incident.get("symptoms", "N/A"))

    # Error logs — optional
    if incident.get("error_logs"):
        lines.append("")
        lines.append("ERROR LOGS (excerpt):")
        lines.append(str(incident["error_logs"])[:500])

    # Suspected causes — labelled as reported
    if incident.get("suspected_causes"):
        lines.append("")
        lines.append("REPORTED SUSPECTED CAUSES (not confirmed):")
        for c in incident["suspected_causes"]:
            lines.append(f"  - {c}")

    # Root cause / resolution — only if actually recorded
    if incident.get("root_cause"):
        lines.append("")
        confirmed = "CONFIRMED ROOT CAUSE" if is_resolved else "ROOT CAUSE (REPORTED, NOT VERIFIED)"
        lines.append(f"{confirmed}:")
        lines.append(incident["root_cause"])

    if incident.get("actions_taken"):
        lines.append("")
        lines.append("ACTIONS TAKEN:")
        for a in incident["actions_taken"]:
            lines.append(f"  - {a}")

    if incident.get("resolution"):
        lines.append("")
        label = "RESOLUTION" if is_resolved else "RESOLUTION (REPORTED, NOT VERIFIED)"
        lines.append(f"{label}:")
        lines.append(incident["resolution"])

    if incident.get("lessons_learned"):
        lines.append("")
        lines.append("LESSONS LEARNED:")
        lines.append(incident["lessons_learned"])

    if incident.get("preventive_actions"):
        lines.append("")
        lines.append("PREVENTIVE ACTIONS:")
        for a in incident["preventive_actions"]:
            lines.append(f"  - {a}")

    # Updates — human-reported evidence; always labelled
    updates = incident.get("updates") or []
    if updates:
        lines.append("")
        lines.append("INVESTIGATION UPDATES (human-reported, not verified by this system):")
        for u in updates:
            kind = u.get("kind", "evidence")
            ts = u.get("timestamp", "")
            note = u.get("note", "")
            lines.append(f"  [{kind.upper()} @ {ts}] {note}")

    if not is_resolved:
        lines.append("")
        lines.append("NOTE: This incident is not yet resolved. "
                      "The above content reflects the state at the time of retain.")

    return "\n".join(lines)


def _retain_tags(incident: Dict[str, Any]) -> List[str]:
    """Build the tag list for a retained document."""
    tags = [
        f"{_TAG_ENV_PREFIX}{incident.get('environment', 'unknown')}",
        f"{_TAG_SVC_PREFIX}{incident.get('service', 'unknown')}",
        f"{_TAG_STATUS_PREFIX}{incident.get('status', 'unknown')}",
    ]
    if incident.get("outcome"):
        tags.append(f"{_TAG_OUTCOME_PREFIX}{incident['outcome']}")
    return tags


def _retain_metadata(incident: Dict[str, Any]) -> Dict[str, str]:
    """Build the metadata dict for a retained document."""
    return {
        "incident_id": str(incident.get("incident_id", "")),
        "service": str(incident.get("service", "")),
        "environment": str(incident.get("environment", "")),
        "severity": str(incident.get("severity", "")),
        "status": str(incident.get("status", "")),
        "outcome": str(incident.get("outcome") or ""),
    }


def _interpret_retain_result(result: Dict[str, Any]) -> str:
    """Map HindsightClient.retain() dict to a MemoryStatus string."""
    if not result.get("accepted"):
        return MEMORY_STATUS_FAILED
    if result.get("async"):
        return MEMORY_STATUS_PENDING
    return MEMORY_STATUS_ACCEPTED


# ---------------------------------------------------------------------------
# MemoryService
# ---------------------------------------------------------------------------


class MemoryService:
    def __init__(self, hindsight: Optional[HindsightClient] = None) -> None:
        self.hindsight: HindsightClient = hindsight or hindsight_client
        self.retain_count = 0
        self.recall_count = 0
        self.last_retain: Optional[datetime] = None
        self.last_recall: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------

    def recall_similar_incidents(
        self,
        service: str,
        environment: str,
        symptoms: str,
        error_logs: Optional[str] = None,
        suspected_causes: Optional[List[str]] = None,
        updates: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        budget: str = "mid",
    ) -> List[Dict[str, Any]]:
        """Recall similar historical incidents from Hindsight."""
        query = build_memory_query(
            service=service,
            environment=environment,
            symptoms=symptoms,
            error_logs=error_logs,
            suspected_causes=suspected_causes,
            updates=updates,
        )

        logger.info(
            "Recalling memories: service=%r env=%r symptoms_len=%d logs_len=%d",
            service, environment, len(symptoms or ""), len(error_logs or ""),
        )

        # Redact query if enabled (belt-and-braces in case symptoms contain PII)
        if settings.memory_redaction:
            from app.redaction import redact
            query, n = redact(query)
            if n:
                logger.info("Redacted %d item(s) from recall query", n)

        memories = self.hindsight.recall(
            query=query,
            max_tokens=max_tokens,
            budget=budget,
            environment=environment if settings.recall_same_env_only else None,
        )

        self.recall_count += 1
        self.last_recall = datetime.utcnow()
        logger.info("Recalled %d memories", len(memories))
        return memories

    # ------------------------------------------------------------------
    # Retain (both paths use the single serialiser)
    # ------------------------------------------------------------------

    def retain_resolved_incident(
        self,
        incident: Dict[str, Any],
        resolution: Dict[str, Any],
    ) -> str:
        """Retain a resolved incident.  Returns a MemoryStatus string."""
        env = incident.get("environment", "production")

        # Contamination control
        if env != "production" and not settings.retain_non_production:
            logger.info(
                "Skipping retain for non-production incident %s (env=%s). "
                "Set RETAIN_NON_PRODUCTION=true to allow.",
                incident.get("incident_id"), env,
            )
            return MEMORY_STATUS_NOT_RECORDED

        # Merge resolution fields into incident snapshot for the document
        snapshot = dict(incident)
        for field in ("root_cause", "resolution", "actions_taken", "outcome",
                      "lessons_learned", "preventive_actions", "downtime",
                      "affected_users"):
            if field in resolution:
                snapshot[field] = resolution[field]

        return self._do_retain(snapshot)

    def retain_incident(self, incident: Dict[str, Any]) -> str:
        """Retain an in-progress or partially-resolved incident.

        Used by retry_memory / add_update paths.  Returns a MemoryStatus string.
        """
        env = incident.get("environment", "production")
        if env != "production" and not settings.retain_non_production:
            logger.info(
                "Skipping retain for non-production incident %s (env=%s).",
                incident.get("incident_id"), env,
            )
            return MEMORY_STATUS_NOT_RECORDED

        return self._do_retain(incident)

    def _do_retain(self, incident: Dict[str, Any]) -> str:
        """Internal: build document, redact if configured, and retain."""
        iid = incident.get("incident_id", "?")
        content = build_incident_memory_document(incident)

        if settings.memory_redaction:
            from app.redaction import redact, redact_dict_values
            content, n = redact(content)
            if n:
                logger.info("Redacted %d item(s) from retain content for %s", n, iid)

        metadata = _retain_metadata(incident)
        tags = _retain_tags(incident)
        context = (
            f"Incident {iid} — {incident.get('service')} "
            f"({incident.get('environment')}) status={incident.get('status')}"
        )

        logger.info("Retaining incident %s to memory (status=%s)", iid, incident.get("status"))

        try:
            result = self.hindsight.retain(
                content=content,
                metadata=metadata,
                context=context,
                document_id=iid,
                tags=tags,
                update_mode="replace",
            )
        except Exception as exc:
            logger.error(
                "Retain failed for %s [type=%s]", iid, type(exc).__name__
            )
            return MEMORY_STATUS_FAILED

        status = _interpret_retain_result(result)
        logger.info(
            "Retain result for %s: status=%s operation_id=%s",
            iid, status, result.get("operation_id"),
        )

        if status in (MEMORY_STATUS_ACCEPTED, MEMORY_STATUS_PENDING):
            self.retain_count += 1
            self.last_retain = datetime.utcnow()

        return status

    # ------------------------------------------------------------------
    # Delete memory
    # ------------------------------------------------------------------

    def delete_incident_memory(self, incident_id: str) -> bool:
        """Delete the memory document for *incident_id* from Hindsight.

        Returns True on success, False if the remote delete failed (the local
        incident record is deleted regardless — caller decides how to surface
        the failure).
        """
        logger.info("Deleting memory document for incident %s", incident_id)
        return self.hindsight.delete_document(incident_id)

    # ------------------------------------------------------------------
    # Reflect
    # ------------------------------------------------------------------

    def reflect_on_patterns(self, query: str, budget: str = "mid") -> str:
        logger.info("Reflecting on patterns: query_len=%d", len(query))
        if settings.memory_redaction:
            from app.redaction import redact
            query, n = redact(query)
            if n:
                logger.info("Redacted %d item(s) from reflect query", n)
        reflection = self.hindsight.reflect(
            query=query,
            budget=budget,
            context="Pattern discovery across historical incidents",
        )
        logger.info("Completed reflection")
        return reflection

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        return {
            "bank_id": self.hindsight.bank_id,
            "total_recalls": self.recall_count,
            "total_retains": self.retain_count,
            "last_retain": self.last_retain.isoformat() if self.last_retain else None,
            "last_recall": self.last_recall.isoformat() if self.last_recall else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_category(self, root_cause: str) -> str:
        rc = root_cause.lower()
        if any(t in rc for t in ("redis", "cache", "memcache")):
            return "cache"
        if any(t in rc for t in ("database", "postgres", "mysql", "db", "sql")):
            return "database"
        if any(t in rc for t in ("network", "timeout", "latency", "connection")):
            return "network"
        if any(t in rc for t in ("memory", "oom", "heap")):
            return "memory"
        if any(t in rc for t in ("cpu", "compute")):
            return "cpu"
        if any(t in rc for t in ("disk", "storage")):
            return "storage"
        if any(t in rc for t in ("kubernetes", "k8s", "pod", "container")):
            return "kubernetes"
        if any(t in rc for t in ("config", "configuration")):
            return "configuration"
        return "other"


# Module-level singleton
memory_service = MemoryService()
