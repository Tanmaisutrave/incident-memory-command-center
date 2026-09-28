"""Hindsight memory client for storing and retrieving incident memories."""

import logging
import atexit
from typing import List, Dict, Any, Optional
from datetime import datetime

from hindsight_client import Hindsight
from app.config import settings

logger = logging.getLogger(__name__)


class HindsightClient:
    """Client for interacting with Hindsight memory system."""
    
    def __init__(self):
        """Initialize Hindsight client with API credentials."""
        # Initialize client with Cloud or self-hosted URL
        if settings.hindsight_api_key:
            self.client = Hindsight(
                base_url=settings.hindsight_base_url,
                api_key=settings.hindsight_api_key
            )
        else:
            self.client = Hindsight(
                base_url=settings.hindsight_base_url
            )
        self.bank_id = settings.hindsight_bank_id
        logger.info(f"Initialized Hindsight client for bank: {self.bank_id}")
        
        # Register cleanup on exit
        atexit.register(self.close)
    
    def close(self):
        """Close the Hindsight client and cleanup resources."""
        try:
            if hasattr(self.client, 'close'):
                self.client.close()
            elif hasattr(self.client, 'aclose'):
                # For async clients, we can't await here, but we can try to close
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.client.aclose())
                    else:
                        loop.run_until_complete(self.client.aclose())
                except Exception:
                    pass
            logger.info("Closed Hindsight client")
        except Exception as e:
            logger.debug(f"Error closing Hindsight client: {e}")
    
    def retain(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store a memory in Hindsight.
        
        Args:
            content: The memory content to store
            metadata: Optional metadata to attach to the memory
            context: Optional context string
            
        Returns:
            Response dict with memory information
        """
        try:
            result = self.client.retain(
                bank_id=self.bank_id,
                content=content,
                metadata=metadata or {},
                context=context
            )
            logger.info(f"Retained memory successfully")
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Failed to retain memory: {e}")
            raise
    
    def recall(
        self,
        query: str,
        max_tokens: int = 4096,
        budget: str = "mid"
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories from Hindsight.
        
        Args:
            query: Search query for finding relevant memories
            max_tokens: Maximum tokens for context
            budget: Budget level (low, mid, high)
            
        Returns:
            List of relevant memory results
        """
        try:
            response = self.client.recall(
                bank_id=self.bank_id,
                query=query,
                max_tokens=max_tokens,
                budget=budget
            )
            # Extract results from response
            memories = response.results if hasattr(response, 'results') else []
            logger.info(f"Recalled {len(memories)} memories for query: {query[:50]}...")
            return [{"text": m.text, "type": m.type} for m in memories]
        except Exception as e:
            logger.error(f"Failed to recall memories: {e}")
            raise
    
    def reflect(
        self,
        query: str,
        budget: str = "mid",
        context: Optional[str] = None
    ) -> str:
        """
        Perform reflection to discover patterns across memories.
        
        Args:
            query: The reflection query/prompt
            budget: Budget level (low, mid, high)
            context: Optional context string
            
        Returns:
            Reflection insights as text
        """
        try:
            response = self.client.reflect(
                bank_id=self.bank_id,
                query=query,
                budget=budget,
                context=context
            )
            # Extract text from response
            reflection_text = response.text if hasattr(response, 'text') else str(response)
            logger.info("Completed reflection analysis")
            return reflection_text
        except Exception as e:
            logger.error(f"Failed to reflect: {e}")
            raise
    
    def health_check(self) -> bool:
        """
        Check if Hindsight is accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            import requests
            # Use the official Hindsight health endpoint
            url = f"{settings.hindsight_base_url}/health/ready"
            headers = {"Authorization": f"Bearer {settings.hindsight_api_key}"}
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                logger.debug("Hindsight health check passed")
                return True
            else:
                logger.warning(f"Hindsight health check failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Hindsight health check failed: {type(e).__name__}: {e}")
            return False


# Global client instance
hindsight_client = HindsightClient()
