"""Groq LLM client for incident analysis."""

import logging
from typing import Dict, Any, Optional
from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with Groq LLM."""
    
    def __init__(self):
        """Initialize Groq client."""
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        logger.info(f"Initialized Groq client with model: {self.model}")
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        try:
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            result = response.choices[0].message.content
            logger.info(f"Generated response ({len(result)} chars)")
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Provide helpful error messages
            if "401" in error_msg or "unauthorized" in error_msg:
                logger.error("Groq API authentication failed - check GROQ_API_KEY")
                raise Exception("Groq authentication failed. Please verify your GROQ_API_KEY is correct.")
            elif "404" in error_msg or "model_not_found" in error_msg:
                logger.error(f"Groq model not found: {self.model}")
                raise Exception(f"Groq model '{self.model}' does not exist or is not accessible. Please update GROQ_MODEL in your .env file.")
            elif "429" in error_msg or "rate_limit" in error_msg:
                logger.error("Groq rate limit exceeded")
                raise Exception("Groq rate limit exceeded. Please wait and try again.")
            else:
                logger.error(f"LLM generation failed: {e}")
                raise Exception(f"LLM generation failed: {str(e)}")
    
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.5,
        max_tokens: int = 2048
    ) -> str:
        """
        Generate a JSON response from the LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (lower for structured output)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated JSON string
        """
        json_instruction = "\n\nYou MUST respond with valid JSON only. No markdown, no code blocks, just pure JSON."
        
        full_prompt = prompt + json_instruction
        
        return self.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def health_check(self) -> bool:
        """
        Check if Groq API is accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "health check"}],
                max_tokens=10
            )
            logger.info(f"Groq health check passed for model: {self.model}")
            return bool(response.choices)
        except Exception as e:
            error_msg = str(e).lower()
            if "404" in error_msg or "model_not_found" in error_msg:
                logger.error(f"Groq model not available: {self.model}")
            elif "401" in error_msg or "unauthorized" in error_msg:
                logger.error("Groq authentication failed")
            else:
                logger.error(f"Groq health check failed: {e}")
            return False


# Global LLM client instance
llm_client = LLMClient()
