"""Redact secrets from error strings before they reach logs, status bar, or QMessageBox.

Per CONTEXT.md D-19 + GUI-09: ALL error strings routed through the editor must pass
through ``safe_error_message()`` so that API keys, bearer tokens, and env-var-style
assignments are replaced with ``[REDACTED]`` before display.

Five pattern families are covered:

1. OpenAI keys:    ``sk-...`` (20+ alphanumeric chars)
2. Anthropic keys: ``sk-ant-...`` (20+ alphanumeric chars/dashes)
3. xAI/Grok keys:  ``xai-...`` (20+ alphanumeric chars)
4. Bearer tokens:  ``Bearer <token>``
5. Env-var style:  ``*_KEY=...`` / ``*_TOKEN=...`` (value runs until whitespace, comma, or end)

The module is pure Python (no PySide6 import) so it can be unit-tested without
``QT_QPA_PLATFORM=offscreen``.
"""

from __future__ import annotations

import re
from typing import Final

_REDACTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"sk-ant-[A-Za-z0-9-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xai-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"\b([A-Z][A-Z0-9]*(?:_KEY|_TOKEN))=(?:[^\s,;]+)", re.IGNORECASE),
)
_REDACTED: Final[str] = "[REDACTED]"


def safe_error_message(error: BaseException | str) -> str:
    """Return a copy of ``error`` with all secret-like substrings replaced by ``[REDACTED]``.

    Accepts either an Exception (uses ``str(exc)``) or a raw string. The function is
    pure: no logging, no side effects, no Qt dependency.
    """
    text = str(error) if isinstance(error, BaseException) else error
    for pattern in _REDACTION_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text
