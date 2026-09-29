"""Prompt-building helpers for incident analysis.

Key design decisions
--------------------
* build_memory_query – builds the Hindsight recall query from bounded slices of
  the incident fields so the query stays a compact semantic signal.

* build_llm_payload – assembles the full JSON payload sent to the model and
  enforces a total character budget (~24 k).  Oldest updates are dropped first,
  then logs are truncated.  A ``warnings`` entry is added whenever anything is
  trimmed so the caller can surface it in the response.

* Recalled memories are wrapped in clearly delimited objects with only
  {source_id, text, type} so the model cannot mistake them for instructions.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Recall-query limits
# ---------------------------------------------------------------------------
_SYMPTOMS_RECALL_MAX = 1500   # chars
_LOGS_RECALL_MAX = 300        # first N chars of error_logs
_UPDATES_RECALL_MAX = 3       # last N updates
_UPDATE_RECALL_CHARS = 300    # chars per update note

# ---------------------------------------------------------------------------
# LLM-payload budget
# ---------------------------------------------------------------------------
_LLM_BUDGET_CHARS = 24_000   # soft ceiling for the whole JSON payload
# Field slices (applied before budget check)
_SYMPTOMS_LLM_MAX = 6_000
_LOGS_LLM_MAX = 4_000
_UPDATE_LLM_CHARS = 600      # per update in the LLM payload
_UPDATES_LLM_MAX = 10        # start with up to 10 updates; drop oldest first


# ---------------------------------------------------------------------------
# build_memory_query
# ---------------------------------------------------------------------------


def build_memory_query(
    service: str,
    environment: str,
    symptoms: str,
    error_logs: Optional[str] = None,
    suspected_causes: Optional[List[str]] = None,
    updates: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Build a compact semantic query for Hindsight recall.

    Uses bounded slices so the query is a dense signal, not a dump of the
    full incident body.
    """
    parts: List[str] = [
        f"Service: {service}",
        f"Environment: {environment}",
        f"Symptoms: {symptoms[:_SYMPTOMS_RECALL_MAX]}",
    ]

    if error_logs:
        parts.append(f"Errors: {error_logs[:_LOGS_RECALL_MAX]}")

    if suspected_causes:
        parts.append(f"Possible causes: {', '.join(suspected_causes)}")

    if updates:
        recent = updates[-_UPDATES_RECALL_MAX:]
        notes = "; ".join(
            u.get("note", "")[:_UPDATE_RECALL_CHARS] for u in recent
        )
        if notes:
            parts.append(f"Recent updates: {notes}")

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# build_llm_payload
# ---------------------------------------------------------------------------


