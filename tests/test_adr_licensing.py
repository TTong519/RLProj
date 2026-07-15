"""ASET-06 auditability guard for ``docs/adr/0001-organ-mesh-licensing.md``.

This module is a CPU-only static-content guard. It has NO module-level
skipif gate so it runs unconditionally on every PR — including macOS CPU
CI — mirroring ``tests/dreamer/test_dreamerv3_regression_guard.py``'s
"runs on every PR" design.

Purpose: fail closed if the organ-mesh licensing ADR ever loses any of the
auditability tokens that make the SurgToolLoc rejection auditable
(Phase 39, plan 02, requirement ASET-06). The plan's SC#4/SC#5 acceptance
gates were originally run as one-off grep gates during execution; this test
persistently re-runs them so a future edit cannot silently strip a cited
clause, URL, or rationale marker.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Resolve the repository root from this test file's location.

    Walks upward until a ``.git`` entry is found (directory or file, for
    worktrees). Falls back to the parent of the ``tests/`` directory if no
    ``.git`` is present, which keeps the guard usable in shallow checkouts.
    """
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        if (ancestor / ".git").exists():
            return ancestor
    # Fallback: tests/ dir's parent is the repo root.
    return here.parents[1]


@pytest.fixture(scope="module")
def adr_text() -> str:
    """Read the ADR file once per module; fail closed if it is missing."""
    root = _repo_root()
    adr_path = root / "docs" / "adr" / "0001-organ-mesh-licensing.md"
    assert adr_path.is_file(), (
        f"ASET-06: ADR artifact not found at {adr_path}. "
        "docs/adr/0001-organ-mesh-licensing.md must exist."
    )
    return adr_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_text() -> str:
    """Read the ADR index once per module; fail closed if it is missing."""
    root = _repo_root()
    readme_path = root / "docs" / "adr" / "README.md"
    assert readme_path.is_file(), (
        f"ASET-06: ADR index not found at {readme_path}. " "docs/adr/README.md must exist."
    )
    return readme_path.read_text(encoding="utf-8")


# Each tuple: (token, description) — substring match (grep -F semantics).
ADR_TOKENS: list[tuple[str, str]] = [
    ("procedural generation", "default organ-mesh source disposition"),
    ("rejected", "SurgToolLoc rejection marker"),
    ("modality", "PRIMARY rejection rationale marker"),
    ("endoscopic", "modality evidence marker (endoscopic video)"),
    ("Status: accepted", "ADR decision status"),
    (
        "neither pass it on to a third party nor use it for any publication "
        "or for commercial uses",
        "verbatim MICCAI/EndoVis clause 2 (auditability)",
    ),
    (
        "surgtoolloc23.grand-challenge.org/challenge-guidelines",
        "public challenge-guidelines URL citation",
    ),
    (
        "surgtoolloc23.grand-challenge.org/data-description",
        "public data-description URL citation",
    ),
]


@pytest.mark.parametrize(
    ("token", "description"),
    ADR_TOKENS,
    ids=[t[1] for t in ADR_TOKENS],
)
def test_adr_contains_aset06_auditability_token(
    adr_text: str, token: str, description: str
) -> None:
    """ASET-06: each auditability token must be present in the ADR body."""
    assert token in adr_text, (
        f"ASET-06 auditability check FAILED: the ADR is missing the token "
        f"required for {description!r}. Expected substring (grep -F): "
        f"{token!r}. If the ADR was intentionally edited, restore the token "
        f"or ESCALATE — do NOT weaken this assertion. See "
        f"docs/adr/0001-organ-mesh-licensing.md and "
        f".planning/phases/39-k8s-pvc-e2e-organ-mesh-licensing-adr/"
        f"39-02-SUMMARY.md."
    )


def test_adr_file_exists() -> None:
    """ASET-06: the ADR artifact file itself must exist on disk."""
    root = _repo_root()
    adr_path = root / "docs" / "adr" / "0001-organ-mesh-licensing.md"
    assert adr_path.is_file(), f"ASET-06: ADR artifact missing at {adr_path}."


def test_adr_readme_indexes_adr_0001(readme_text: str) -> None:
    """ASET-06: the ADR index must reference ADR-0001 by filename."""
    assert "0001-organ-mesh-licensing" in readme_text, (
        "ASET-06 auditability check FAILED: docs/adr/README.md does not "
        "index ADR-0001 (expected the substring "
        "'0001-organ-mesh-licensing'). The ADR index must link the "
        "organ-mesh licensing decision so it is discoverable."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
