"""Shared Hindsight client — one instance, explicit lifecycle, stable source IDs.

Design notes
------------
* A single ``Hindsight`` SDK instance is created lazily on first use and reused
  for the lifetime of the process.  ``close()`` is called in the FastAPI
  lifespan hook so connections are released cleanly on shutdown.

* ``retain()`` returns an explicit dict:
      {'accepted': bool, 'async': bool, 'operation_id': str|None}
  Callers must not rely on a bare boolean "success" flag.
  ``accepted`` is True when the SDK says success=True regardless of async mode.
  Async retains are treated as accepted-but-pending, not failed.

* ``recall()`` produces stable source IDs: the SDK always returns a real UUID
  in ``result.id`` (the field is StrictStr, not Optional).  We use it directly.
  If for any reason it is empty (defensive), we fall back to sha1[:12] of the
  text rather than fabricating ``M{i}`` ordinal IDs.

* Tag filtering: the SDK's ``recall()`` supports a ``tags`` parameter natively.
  When ``settings.recall_same_env_only`` is True and the caller passes an
  ``environment`` argument, we pass ``tags=["env:<environment>"]`` to the SDK.
  Results are also post-filtered as a belt-and-braces measure and the
  limitation is documented in the warning when the environment is not production.

* Metadata: every retained document carries ``env:<environment>``,
  ``svc:<service>`` and ``status:<status>`` tags so recall can filter on them.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Tag namespace prefixes — keep them stable; changing breaks existing filters.
_TAG_ENV_PREFIX = "env:"
_TAG_SVC_PREFIX = "svc:"
_TAG_STATUS_PREFIX = "status:"
_TAG_OUTCOME_PREFIX = "outcome:"


def _stable_source_id(text: str) -> str:
    """sha1[:12] of the text — stable across calls for the same content."""
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:12]


class HindsightClient:
    """Thin wrapper around the Hindsight SDK with explicit lifecycle management."""

    def __init__(self) -> None:
        self.bank_id: str = settings.hindsight_bank_id
        self._client = None  # lazy; created on first use

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _get_client(self):
        """Return (creating if necessary) the shared SDK client."""
        if not settings.hindsight_api_key or settings.hindsight_api_key.startswith("your_"):
            raise RuntimeError(
                "Set HINDSIGHT_API_KEY in backend/.env, then restart the backend."
            )
        if self._client is None:
            from hindsight_client import Hindsight
            self._client = Hindsight(
                base_url=settings.hindsight_base_url,
                api_key=settings.hindsight_api_key,
                timeout=35,
            )
            logger.debug("Hindsight SDK client created (bank=%s)", self.bank_id)
        return self._client

    def close(self) -> None:
        """Release the underlying HTTP connections.  Called in the lifespan hook."""
        if self._client is not None:
            try:
                self._client.close()
                logger.debug("Hindsight SDK client closed")
            except Exception:
                logger.warning("Hindsight client close() raised an exception", exc_info=True)
            finally:
                self._client = None

    # ------------------------------------------------------------------
    # retain
    # ------------------------------------------------------------------

    def retain(
        self,
        content: str,
        metadata: Optional[Dict[str, str]] = None,
        context: Optional[str] = None,
        document_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        update_mode: Optional[str] = "replace",
    ) -> Dict[str, Any]:
        """Retain content in the memory bank.

        Returns:
            {
                'accepted': bool,   # True if SDK reported success (sync or async)
                'async':    bool,   # True if the SDK processed asynchronously
                'operation_id': str | None,
            }
        """
        meta_str: Dict[str, str] = {
            k: str(v) for k, v in (metadata or {}).items()
        }
        doc_id = document_id or (metadata or {}).get("incident_id")

        result = self._get_client().retain(
            bank_id=self.bank_id,
            content=content,
            metadata=meta_str or None,
            context=context,
            document_id=doc_id,
            tags=tags or [],
            update_mode=update_mode,
        )

        accepted = bool(result.success)
        is_async = bool(result.var_async)
        operation_id = result.operation_id

        logger.debug(
            "Retain result: accepted=%s async=%s operation_id=%s doc_id=%s",
            accepted, is_async, operation_id, doc_id,
        )
        return {
            "accepted": accepted,
            "async": is_async,
            "operation_id": operation_id,
        }

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    def delete_document(self, document_id: str) -> bool:
        """Delete a document from the memory bank by document_id.

        Returns True if the delete call succeeded, False otherwise.
        The SDK's low-level documents API is async; we run it synchronously.
        """
        import asyncio
        try:
            client = self._get_client()
            asyncio.run(
                client.documents.delete_document(
                    bank_id=self.bank_id,
                    document_id=document_id,
                )
            )
            logger.info("Deleted memory document %r from bank %s", document_id, self.bank_id)
            return True
        except Exception as exc:
            logger.warning(
                "Failed to delete memory document %r: %s", document_id, type(exc).__name__
            )
            return False

    # ------------------------------------------------------------------
    # recall
    # ------------------------------------------------------------------

    def recall(
        self,
        query: str,
        max_tokens: int = 2400,
        budget: str = "mid",
        environment: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Recall similar memories from the bank.

        When ``settings.recall_same_env_only`` is True and *environment* is
        given, the SDK tag filter is used (native) and results are also
        post-filtered as a belt-and-braces measure.

        Returns a list of dicts with keys: text, type, source_id.
        source_ids are the SDK's real UUIDs; sha1[:12] fallback if empty.
        """
        recall_tags: Optional[List[str]] = None
        if settings.recall_same_env_only and environment:
            recall_tags = [f"{_TAG_ENV_PREFIX}{environment}"]

        response = self._get_client().recall(
            bank_id=self.bank_id,
            query=query,
            max_tokens=max_tokens,
            budget=budget,
            tags=recall_tags,
            tags_match="any_strict" if recall_tags else "any",
        )

        results = []
        for m in (response.results or []):
            raw_id = str(m.id).strip() if m.id else ""
            source_id = raw_id if raw_id else _stable_source_id(m.text)

            # Post-filter: if same-env filtering is on, drop results that
            # carry a different env tag (belt-and-braces; native filter above
            # is the primary mechanism).
            if settings.recall_same_env_only and environment and recall_tags:
                mem_tags: List[str] = list(m.tags or [])
                expected_tag = f"{_TAG_ENV_PREFIX}{environment}"
                if mem_tags and expected_tag not in mem_tags:
                    logger.debug(
                        "Post-filtered memory %s (env tag mismatch)", source_id
                    )
                    continue

            results.append({
                "text": m.text,
                "type": str(m.type) if m.type else "world",
                "source_id": source_id,
            })

        return results

    # ------------------------------------------------------------------
    # reflect
    # ------------------------------------------------------------------

    def reflect(
        self,
        query: str,
        budget: str = "low",
        context: Optional[str] = None,
    ) -> str:
        return self._get_client().reflect(
            bank_id=self.bank_id,
            query=query,
            budget=budget,
            context=context,
            max_tokens=1200,
        ).text

    # ------------------------------------------------------------------
    # health_check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        response = httpx.get(
            settings.hindsight_base_url.rstrip("/") + "/health/ready",
            headers={"Authorization": f"Bearer {settings.hindsight_api_key}"},
            timeout=5,
        )
        return response.is_success


# Module-level singleton — shared across all requests.
hindsight_client = HindsightClient()
