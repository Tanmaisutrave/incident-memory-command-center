"""Content redaction pass for MEMORY_REDACTION=true.

Runs a simple regex-based pass over text before it is sent to the memory
provider or the LLM.  The goal is defence-in-depth: catch obviously sensitive
patterns that might have slipped through input filtering.

Patterns covered
----------------
* Email addresses
* HTTP Bearer tokens (Authorization: Bearer <token>)
* AWS access key IDs  (AKIA…)
* AWS secret access keys (40-char alphanumeric/+ following common env-var names)
* Generic API/secret keys in common env-var assignment patterns
* PEM private key blocks (-----BEGIN … PRIVATE KEY-----)

Redacted text is replaced with a fixed placeholder so the structure of the
document is preserved and the length is roughly similar.
"""

from __future__ import annotations

import re
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Pattern registry — (compiled regex, placeholder) pairs.
# Each regex should match the *entire sensitive token*, not surrounding context.
# ---------------------------------------------------------------------------

_RAW: List[Tuple[str, str]] = [
    # PEM private-key blocks (multiline)
    (
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
        r"[\s\S]*?"
        r"-----END (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
        "[REDACTED-PRIVATE-KEY]",
    ),
    # Authorization Bearer tokens
    (
        r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*",
        "Bearer [REDACTED-TOKEN]",
    ),
    # AWS access key IDs  (20-char AKIA… style)
    (
        r"\bAKIA[0-9A-Z]{16}\b",
        "[REDACTED-AWS-KEY-ID]",
    ),
    # AWS secret key in assignment (SECRET_ACCESS_KEY=<40 chars>)
    (
        r"(?i)(?:aws_secret_access_key|secret_access_key)\s*[=:]\s*"
        r"[A-Za-z0-9/+]{40}",
        "[REDACTED-AWS-SECRET]",
    ),
    # Generic secret/api_key/password assignment (key = value, up to 80 non-space chars)
    (
        r"(?i)(?:api[_-]?key|secret[_-]?key|password|passwd|token|auth[_-]?token)"
        r"\s*[=:]\s*[^\s\"']{8,80}",
        "[REDACTED-CREDENTIAL]",
    ),
    # Email addresses
    (
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
        "[REDACTED-EMAIL]",
    ),
]

REDACT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(raw, re.MULTILINE), placeholder)
    for raw, placeholder in _RAW
]


def redact(text: str) -> Tuple[str, int]:
    """Apply all redaction patterns to *text*.

    Returns:
        (redacted_text, count) where count is the number of substitutions made.
    """
    total = 0
    for pattern, placeholder in REDACT_PATTERNS:
        text, n = pattern.subn(placeholder, text)
        total += n
    return text, total


def redact_dict_values(d: dict) -> dict:
    """Recursively redact string values in a dict (for metadata / context strings)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, str):
            out[k], _ = redact(v)
        elif isinstance(v, dict):
            out[k] = redact_dict_values(v)
        else:
            out[k] = v
    return out
