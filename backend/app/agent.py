"""
Core Incident Memory Agent.

This module provides the high-level agent orchestration that combines
Hindsight memory, LLM analysis, and incident management.
"""

import logging
from typing import Dict, Any, List, Optional

from app.services.incident_service import incident_service
from app.services.memory_service import memory_service
from app.services.analysis_service import analysis_service
from app.schemas import IncidentCreate, AnalysisResponse, ResolutionRequest

logger = logging.getLogger(__name__)


class IncidentMemoryAgent:
    """
    The core incident memory agent.
    
    This agent:
    1. Receives production incidents
    2. Recalls similar historical incidents from Hindsight
    3. Analyzes incidents using LLM with historical context
    4. Provides evidence-based recommendations
    5. Stores resolved incidents back to Hindsight
    6. Learns from each incident to improve future recommendations
    """
    
    def __init__(self):
        """Initialize the incident memory agent."""
        self.incident_service = incident_service
        self.memory_service = memory_service
        self.analysis_service = analysis_service
        logger.info("Incident Memory Agent initialized")
    
    def process_incident(
        self,
        incident_data: IncidentCreate,
        use_memory: bool = True
    ) -> Dict[str, Any]:
        """
        Process a new incident end-to-end.
        
        This is the main agent workflow:
        1. Create incident record
        2. Recall similar incidents from memory
        3. Analyze with historical context
        4. Return structured diagnosis
        
        Args:
            incident_data: New incident information
            use_memory: Whether to use Hindsight memory
            
        Returns:
            Dictionary with incident and analysis
        """
        logger.info(f"Processing new incident: {incident_data.title}")
        
        # Step 1: Create incident
        incident = self.incident_service.create_incident(incident_data)
        logger.info(f"Created incident {incident.incident_id}")
        
        # Step 2: Analyze incident
        analysis = self.incident_service.analyze_incident(
            incident_id=incident.incident_id,
            use_memory=use_memory
        )
        logger.info(f"Completed analysis for {incident.incident_id}")
        
        return {
            "incident": incident,
            "analysis": analysis,
            "memory_used": use_memory,
            "historical_incident_count": len(analysis.historical_incidents)
        }
    
    def resolve_and_learn(
        self,
        incident_id: str,
        resolution: ResolutionRequest
    ) -> Dict[str, Any]:
        """
        Resolve an incident and store it in memory.
        
        This completes the learning loop:
        1. Update incident with resolution
        2. Retain to Hindsight memory
        3. Make available for future incidents
        
        Args:
            incident_id: Incident identifier
            resolution: Resolution details
            
        Returns:
            Dictionary with resolution status
        """
        logger.info(f"Resolving and learning from {incident_id}")
        
        # Resolve incident (automatically retains to memory)
        incident = self.incident_service.resolve_incident(
            incident_id=incident_id,
            resolution=resolution
        )
        
        logger.info(f"Incident {incident_id} resolved and retained to memory")
        
        return {
            "incident_id": incident_id,
            "status": incident.status.value,
            "memory_retained": incident.memory_retained,
            "message": "Outcome recorded; memory saved" if incident.memory_retained else "Outcome recorded; memory save needs retry"
        }
    
    def demonstrate_learning(
        self,
        incident_data: IncidentCreate
    ) -> Dict[str, Any]:
        """
        Demonstrate the agent's learning by comparing with/without memory.
        
        This shows the value of Hindsight:
        - Without memory: Generic recommendations
        - With memory: Evidence-based recommendations from past incidents
        
        Args:
            incident_data: Incident to analyze
            
        Returns:
            Comparison of both analyses
        """
        logger.info("Demonstrating learning capability")
        
        comparison = self.incident_service.compare_analysis(incident_data)
        
        # Add interpretation
        memory_count = len(comparison['with_memory'].historical_incidents)
        
        comparison['demonstration'] = {
            "memory_enabled": memory_count > 0,
            "historical_incidents_used": memory_count,
            "value_proposition": (
                f"With Hindsight memory, the agent recalled {memory_count} similar "
                f"historical incidents to inform its recommendations. Without memory, "
                f"it provides only generic troubleshooting advice."
            )
        }
        
        return comparison
    
    def reflect_on_patterns(
        self,
        focus: Optional[str] = None
    ) -> str:
        """
        Reflect on patterns across all historical incidents.
        
        Uses Hindsight REFLECT to discover:
        - Recurring failure patterns
        - Common root causes
        - Effective resolutions
        - Operational insights
        
        Args:
            focus: Optional focus area (service, root cause type, etc.)
            
        Returns:
            Pattern analysis insights
        """
        logger.info(f"Reflecting on incident patterns (focus: {focus or 'general'})")
        
        from app.prompts import build_reflection_query
        
        query = build_reflection_query(
            service=focus if focus else None,
            pattern_type="service" if focus else "general"
        )
        
        reflection = self.memory_service.reflect_on_patterns(
            query=query,
            budget="high"  # Use high budget for comprehensive analysis
        )
        
        logger.info("Completed pattern reflection")
        return reflection
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the agent's learning.
        
        Returns:
            Statistics about memory usage and learning
        """
        stats = self.memory_service.get_stats()
        
        return {
            "memory_bank": stats['bank_id'],
            "total_recalls": stats['total_recalls'],
            "total_incidents_retained": stats['total_retains'],
            "last_recall": stats.get('last_recall'),
            "last_learning": stats.get('last_retain'),
            "status": "Agent is learning from every resolved incident"
        }


# Global agent instance
agent = IncidentMemoryAgent()
