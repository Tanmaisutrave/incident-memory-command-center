"""Post-generation guardrail: deny-list check over LLM-authored action lists.

Patterns are defined here so they can be updated without touching business
logic.  Each entry is a (regex, human-readable reason) pair.

The checker is intentionally conservative: it flags rather than rejects, so
the on-call engineer always sees every action with full context.  A matched
action gets a visible warning prepended to the analysis ``warnings`` list and
the matched text is collected in ``flagged_actions`` on the response.

Redis-specific production prohibitions (MONITOR, FLUSHALL) are deliberately
placed here rather than in the generic SYSTEM prompt.
"""

import re
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Deny-list
# Each entry: (compiled regex, short label for the warning message)
# ---------------------------------------------------------------------------
_RAW_PATTERNS: List[Tuple[str, str]] = [
    # TLS / certificate verification
    (r"disable\s+(tls|ssl|certificate)\s*verif", "disable TLS/certificate verification"),
    (r"verify[\s_-]?ssl\s*[=:]\s*false", "disable SSL verification flag"),
    (r"insecure[\s_-]?skip[\s_-]?verify", "skip TLS verify flag"),
    (r"--insecure\b", "--insecure flag (disables TLS verification)"),
    # Dangerous shell operations
    (r"\brm\s+-[a-z]*r[a-z]*\s*[/~]", "recursive remove from root or home"),
    (r"\brm\s+-rf\b", "rm -rf"),
    # Kubernetes destructive ops
    (r"\bkubectl\s+delete\b", "kubectl delete (destructive cluster operation)"),
    # SQL destructive ops
    (r"\bDROP\s+TABLE\b", "DROP TABLE"),
    (r"\bTRUNCATE\s+TABLE\b", "TRUNCATE TABLE"),
    (r"\bDROP\s+DATABASE\b", "DROP DATABASE"),
    # Redis dangerous ops
    (r"\bFLUSHALL\b", "Redis FLUSHALL (wipes all data)"),
    (r"\bFLUSHDB\b", "Redis FLUSHDB (wipes current DB)"),
    (r"\bMONITOR\b", "Redis MONITOR (blocks server, never use in production)"),
    # Restart presented as a low-risk diagnostic step
    (r"\brestart\b.{0,60}\bdiagnos", "restart presented as a harmless diagnostic step"),
    (r"\breboot\b.{0,60}\bdiagnos", "reboot presented as a harmless diagnostic step"),
]

DENY_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(raw, re.IGNORECASE | re.DOTALL), label)
    for raw, label in _RAW_PATTERNS
]


def check_actions(texts: List[str]) -> List[str]:
    """Return a list of warning strings for any text that matches the deny-list.

    Each warning names the matched text (truncated) and the reason.
    The caller is responsible for attaching these warnings to the response and
    populating ``flagged_actions``.
    """
    warnings: List[str] = []
    for text in texts:
        for pattern, label in DENY_PATTERNS:
            if pattern.search(text):
                snippet = text[:120].replace("\n", " ")
                warnings.append(
                    f"Flagged action — contains '{label}': \"{snippet}…\" "
                    "Verify this is safe before executing."
                )
                break  # one warning per action item is enough
    return warnings
