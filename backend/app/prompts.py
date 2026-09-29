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
        f"Symptoms: {symptoms}"
    ]
    
    if error_logs:
        # Extract key error patterns
        error_preview = error_logs[:200]
        query_parts.append(f"Errors: {error_preview}")
    
    if suspected_causes:
        query_parts.append(f"Possible causes: {', '.join(suspected_causes)}")
    
    return " | ".join(query_parts)


def build_analysis_prompt(
    incident: Dict[str, Any],
    historical_memories: List[Dict[str, Any]],
    use_memory: bool = True
) -> str:
    """
    Build the analysis prompt for the LLM.
    
    Args:
        incident: Current incident details
        historical_memories: Retrieved historical incidents
        use_memory: Whether to include memory context
        
    Returns:
        Complete analysis prompt
    """
    if use_memory and historical_memories:
        return _build_memory_informed_prompt(incident, historical_memories)
    else:
        return _build_generic_prompt(incident)


def _build_generic_prompt(incident: Dict[str, Any]) -> str:
    """Build a generic analysis prompt without historical context."""
    return f"""You are an expert DevOps/SRE engineer analyzing a production incident.

INCIDENT DETAILS:
- Service: {incident.get('service')}
- Environment: {incident.get('environment')}
- Severity: {incident.get('severity')}
- Symptoms: {incident.get('symptoms')}
{f"- Error Logs: {incident.get('error_logs')}" if incident.get('error_logs') else ""}
{f"- Metrics: {incident.get('metrics')}" if incident.get('metrics') else ""}
{f"- Suspected Causes: {', '.join(incident.get('suspected_causes', []))}" if incident.get('suspected_causes') else ""}

Analyze this incident and provide:

1. **Root Cause Analysis**: What is the most likely root cause?
2. **Confidence Level**: How confident are you? (0.0 to 1.0)
3. **Investigation Steps**: Ordered list of investigation steps
4. **Recommended Actions**: Specific remediation actions
5. **Risk Notes**: Any risks or caveats

Provide a thorough, professional analysis based on DevOps/SRE best practices."""


def _build_memory_informed_prompt(
    incident: Dict[str, Any],
    historical_memories: List[Dict[str, Any]]
) -> str:
    """Build an analysis prompt with historical memory context."""
    
    # Format historical context
    memory_context = "\n\n".join([
        f"HISTORICAL INCIDENT {i+1}:\n{memory['text']}"
        for i, memory in enumerate(historical_memories[:5])  # Limit to top 5
    ])
    
    return f"""You are an expert DevOps/SRE engineer with access to historical incident data.

CURRENT INCIDENT:
- Service: {incident.get('service')}
- Environment: {incident.get('environment')}
- Severity: {incident.get('severity')}
- Symptoms: {incident.get('symptoms')}
{f"- Error Logs: {incident.get('error_logs')}" if incident.get('error_logs') else ""}
{f"- Metrics: {incident.get('metrics')}" if incident.get('metrics') else ""}
{f"- Suspected Causes: {', '.join(incident.get('suspected_causes', []))}" if incident.get('suspected_causes') else ""}

HISTORICAL INCIDENTS (Similar Past Cases):
{memory_context}

ANALYSIS INSTRUCTIONS:

1. **Compare with Historical Incidents**: Identify similarities and differences between the current incident and past incidents.

2. **Root Cause Analysis**: 
   - Consider what caused similar incidents historically
   - Identify if this appears to be the same pattern or a different root cause
   - DO NOT assume identical symptoms mean identical root causes

3. **Historical Evidence**:
   - What do previous incidents tell us?
   - What resolutions worked before?
   - What resolutions failed before?
   - What patterns are recurring?

4. **Confidence Level**: Based on historical data and current evidence (0.0 to 1.0)

5. **Investigation Steps**: 
   - Prioritize checks based on historical patterns
   - Include verification steps to distinguish between similar root causes

6. **Recommended Actions**:
   - Leverage successful resolutions from similar past incidents
   - Note any important differences that might require different approaches

7. **Memory Insights**:
   - Explicitly state which historical incidents informed your recommendation
   - Explain the relevance of past incidents to the current situation

Provide a thorough analysis that CLEARLY demonstrates how historical knowledge improves the diagnosis."""


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
        f"SYMPTOMS:",
        incident.get('symptoms', 'N/A'),
        ""
    ]
    
    if incident.get('error_logs'):
        content_parts.extend([
            "ERROR LOGS:",
            incident.get('error_logs')[:500],  # Limit length
            ""
        ])
    
    if incident.get('metrics'):
        content_parts.extend([
            f"METRICS: {incident.get('metrics')}",
            ""
        ])
    
    content_parts.extend([
        f"ROOT CAUSE:",
        resolution.get('root_cause', 'N/A'),
        "",
        "ACTIONS TAKEN:",
        "\n".join(f"- {action}" for action in resolution.get('actions_taken', [])),
        "",
        f"RESOLUTION:",
        resolution.get('resolution', 'N/A'),
        "",
        f"OUTCOME:",
        resolution.get('outcome', 'N/A'),
        ""
    ])
    
    if resolution.get('before_metrics') or resolution.get('after_metrics'):
        content_parts.extend([
            "IMPACT:",
            f"Before: {resolution.get('before_metrics', 'N/A')}",
            f"After: {resolution.get('after_metrics', 'N/A')}",
            ""
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
            ""
        ])
    
    if resolution.get('preventive_actions'):
        content_parts.extend([
            "PREVENTIVE ACTIONS:",
            "\n".join(f"- {action}" for action in resolution.get('preventive_actions', [])),
        ])
    
    content_parts.extend(["", "RECORDED UPDATES:", str(incident.get("updates", []))])
    return "\n".join(content_parts)


def build_reflection_query(
    service: Optional[str] = None,
    pattern_type: str = "general"
) -> str:
    """
    Build a reflection query for pattern discovery.
    
    Args:
        service: Optional service to focus on
        pattern_type: Type of pattern analysis (general, service, root_cause)
        
    Returns:
        Reflection query
    """
    if pattern_type == "service" and service:
        return f"""Analyze all incidents for the {service} service and identify:

1. Most common failure patterns
2. Recurring root causes
3. Most effective resolutions
4. Trends over time
5. Preventive recommendations

Provide a structured analysis with specific examples."""
    
    elif pattern_type == "root_cause":
        return """Analyze all incidents and identify:

1. Most frequent root causes across all services
2. Common symptom patterns for each root cause
3. Resolution strategies that work consistently
4. Services most affected by each root cause type

Group findings by root cause category (e.g., resource exhaustion, network issues, configuration errors)."""
    
    else:  # general
        return """Analyze all incidents in the memory bank and identify:

1. Recurring patterns across services
2. Most common types of incidents
3. Services with the most incidents
4. Resolution patterns that work consistently
5. Operational insights and trends
6. Preventive recommendations

Provide a comprehensive operational intelligence summary."""
