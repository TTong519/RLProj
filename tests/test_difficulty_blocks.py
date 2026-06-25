"""Tests for TaskConfig.difficulty_blocks scene-author field (Phase 37, TASK-08 / SC#1 / SC#5).

SC#1: Scene JSON with ``task.difficulty_blocks`` for all three levels (EASY/MEDIUM/HARD)
      round-trips through Pydantic v2 validation with authored values preserved.
      A scene WITHOUT ``difficulty_blocks`` still loads with ``scene.task.difficulty_blocks is None``
      (6 existing v0.4.0 scenes unaffected). Malformed blocks (out-of-range overrides) are
      rejected at scene-load time (ASVS V5 / T-37-01).

SC#5: ``difficulty_blocks`` is the canonical spelling across PROJECT.md, schema, and STATE.md;
      the prior plural-s drift spelling is gone (subprocess grep audit).

This file is shared across plans 37-01/02/03. Plan 37-01 adds ONLY the SC#1 round-trip +
SC#5 naming-audit tests below. Plans 37-02/37-03 add their own test classes.
"""

import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from surg_rl.rl import DifficultyLevel
from surg_rl.rl.difficulty import DifficultyLevelConfig
from surg_rl.scene_definition.loader import SceneLoader, SceneValidationError
from surg_rl.scene_definition.schema import TaskConfig


# =============================================================================
# SC#1 — scene JSON round-trip for TaskConfig.difficulty_blocks
# =============================================================================


class TestSceneBlocksRoundTrip:
    """SC#1: ``difficulty_blocks`` round-trips through Pydantic v2 + SceneLoader."""

    #: Inline scene JSON fixture with all three levels authored (RESEARCH.md:558-572).
    #: Override values are inside the verified D-07 global union bounds
    #: for ``target_precision_tolerance`` ([0.002, 0.3]).
    BLOCKS_SCENE_JSON = json.dumps(
        {
            "metadata": {"name": "suturing_with_blocks", "version": "0.6.0"},
            "scene": {"id": "suturing_blocks", "environment": "operating_room"},
            "task": {
                "name": "suturing_task",
                "description": "Suturing with per-level difficulty blocks",
                "task_type": "suturing",
                "difficulty_level": 1.0,
                "difficulty_blocks": {
                    "EASY": {"target_precision_tolerance": 0.02},
                    "MEDIUM": {"target_precision_tolerance": 0.005},
                    "HARD": {"target_precision_tolerance": 0.002},
                },
            },
        }
    )

    def test_scene_with_blocks_round_trips(self):
        """SC#1: a scene with all 3 levels of difficulty_blocks round-trips with values preserved."""
        scene = SceneLoader().load_from_string(self.BLOCKS_SCENE_JSON, format="json")

        assert scene.task is not None
        blocks = scene.task.difficulty_blocks
        assert blocks is not None
        assert isinstance(blocks, dict)
        # DifficultyLevel enum keys (Pydantic v2 coerces JSON string keys by float value).
        assert DifficultyLevel.EASY in blocks
        assert DifficultyLevel.MEDIUM in blocks
        assert DifficultyLevel.HARD in blocks
        # Authored override values preserved on each DifficultyLevelConfig value.
        assert blocks[DifficultyLevel.EASY].target_precision_tolerance == 0.02
        assert blocks[DifficultyLevel.MEDIUM].target_precision_tolerance == 0.005
        assert blocks[DifficultyLevel.HARD].target_precision_tolerance == 0.002

        # Re-serialization round-trip: model_dump() -> TaskConfig.model_validate preserves values.
        dump = scene.model_dump()
        re_validated = TaskConfig.model_validate(dump["task"])
        assert re_validated.difficulty_blocks is not None
        assert (
            re_validated.difficulty_blocks[DifficultyLevel.HARD].target_precision_tolerance == 0.002
        )
        assert (
            re_validated.difficulty_blocks[DifficultyLevel.EASY].target_precision_tolerance == 0.02
        )

    @pytest.mark.parametrize(
        "scene_file",
        [
            "simple_suturing.json",
            "knot_tying.json",
            "needle_insertion.json",
            "grasping.json",
            "cutting.json",
            "dissection.json",
        ],
    )
    def test_existing_scenes_load_without_blocks(self, scene_file):
        """SC#1 negative: the 6 v0.4.0 task scenes load with ``difficulty_blocks is None``.

        Canonical SC#1 negative regression name — shared with 37-03 Task 2 and
        37-VALIDATION.md row 37-SC1-neg.
        """
        scene_path = Path(__file__).parent.parent / "scenes" / scene_file
        if not scene_path.exists():
            pytest.skip(f"scenes/{scene_file} not found")
        scene = SceneLoader().load(str(scene_path))
        assert scene.task is not None
        assert scene.task.difficulty_blocks is None

    def test_malformed_blocks_rejected(self):
        """SC#1 / T-37-01: an out-of-range override raises at scene-load time (ASVS V5)."""
        malformed_json = json.dumps(
            {
                "metadata": {"name": "malformed_blocks", "version": "0.6.0"},
                "scene": {"id": "malformed", "environment": "operating_room"},
                "task": {
                    "name": "suturing_task",
                    "description": "Malformed blocks — out of D-07 bounds",
                    "task_type": "suturing",
                    "difficulty_level": 1.0,
                    "difficulty_blocks": {
                        "HARD": {"target_precision_tolerance": 999.0},  # outside [0.002, 0.3]
                    },
                },
            }
        )
        # SceneLoader wraps pydantic.ValidationError as SceneValidationError; both
        # are acceptable signals that validation rejected the malformed input.
        with pytest.raises((SceneValidationError, ValidationError)):
            SceneLoader().load_from_string(malformed_json, format="json")


# =============================================================================
# SC#5 — naming audit (canonical spelling = difficulty_blocks)
# =============================================================================


class TestNamingAudit:
    """SC#5: the prior plural-s drift spelling is gone from canonical docs."""

    def test_no_drift_spelling_in_canonical_docs(self):
        """SC#5: ``difficulty_levels`` (the drift spelling) is absent from canonical docs.

        Greps PROJECT.md, STATE.md, and the src/ tree. Historical milestone archives
        under ``.planning/milestones/`` are intentionally excluded (they are frozen
        historical record). ``grep`` exits 1 when no matches are found.
        """
        result = subprocess.run(
            ["grep", "-rn", "difficulty_levels",
             ".planning/PROJECT.md", ".planning/STATE.md", "src/surg_rl/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            "drift spelling `difficulty_levels` still present in canonical docs:\n"
            f"{result.stdout}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])