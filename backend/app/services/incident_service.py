"""Service for managing incidents."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json
import os

from app.schemas import (
    Incident, IncidentCreate, IncidentStatus,
    ResolutionRequest, AnalysisResponse
)
from app.services.analysis_service import analysis_service
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)


class IncidentService:
    """Service for incident lifecycle management."""
    
    def __init__(self):
        """Initialize incident service."""
        self.analysis = analysis_service
        self.memory = memory_service
        self.incidents: Dict[str, Incident] = {}
        self.incident_counter = 1000
        
        # Load existing incidents if storage exists
        self._load_incidents()
    
    def create_incident(self, incident_data: IncidentCreate) -> Incident:
        """
        Create a new incident.
        
        Args:
            incident_data: Incident creation data
            
        Returns:
            Created incident
        """
        # Generate incident ID
        self.incident_counter += 1
        incident_id = f"INC-{self.incident_counter}"
        
        # Create incident
        incident = Incident(
            incident_id=incident_id,
            title=incident_data.title,
            service=incident_data.service,
            environment=incident_data.environment,
            severity=incident_data.severity,
            status=IncidentStatus.REPORTED,
            symptoms=incident_data.symptoms,
            error_logs=incident_data.error_logs,
            metrics=incident_data.metrics,
            suspected_causes=incident_data.suspected_causes,
            tags=incident_data.tags,
            timestamp=datetime.utcnow()
        )
        
        # Store incident
        self.incidents[incident_id] = incident
        self._save_incidents()
        
        logger.info(f"Created incident {incident_id}")
        return incident
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """
        Get an incident by ID.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            Incident or None
        """
        return self.incidents.get(incident_id)
    
    def analyze_incident(
        self,
        incident_id: str,
        use_memory: bool = True
    ) -> AnalysisResponse:
        """
        Analyze an incident.
        
        Args:
            incident_id: Incident ID
            use_memory: Whether to use historical memory
            
        Returns:
            Analysis response
        """
        incident = self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        
        # Update status
        incident.status = IncidentStatus.INVESTIGATING
        self._save_incidents()
        
        # Convert to dict for analysis
        incident_dict = incident.model_dump()
        
        # Analyze
        analysis = self.analysis.analyze_incident(
            incident=incident_dict,
            use_memory=use_memory
        )
        
        # Update status
        incident.status = IncidentStatus.DIAGNOSED
        self._save_incidents()
        
        return analysis
    
    def resolve_incident(
        self,
        incident_id: str,
        resolution: ResolutionRequest
    ) -> Incident:
        """
        Resolve an incident and retain to memory.
        
        Args:
            incident_id: Incident ID
            resolution: Resolution details
            
        Returns:
            Updated incident
        """
        incident = self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        
        # Update incident with resolution
        incident.status = IncidentStatus.RESOLVED
        incident.root_cause = resolution.root_cause
        incident.actions_taken = resolution.actions_taken
        incident.resolution = resolution.resolution
        incident.outcome = resolution.outcome
        incident.before_metrics = resolution.before_metrics
        incident.after_metrics = resolution.after_metrics
        incident.downtime = resolution.downtime
        incident.affected_users = resolution.affected_users
        incident.lessons_learned = resolution.lessons_learned
        incident.resolved_at = datetime.utcnow()
        
        # Save incident
        self._save_incidents()
        
        # Retain to Hindsight memory
        incident_dict = incident.model_dump()
        resolution_dict = resolution.model_dump()
        
        self.memory.retain_resolved_incident(
            incident=incident_dict,
            resolution=resolution_dict
        )
        
        logger.info(f"Resolved incident {incident_id} and retained to memory")
        return incident
    
    def get_incident_memories(self, incident_id: str) -> Dict[str, Any]:
        """
        Get memories related to an incident.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            Memory information
        """
        incident = self.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        
        # Recall similar incidents
        memories = self.memory.recall_similar_incidents(
            service=incident.service,
            environment=incident.environment.value,
            symptoms=incident.symptoms,
            error_logs=incident.error_logs,
            max_tokens=4096,
            budget="mid"
        )
        
        return {
            "incident_id": incident_id,
            "memories": memories,
            "count": len(memories)
        }
    
    def compare_analysis(
        self,
        incident_data: IncidentCreate
    ) -> Dict[str, AnalysisResponse]:
        """
        Compare analysis with and without memory.
        
        Args:
            incident_data: Incident data
            
        Returns:
            Dictionary with 'without_memory' and 'with_memory' analyses
        """
        # Create temporary incident
        incident = self.create_incident(incident_data)
        
        try:
            # Analyze without memory
            analysis_without = self.analyze_incident(
                incident_id=incident.incident_id,
                use_memory=False
            )
            
            # Analyze with memory
            analysis_with = self.analyze_incident(
                incident_id=incident.incident_id,
                use_memory=True
            )
            
            return {
                "incident_id": incident.incident_id,
                "without_memory": analysis_without,
                "with_memory": analysis_with
            }
            
        finally:
            # Clean up temporary incident
            self.incidents.pop(incident.incident_id, None)
            self._save_incidents()
    
    def _load_incidents(self):
        """Load incidents from storage."""
        storage_path = "backend/data/incidents/incidents.json"
        if os.path.exists(storage_path):
            try:
                with open(storage_path, 'r') as f:
                    data = json.load(f)
                    for incident_data in data.get('incidents', []):
                        incident = Incident(**incident_data)
                        self.incidents[incident.incident_id] = incident
                    self.incident_counter = data.get('counter', 1000)
                logger.info(f"Loaded {len(self.incidents)} incidents from storage")
            except Exception as e:
                logger.error(f"Failed to load incidents: {e}")
    
    def _save_incidents(self):
        """Save incidents to storage."""
        storage_path = "backend/data/incidents/incidents.json"
        try:
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            
            data = {
                'counter': self.incident_counter,
                'incidents': [
                    incident.model_dump(mode='json')
                    for incident in self.incidents.values()
                ]
            }
            
            with open(storage_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to save incidents: {e}")


# Global incident service instance
incident_service = IncidentService()