def build_llm_payload(
    incident: Dict[str, Any],
    memories: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """Assemble the JSON payload sent to the model and enforce a character budget.

    Returns:
        (payload_json, trim_warnings)  — trim_warnings is non-empty if any
        field was shortened to fit the budget.
    """
    trim_warnings: List[str] = []

    # ------------------------------------------------------------------
    # 1. Initial field slices (these are always applied)
    # ------------------------------------------------------------------
    symptoms = incident.get("symptoms") or ""
    if len(symptoms) > _SYMPTOMS_LLM_MAX:
        symptoms = symptoms[:_SYMPTOMS_LLM_MAX]
        trim_warnings.append(
            "Symptoms were truncated to fit the analysis budget "
            f"(kept first {_SYMPTOMS_LLM_MAX} chars)."
        )

    error_logs = incident.get("error_logs") or ""
    if len(error_logs) > _LOGS_LLM_MAX:
        error_logs = error_logs[:_LOGS_LLM_MAX]
        trim_warnings.append(
            "Error logs were truncated to fit the analysis budget "
            f"(kept first {_LOGS_LLM_MAX} chars)."
        )

    updates = list(incident.get("updates") or [])
    # Truncate individual update notes first
    for u in updates:
        note = u.get("note", "")
        if len(note) > _UPDATE_LLM_CHARS:
            u = dict(u)
            u["note"] = note[:_UPDATE_LLM_CHARS]

    # ------------------------------------------------------------------
    # 2. Wrap memories in clearly delimited objects (prompt injection guard)
    # ------------------------------------------------------------------
    safe_memories = [
        {
            "source_id": m.get("source_id", ""),
            "text": m.get("text", ""),
            "type": m.get("type", ""),
        }
        for m in memories
    ]

    # ------------------------------------------------------------------
    # 3. Budget loop: drop oldest updates until payload fits
    # ------------------------------------------------------------------
    def _assemble(upd: List[Dict[str, Any]]) -> Dict[str, Any]:
        inc_safe = {
            k: v
            for k, v in incident.items()
            if k not in ("analysis", "symptoms", "error_logs", "updates")
        }
        inc_safe["symptoms"] = symptoms
        if error_logs:
            inc_safe["error_logs"] = error_logs
        inc_safe["updates"] = upd
        return {"incident": inc_safe, "historical_sources": safe_memories}

    while True:
        payload = _assemble(updates)
        serialised = json.dumps(payload, default=str)
        if len(serialised) <= _LLM_BUDGET_CHARS or not updates:
            break
        dropped = updates.pop(0)
        trim_warnings.append(
            f"Update '{dropped.get('note', '')[:60]}…' was dropped to fit "
            "the analysis budget (oldest first)."
        )

    # One last check: if still over budget after dropping all updates,
    # truncate logs further
    if len(serialised) > _LLM_BUDGET_CHARS and error_logs:
        overage = len(serialised) - _LLM_BUDGET_CHARS
        error_logs = error_logs[: max(0, len(error_logs) - overage - 50)]
        trim_warnings.append("Error logs were further truncated to fit the analysis budget.")
        payload = _assemble(updates)
        serialised = json.dumps(payload, default=str)

    return serialised, trim_warnings


# ---------------------------------------------------------------------------
# Resolution memory content
# ---------------------------------------------------------------------------


def build_resolution_memory_content(
    incident: Dict[str, Any],
    resolution: Dict[str, Any],
) -> str:
    """Build memory content for a resolved incident."""
    parts: List[str] = [
        f"INCIDENT: {incident.get('incident_id')} - {incident.get('title')}",
        f"Service: {incident.get('service')}",
        f"Environment: {incident.get('environment')}",
        f"Severity: {incident.get('severity')}",
        "",
        "SYMPTOMS:",
        incident.get("symptoms", "N/A"),
        "",
    ]

    if incident.get("error_logs"):
        parts += ["ERROR LOGS:", incident["error_logs"][:500], ""]

    if incident.get("metrics"):
        parts += [f"METRICS: {incident.get('metrics')}", ""]

    parts += [
        "ROOT CAUSE:",
        resolution.get("root_cause", "N/A"),
        "",
        "ACTIONS TAKEN:",
        "\n".join(f"- {a}" for a in resolution.get("actions_taken", [])),
        "",
        "RESOLUTION:",
        resolution.get("resolution", "N/A"),
        "",
        "OUTCOME:",
        resolution.get("outcome", "N/A"),
        "",
    ]

    if resolution.get("before_metrics") or resolution.get("after_metrics"):
        parts += [
            "IMPACT:",
            f"Before: {resolution.get('before_metrics', 'N/A')}",
            f"After: {resolution.get('after_metrics', 'N/A')}",
            "",
        ]

    if resolution.get("downtime"):
        parts.append(f"Downtime: {resolution['downtime']} minutes")
    if resolution.get("affected_users"):
        parts.append(f"Affected Users: {resolution['affected_users']}")
    if resolution.get("lessons_learned"):
        parts += ["", "LESSONS LEARNED:", resolution["lessons_learned"], ""]
    if resolution.get("preventive_actions"):
        parts += [
            "PREVENTIVE ACTIONS:",
            "\n".join(f"- {a}" for a in resolution["preventive_actions"]),
        ]

    parts += ["", "RECORDED UPDATES:", str(incident.get("updates", []))]
    return "\n".join(parts)
