"""Service for managing incident memories in Hindsight."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.hindsight_client import hindsight_client
from app.prompts import build_memory_query, build_resolution_memory_content

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for incident memory operations."""
    
    def __init__(self):
        """Initialize memory service."""
        self.hindsight = hindsight_client
        self.retain_count = 0
        self.recall_count = 0
        self.last_retain = None
        self.last_recall = None
    
    def recall_similar_incidents(
        self,
        service: str,
        environment: str,
        symptoms: str,
        error_logs: Optional[str] = None,
        suspected_causes: Optional[List[str]] = None,
        updates: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        budget: str = "mid"
    ) -> List[Dict[str, Any]]:
        """
        Recall similar historical incidents from Hindsight.
        """
        try:
            # Build semantic query
            query = build_memory_query(
                service=service,
                environment=environment,
                symptoms=symptoms,
                error_logs=error_logs,
                suspected_causes=suspected_causes,
                updates=updates,
            )

            logger.info(
                "Recalling memories for service=%r env=%r symptoms_len=%d error_logs_len=%d",
                service, environment, len(symptoms or ""), len(error_logs or ""),
            )

            # Recall from Hindsight
            memories = self.hindsight.recall(
                query=query,
                max_tokens=max_tokens,
                budget=budget
            )

            # Update stats
            self.recall_count += 1
            self.last_recall = datetime.utcnow()

            logger.info("Recalled %d historical incidents", len(memories))
            return memories

        except Exception as e:
            logger.error("Failed to recall similar incidents [type=%s]", type(e).__name__)
            raise
    
    def retain_resolved_incident(
        self,
        incident: Dict[str, Any],
        resolution: Dict[str, Any]
    ) -> bool:
        """
        Store a resolved incident in Hindsight memory.
        
        Args:
            incident: Incident details
            resolution: Resolution details
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build memory content
            content = build_resolution_memory_content(incident, resolution)
            
            # Build metadata
            metadata = {
                "incident_id": incident.get("incident_id"),
                "service": incident.get("service"),
                "environment": incident.get("environment"),
                "severity": incident.get("severity"),
                "root_cause_category": self._extract_category(resolution.get("root_cause", "")),
                "resolved_at": datetime.utcnow().isoformat(),
                "tags": ",".join(incident.get("tags", [])) if incident.get("tags") else ""
            }
            
            # Build context
            context = f"Reported outcome {resolution.get('outcome')} for {incident.get('service')} in {incident.get('environment')}"
            
            logger.info("Retaining incident %s to memory", incident.get("incident_id"))
            
            # Retain to Hindsight
            result = self.hindsight.retain(
                content=content,
                metadata=metadata,
                context=context
            )
            
            # Update stats
            if result.get("success"):
                self.retain_count += 1
                self.last_retain = datetime.utcnow()
            
            logger.info("Successfully retained incident %s", incident.get("incident_id"))
            return result.get("success", False)
            
        except Exception as e:
            logger.error(f"Failed to retain incident: {e}")
            return False
    
    def reflect_on_patterns(
        self,
        query: str,
        budget: str = "mid"
    ) -> str:
        """
        Perform reflection to discover patterns across incidents.
        
        Args:
            query: Reflection query
            budget: Budget level
            
        Returns:
            Reflection insights
        """
        try:
            logger.info("Reflecting on patterns: query_len=%d", len(query))
            
            reflection = self.hindsight.reflect(
                query=query,
                budget=budget,
                context="Pattern discovery across historical incidents"
            )
            
            logger.info("Completed reflection analysis")
            return reflection
            
        except Exception as e:
            logger.error(f"Failed to reflect on patterns: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory service statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "bank_id": self.hindsight.bank_id,
            "total_recalls": self.recall_count,
            "total_retains": self.retain_count,
            "last_retain": self.last_retain.isoformat() if self.last_retain else None,
            "last_recall": self.last_recall.isoformat() if self.last_recall else None
        }
    
    def _extract_category(self, root_cause: str) -> str:
        """
        Extract a category from the root cause description.
        
        Args:
            root_cause: Root cause description
            
        Returns:
            Category string
        """
        root_cause_lower = root_cause.lower()
        
        if any(term in root_cause_lower for term in ["redis", "cache", "memcache"]):
            return "cache"
        elif any(term in root_cause_lower for term in ["database", "postgres", "mysql", "db", "sql"]):
            return "database"
        elif any(term in root_cause_lower for term in ["network", "timeout", "latency", "connection"]):
            return "network"
        elif any(term in root_cause_lower for term in ["memory", "oom", "heap"]):
            return "memory"
        elif any(term in root_cause_lower for term in ["cpu", "compute"]):
            return "cpu"
        elif any(term in root_cause_lower for term in ["disk", "storage"]):
            return "storage"
        elif any(term in root_cause_lower for term in ["kubernetes", "k8s", "pod", "container"]):
            return "kubernetes"
        elif any(term in root_cause_lower for term in ["config", "configuration"]):
            return "configuration"
        else:
            return "other"


# Global memory service instance
memory_service = MemoryService()
