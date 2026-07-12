"""DMV3-09 regression guard for ``surg_rl.dreamer.subprocess._build_agent``.

This module is a CPU-only source-inspection guard. It has NO module-level
skipif gate (unlike ``test_dreamerv3_subprocess_e2e.py``) so it runs
unconditionally on every PR — including macOS CPU CI — per
40-CONTEXT.md D-10.

Purpose: fail closed if ``_build_agent`` ever regresses to a stub that
returns ``None``. The Phase 24 stub returned ``None``; the Phase 40 real
implementation returns an agent bundle (``{agent, env, checkpoint, replay,
step}``). If a future change reintroduces a ``return None`` (or an
implicit bare ``return`` that evaluates to ``None``), this guard fails
with a DMV3-09-tagged message — surfacing the stub regression structurally
rather than waiting for the GPU-gated E2E test to catch it.

The check uses ``inspect.getsource`` + ``ast.parse`` + an AST walk for
``ast.Return`` nodes whose ``.value`` is ``ast.Constant(value=None)``. This
is more robust than a naive ``"return None" in source`` string match,
which would false-positive on docstrings/comments mentioning ``None``.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from surg_rl.dreamer.subprocess import _build_agent


def _walk_for_none_return(source: str) -> bool:
    """Return True if ``source`` contains a ``return None`` (or bare ``return``).

    Walks the parsed AST for ``ast.Return`` nodes. A bare ``return`` is
    represented at the AST level as ``Return(value=None)`` (no value node),
    while an explicit ``return None`` is ``Return(value=Constant(value=None))``.
    Both shapes indicate the function can yield ``None`` and are caught here.
    If the source cannot be parsed, fall back to a conservative string
    check — better to fail closed on a parse error than silently pass.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "return None" in source

    for node in ast.walk(tree):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        if value is None:
            # Bare `return` (returns None implicitly).
            return True
        if isinstance(value, ast.Constant) and value.value is None:
            return True
    return False


def test_build_agent_does_not_return_none() -> None:
    """DMV3-09: ``_build_agent`` must NEVER return ``None`` (stub regression guard).

    The Phase 24 stub returned ``None`` and the subprocess protocol gated on
    ``agent is None`` to emit ``{"type": "ERROR", "error": "Agent not
    configured"}``. The Phase 40 real implementation must return an agent
    bundle. If the source contains an explicit ``return None`` (or a bare
    ``return``), this guard fails closed — preventing a silent stub
    regression that would otherwise only surface on the GPU-gated E2E job.
    """
    source = textwrap.dedent(inspect.getsource(_build_agent))
    has_none = _walk_for_none_return(source)
    assert not has_none, (
        "DMV3-09 regression guard FAILED: surg_rl.dreamer.subprocess._build_agent "
        "contains a `return None` (or bare `return`) statement — stub regression! "
        "The real implementation must return an agent bundle "
        "({agent, env, checkpoint, replay, step}). See "
        ".planning/phases/40-real-dreamerv3-integration-sentinel-flip/40-01-PLAN.md"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
