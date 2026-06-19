#!/usr/bin/env python3
"""Shared helpers for the ``demos/`` demo suite.

This module is the single source of truth for:

- Rich-based banner printing (``print_banner``)
- Scene info printing (``print_scene_info``)
- Scene path resolution with repo-root fallback + traversal guard (``resolve_scene``)
- Narration step formatting that enforces the 5-stage template (``format_narration_step``)
- Default RL training hyperparameters shared across all 3 demos (``DEFAULT_TRAINING_CONFIG``)

All demos in ``demos/`` MUST import from this module rather than
re-implementing banner printing or scene loading. The narration template
lives at ``demos/NARRATION_TEMPLATE.md`` (written FIRST per P8 pitfall
prevention); see :func:`format_narration_step` for the in-code pointer.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from rich.console import Console

# Lazy import: SceneDefinition is heavy and pulls in pydantic; demos that
# only need ``resolve_scene`` shouldn't pay for it. We import the type
# solely for runtime annotations (``TYPE_CHECKING``) and resolve it at
# runtime only when ``print_scene_info`` is called.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from surg_rl.scene_definition.schema import SceneDefinition


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Repo root: parent of the ``demos/`` directory containing this file. This is
# the canonical anchor for scene-path resolution (always relative to repo
# root, never to the demo's CWD — which may differ when the user runs the
# demo from a worktree, a CI checkout, or a different shell).
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Rich Console writes to stderr so banners don't pollute ``--json`` or pipe
# output. Mirrors ``surg_rl.utils.logging`` style.
_CONSOLE = Console(stderr=True)

# The 5 narration stages — must match ``demos/NARRATION_TEMPLATE.md`` exactly.
# Plan 03's regression test greps for these literal strings.
_NARRATION_STAGES: tuple[str, ...] = (
    "Setup",
    "Action",
    "Critical Moment",
    "Outcome",
    "Takeaway",
)
_MAX_WORDS_PER_SENTENCE = 25

# Regex used as a quick pre-check for ``..`` path-traversal. The
# authoritative guard is the ``Path.relative_to(_REPO_ROOT)`` check inside
# :func:`resolve_scene`, which runs after symlink resolution. The pre-check
# exists so that obviously-malicious paths (e.g. ``../etc/passwd``) raise
# with a clear message before we even try to resolve them.
_REPO_TRAVERSAL_RE = re.compile(r"(^|/)\.\.(/|$)")


# ---------------------------------------------------------------------------
# Banner / scene info
# ---------------------------------------------------------------------------


def print_banner(title: str, subtitle: str = "") -> None:
    """Print a Rich banner block to stderr.

    Args:
        title: Demo title (e.g., "Suturing RL Training Demo").
        subtitle: Optional subtitle (e.g., "Phase 32 — Demo Suite Polish").

    The banner mirrors the 60-char ASCII rule from ``demos/demo.py`` but
    upgrades to Rich markup so colors and centering render correctly in
    non-TTY contexts. Writes to stderr so stdout remains machine-parseable
    for ``--json`` / pipe consumers.
    """
    _CONSOLE.rule(title)
    if subtitle:
        _CONSOLE.print(subtitle, style="dim")
    _CONSOLE.print()  # trailing blank line


def print_scene_info(scene: SceneDefinition) -> None:
    """Print a summary of the loaded scene.

    Args:
        scene: A ``SceneDefinition`` instance loaded via ``load_scene()``.

    Prints scene metadata, robot/tissue/instrument counts, and (if present)
    task objectives. Each ``scene.X`` access is guarded per AGENTS.md
    optional-field rules: ``scene.task`` may be ``None`` (default per the
    schema), so we guard before reading its fields.

    Writes to stderr so stdout remains machine-parseable.
    """
    _CONSOLE.print(f"  Scene:      {scene.metadata.name}")
    _CONSOLE.print(f"  Robots:     {len(scene.robots)}")
    _CONSOLE.print(f"  Tissues:    {len(scene.tissues)}")
    _CONSOLE.print(f"  Instruments:{len(scene.instruments)}")
    if scene.task is not None:
        _CONSOLE.print(f"  Task:       {scene.task.name}")
        for obj in scene.task.objectives:
            _CONSOLE.print(f"    - {obj.name} (weight={obj.weight})")


# ---------------------------------------------------------------------------
# Scene path resolution
# ---------------------------------------------------------------------------


def resolve_scene(path: str | Path) -> Path:
    """Resolve a scene path to an absolute ``Path`` inside the repo root.

    Args:
        path: Relative or absolute path to a scene JSON/YAML file.

    Returns:
        Absolute ``Path`` to the scene file, resolved against the repo
        root (parent of ``demos/``) when the input is relative.

    Raises:
        ValueError: If the resolved path escapes the repo root via
            ``..`` traversal. This is the threat-model T-32-02 guard
            (Tampering — accidental or malicious scene-file swap).
        FileNotFoundError: If the resolved path does not exist on disk.

    The function is CWD-independent: it anchors on ``__file__`` (this
    module's location) rather than ``Path.cwd()`` so demos can be invoked
    from any working directory.
    """
    p = Path(path)
    # Reject obviously-malicious paths before any filesystem call so the
    # error message is informative (relative_to() after resolve() can
    # produce a confusing message for symlinked traversals).
    if _REPO_TRAVERSAL_RE.search(str(p)):
        raise ValueError(f"Scene path contains '..' traversal: {p!s} (root={_REPO_ROOT})")
    if not p.is_absolute():
        p = _REPO_ROOT / p
    # Resolve .. components without requiring the file to exist.
    p = p.resolve(strict=False)
    # Authoritative guard: after symlink resolution, the path MUST live
    # inside the repo root. Any path outside raises ValueError.
    try:
        p.relative_to(_REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"Scene path escapes the repo root: {p} (root={_REPO_ROOT})") from exc
    if not p.exists():
        raise FileNotFoundError(f"Scene file not found: {p}")
    return p


# ---------------------------------------------------------------------------
# Narration step formatting
# ---------------------------------------------------------------------------


def _count_words(text: str) -> int:
    """Count whitespace-delimited word tokens in ``text``."""
    return len(re.findall(r"\b\w+\b", text))


def format_narration_step(stage: str, line: str) -> str:
    """Format a single narration step that conforms to ``demos/NARRATION_TEMPLATE.md``.

    Args:
        stage: One of ``"Setup"``, ``"Action"``, ``"Critical Moment"``,
            ``"Outcome"``, ``"Takeaway"``.
        line: The narration sentence (≤25 words, no first-person,
            present tense for ongoing actions).

    Returns:
        Rich-formatted string: ``"[{stage}] {line}"`` with the stage name
        in bold + cyan. The function does NOT print the string — the
        caller decides whether to print it, log it, or pass it to a Rich
        Panel. This keeps the function testable without Rich's TTY
        detection.

    Raises:
        ValueError: If ``stage`` is not one of the 5 valid stages.
        ValueError: If ``line`` contains more than 25 words.

    See ``demos/NARRATION_TEMPLATE.md`` for the full vocabulary rules and
    the 5-stage structure that all 3 demos (suturing, knot-tying,
    needle-passing) must follow.
    """
    if stage not in _NARRATION_STAGES:
        raise ValueError(
            f"Invalid narration stage: {stage!r}. Must be one of "
            f"{_NARRATION_STAGES}. See demos/NARRATION_TEMPLATE.md."
        )
    word_count = _count_words(line)
    if word_count > _MAX_WORDS_PER_SENTENCE:
        raise ValueError(
            f"Narration line has {word_count} words (max "
            f"{_MAX_WORDS_PER_SENTENCE}). See demos/NARRATION_TEMPLATE.md."
        )
    return f"[bold cyan][{stage}][/bold cyan] {line}"


# ---------------------------------------------------------------------------
# Default training config
# ---------------------------------------------------------------------------


# Shared RL hyperparameter defaults for all 3 demos. Values originate from
# the existing ``demos/demo.py:115-125`` AlgorithmConfig constructor
# args. Do NOT export individual fields as module constants — keep them
# in the dict so callers can splat-merge:
#
#     TrainingConfig(**{**DEFAULT_TRAINING_CONFIG, "scene_path": args.scene})
#
# Pydantic v2 models don't accept ``**dict`` directly; demos unpack the
# fields explicitly when constructing ``AlgorithmConfig``.
DEFAULT_TRAINING_CONFIG: dict[str, Any] = {
    "algorithm": "PPO",
    "learning_rate": 3e-4,
    "n_steps": 2048,
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "ent_coef": 0.01,
    "total_timesteps": 50_000,
    "max_episode_steps": 2000,
    "seed": 42,
}


__all__ = [
    "DEFAULT_TRAINING_CONFIG",
    "format_narration_step",
    "print_banner",
    "print_scene_info",
    "resolve_scene",
]


if __name__ == "__main__":
    # Quick smoke test: print the banner + the 5-stage narration shape.
    # Useful for manual visual inspection during demos/_common.py dev.
    print_banner("demos/_common.py", subtitle="Shared helpers smoke test")
    for stage in _NARRATION_STAGES:
        print(format_narration_step(stage, f"Sample {stage} narration."))
    sys.stdout.write(f"DEFAULT_TRAINING_CONFIG has {len(DEFAULT_TRAINING_CONFIG)} keys\n")
