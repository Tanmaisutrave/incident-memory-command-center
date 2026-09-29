"""Prompt templates for incident analysis."""

from typing import List, Dict, Any, Optional


def build_memory_query(
    service: str,
    environment: str,
    symptoms: str,
    error_logs: Optional[str] = None,
    suspected_causes: Optional[List[str]] = None
) -> str:
    """
    Build a semantic query for Hindsight memory recall.

    Args:
        service: Service name
        environment: Environment (production, staging, etc.)
        symptoms: Incident symptoms
        error_logs: Optional error logs
        suspected_causes: Optional suspected causes

    Returns:
        Optimized semantic query string
    """
    query_parts = [
        f"Service: {service}",
        f"Environment: {environment}",
        f"Symptoms: {symptoms}",
    ]

    if error_logs:
        # Extract key error patterns
        error_preview = error_logs[:200]
        query_parts.append(f"Errors: {error_preview}")

    if suspected_causes:
        query_parts.append(f"Possible causes: {', '.join(suspected_causes)}")

    return " | ".join(query_parts)


def build_resolution_memory_content(
    incident: Dict[str, Any],
    resolution: Dict[str, Any]
) -> str:
    """
    Build memory content for a resolved incident.

    Args:
        incident: Incident details
        resolution: Resolution details

    Returns:
        Formatted memory content
    """
    content_parts = [
        f"INCIDENT: {incident.get('incident_id')} - {incident.get('title')}",
        f"Service: {incident.get('service')}",
        f"Environment: {incident.get('environment')}",
        f"Severity: {incident.get('severity')}",
        "",
        "SYMPTOMS:",
        incident.get('symptoms', 'N/A'),
        "",
    ]

    if incident.get('error_logs'):
        content_parts.extend([
            "ERROR LOGS:",
            incident.get('error_logs')[:500],  # Limit length
            "",
        ])

    if incident.get('metrics'):
        content_parts.extend([
            f"METRICS: {incident.get('metrics')}",
            "",
        ])

    content_parts.extend([
        "ROOT CAUSE:",
        resolution.get('root_cause', 'N/A'),
        "",
        "ACTIONS TAKEN:",
        "\n".join(f"- {action}" for action in resolution.get('actions_taken', [])),
        "",
        "RESOLUTION:",
        resolution.get('resolution', 'N/A'),
        "",
        "OUTCOME:",
        resolution.get('outcome', 'N/A'),
        "",
    ])

    if resolution.get('before_metrics') or resolution.get('after_metrics'):
        content_parts.extend([
            "IMPACT:",
            f"Before: {resolution.get('before_metrics', 'N/A')}",
            f"After: {resolution.get('after_metrics', 'N/A')}",
            "",
        ])

    if resolution.get('downtime'):
        content_parts.append(f"Downtime: {resolution.get('downtime')} minutes")

    if resolution.get('affected_users'):
        content_parts.append(f"Affected Users: {resolution.get('affected_users')}")

    if resolution.get('lessons_learned'):
        content_parts.extend([
            "",
            "LESSONS LEARNED:",
            resolution.get('lessons_learned'),
            "",
        ])

    if resolution.get('preventive_actions'):
        content_parts.extend([
            "PREVENTIVE ACTIONS:",
            "\n".join(f"- {action}" for action in resolution.get('preventive_actions', [])),
        ])

    content_parts.extend(["", "RECORDED UPDATES:", str(incident.get("updates", []))])
    return "\n".join(content_parts)
