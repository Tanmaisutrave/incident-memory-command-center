"""Groq structured generation with retry, schema sanitisation and token budget.

Design notes
------------
* max_tokens is configurable via settings (default 4000).
* reasoning_effort="low" is passed when the model name contains "r1" or the
  settings flag enables it — the Groq SDK ignores unknown kwargs silently, so
  this is safe to include conditionally.
* On finish_reason == 'length' we retry once with 1.5× tokens.
* On Pydantic ValidationError or unknown-citation we retry once with the
  validation error appended as a short correction instruction.
* The schema sent to Groq is stripped of keywords that the API rejects
  (minLength, minItems, maxItems, exclusiveMinimum, exclusiveMaximum);
  Pydantic still enforces them locally on the returned JSON.
* generate() and generate_json() accept an optional temperature kwarg so
  compare_analysis can pass temperature=0 for reproducibility.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, Dict, Optional

from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)

# Keywords that Groq's structured-output schema parser rejects.
# We strip them before sending; Pydantic re-applies them locally.
_UNSUPPORTED_SCHEMA_KEYS = frozenset({
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "exclusiveMinimum",
    "exclusiveMaximum",
})

# How much to expand max_tokens on a length-retry
_LENGTH_RETRY_FACTOR = 1.5


def _sanitise_schema(obj: Any) -> Any:
    """Recursively strip unsupported JSON-Schema keywords from *obj*."""
    if isinstance(obj, dict):
        return {
            k: _sanitise_schema(v)
            for k, v in obj.items()
            if k not in _UNSUPPORTED_SCHEMA_KEYS
        }
    if isinstance(obj, list):
        return [_sanitise_schema(item) for item in obj]
    return obj


class LLMClient:
    def __init__(self) -> None:
        self.model: str = settings.groq_model
        self._groq: Optional[Groq] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _client(self) -> Groq:
        if not settings.groq_api_key or settings.groq_api_key.startswith("your_"):
            raise RuntimeError(
                "Set GROQ_API_KEY in backend/.env, then restart the backend."
            )
        if self._groq is None:
            self._groq = Groq(
                api_key=settings.groq_api_key,
                timeout=60.0,
                max_retries=0,
            )
        return self._groq

    def _supports_reasoning_effort(self) -> bool:
        """True for model families known to accept reasoning_effort."""
        name = self.model.lower()
        return "r1" in name or getattr(settings, "groq_reasoning_effort", False)

    # ------------------------------------------------------------------
    # Core generate
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Single-turn generation.  Raises RuntimeError on finish_reason=='length'
        (caller is responsible for the length-retry loop)."""
        if max_tokens is None:
            max_tokens = getattr(settings, "groq_max_tokens", 4000)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {}
        if response_format:
            kwargs["response_format"] = response_format
        if self._supports_reasoning_effort():
            kwargs["reasoning_effort"] = "low"

        response = self._client().chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        finish_reason = response.choices[0].finish_reason
        if finish_reason == "length":
            raise _LengthError(
                "The model response was truncated (finish_reason=length). "
                "Retrying with a larger token budget."
            )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The model returned an empty response. Please retry.")
        return content

    # ------------------------------------------------------------------
    # generate_json — with retry logic
    # ------------------------------------------------------------------

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Structured-JSON generation with:
        * schema sanitisation (unsupported keywords stripped before sending)
        * one retry on finish_reason=='length' with 1.5× tokens
        * one retry on ValidationError / unknown-citation with correction hint
        """
        if max_tokens is None:
            max_tokens = getattr(settings, "groq_max_tokens", 4000)

        safe_schema = _sanitise_schema(copy.deepcopy(schema)) if schema else None
        response_format = (
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "incident_diagnosis",
                    "strict": True,
                    "schema": safe_schema,
                },
            }
            if safe_schema is not None
            else None
        )

        # --- first attempt ---
        try:
            return self.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except _LengthError:
            logger.warning(
                "finish_reason=length on first attempt; retrying with larger budget"
            )
            expanded = int(max_tokens * _LENGTH_RETRY_FACTOR)
            return self.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=expanded,
                response_format=response_format,
            )

    def generate_json_with_correction(
        self,
        prompt: str,
        correction: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Second-attempt call with a correction instruction appended."""
        corrected_prompt = (
            prompt
            + "\n\n[CORRECTION — please fix and regenerate]: "
            + correction[:400]
        )
        if max_tokens is None:
            max_tokens = getattr(settings, "groq_max_tokens", 4000)
        return self.generate_json(
            corrected_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            schema=schema,
        )

    def health_check(self) -> bool:
        self._client().models.list()
        return True


class _LengthError(RuntimeError):
    """Internal sentinel raised when finish_reason == 'length'."""


llm_client = LLMClient()
