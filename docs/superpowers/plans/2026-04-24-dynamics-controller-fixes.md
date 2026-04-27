# Dynamics Controller Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Fix dynamics controller correctness issues: silent failures, dead code, wrong API calls, and parameter application.

**Architecture:** Each fix is localized to one controller file.

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/surg_rl/dynamics/parameter_randomizer.py` | Domain randomization: silent failures, visual color destruction |
| `src/surg_rl/dynamics/adaptive_difficulty.py` | Adaptive difficulty: dead code, wrong PyBullet gravity API |
| `src/surg_rl/dynamics/environment_controller.py` | Facade: encapsulation leak, parameter passing |

---

### Task 1: Fix ParameterRandomizer Silent Failures

**Bug:** Every `_apply_*` method uses bare `except Exception: pass`, swallowing real misconfigurations.

**Files:**
- Modify: `src/surg_rl/dynamics/parameter_randomizer.py`
- Test: `tests/test_dynamics.py`

- [ ] **Step 1: Find bare except blocks**

Run: `grep -n "except Exception:" src/surg_rl/dynamics/parameter_randomizer.py`

- [ ] **Step 2: Replace with logging**

Replace each `except Exception: pass` with:
```python
        except Exception as e:
            logger.warning(f"Failed to apply {parameter_name}: {e}")
```

- [ ] **Step 3: Add test**

```python
def test_parameter_randomizer_logs_on_failure():
    """Failed parameter application must log a warning, not be silent."""
    import logging
    from unittest.mock import MagicMock, patch
    from surg_rl.dynamics.parameter_randomizer import ParameterRandomizer
    from surg_rl.scene_definition.schema import DomainRandomizationConfig

    randomizer = ParameterRandomizer(DomainRandomizationConfig())
    randomizer.start()
    randomizer.reset()

    snapshot = randomizer.sample_parameters()
    simulator = MagicMock()
    simulator.__class__.__name__ = "BrokenSimulator"
    # Make setGravity raise
    simulator.setGravity.side_effect = RuntimeError("no gravity")

    with patch("surg_rl.dynamics.parameter_randomizer.logger") as mock_logger:
        result = randomizer.apply_parameters(snapshot, simulator)
        assert result is False
        mock_logger.warning.assert_called()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dynamics.py::test_parameter_randomizer_logs_on_failure -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/dynamics/parameter_randomizer.py tests/test_dynamics.py
git commit -m "fix: replace silent failure suppression with warning logging in ParameterRandomizer"
```

---

### Task 2: Fix PyBullet Visual Randomization Destroys Colors

**Bug:** `_apply_visual_parameters` hardcodes base RGB of `0.5` instead of reading the body's actual color.

**Files:**
- Modify: `src/surg_rl/dynamics/parameter_randomizer.py`
- Test: `tests/test_dynamics.py`

- [ ] **Step 1: Find _apply_visual_parameters**

Run: `grep -n "_apply_visual_parameters" src/surg_rl/dynamics/parameter_randomizer.py`

- [ ] **Step 2: Read actual color before applying offset**

In the PyBullet visual randomization path, before applying the offset, read the actual color:

```python
        for body_name, body_id in simulator._body_ids.items():
            # Read current visual shape data to get actual base color
            num_links = p.getNumJoints(body_id, physicsClientId=simulator._physics_client)
            # Try to get color from link 0 or base
            for link_idx in range(-1, num_links):
                color_data = p.getVisualShapeData(
                    body_id,
                    linkIndex=link_idx,
                    physicsClientId=simulator._physics_client,
                )
                if color_data:
                    rgba = color_data[0][7]  # RGBA tuple
                    base_r, base_g, base_b = rgba[0], rgba[1], rgba[2]
                    break
            else:
                base_r = base_g = base_b = 0.5

            r = np.clip(base_r + visual_params.get("color_r_offset", 0.0), 0.0, 1.0)
            g = np.clip(base_g + visual_params.get("color_g_offset", 0.0), 0.0, 1.0)
            b = np.clip(base_b + visual_params.get("color_b_offset", 0.0), 0.0, 1.0)
```

If the above is too complex, at minimum read the existing color from the simulator's stored data if available, or use the original scene color from `_initial_` data.

Simpler fix: Store original colors in the baseline dictionary alongside other baselines:

```python
        # In the baseline storage path:
        # Store original visual colors
        for body_name, body_id in simulator._body_ids.items():
            color_data = p.getVisualShapeData(
                body_id,
                physicsClientId=simulator._physics_client,
            )
            if color_data:
                self._baselines[simulator]["visual_colors"][body_name] = color_data[0][7]
```

Then apply offset relative to the baseline.

- [ ] **Step 3: Add test**

```python
def test_visual_randomization_preserves_original_colors():
    """Visual randomization must offset from original color, not hardcode 0.5."""
    from unittest.mock import MagicMock, patch
    from surg_rl.dynamics.parameter_randomizer import ParameterRandomizer
    from surg_rl.scene_definition.schema import DomainRandomizationConfig, VisualRandomization

    config = DomainRandomizationConfig(
        visual=VisualRandomization(
            enabled=True,
            color_r_offset=0.1,
        ),
    )
    randomizer = ParameterRandomizer(config)
    randomizer.start()
    randomizer.reset()

    simulator = MagicMock()
    simulator._physics_client = 0
    simulator._body_ids = {"robot": 1}

    mock_pb = MagicMock()
    mock_pb.getVisualShapeData.return_value = [(1, 0, 0, 0, 0, 0, 0, (0.9, 0.2, 0.3, 1.0))]
    mock_pb.getNumJoints.return_value = 0
    simulator._pb = mock_pb

    snapshot = randomizer.sample_parameters()
    randomizer.apply_parameters(snapshot, simulator)

    # The new color should be ~1.0 (0.9 + 0.1), not ~0.6 (0.5 + 0.1)
    called_color = mock_pb.changeVisualShape.call_args.kwargs.get("rgbaColor")
    assert called_color is not None
    assert abs(called_color[0] - 1.0) < 0.01, f"Expected ~1.0 but got {called_color[0]}"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dynamics.py::test_visual_randomization_preserves_original_colors -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/dynamics/parameter_randomizer.py tests/test_dynamics.py
git commit -m "fix: apply visual randomization offsets from actual colors, not 0.5"
```

---

### Task 3: Fix AdaptiveDifficultyController Dead Code

**Bug:** `_get_base_parameters` returns `mass_ratio_range`, `friction_range`, `texture_variation`, etc., but `apply_parameters` only handles `gravity_variation`. Other scaled parameters are never consumed.

**Files:**
- Modify: `src/surg_rl/dynamics/adaptive_difficulty.py`
- Test: `tests/test_dynamics.py`

- [ ] **Step 1: Find apply_parameters**

Run: `grep -n "def apply_parameters" src/surg_rl/dynamics/adaptive_difficulty.py`

- [ ] **Step 2: Extend apply_parameters to apply mass/friction/texture**

Add mass_ratio and friction application via simulator attributes or parameter passing:

```python
    def apply_parameters(self, snapshot, simulator):
        """Apply adaptive difficulty parameters."""
        try:
            # Gravity variation
            if "gravity_variation" in snapshot.physics:
                ...
            # Mass ratio
            if "mass_ratio" in snapshot.physics:
                mass_ratio = snapshot.physics["mass_ratio"]
                # Apply via simulator if supported
                if hasattr(simulator, "set_mass_ratio"):
                    simulator.set_mass_ratio(mass_ratio)
            # Friction
            if "friction" in snapshot.physics:
                friction = snapshot.physics["friction"]
                if hasattr(simulator, "set_friction"):
                    simulator.set_friction(friction)
            self._current_params = snapshot
            return True
        except Exception:
            return False
```

- [ ] **Step 3: Add test**

```python
def test_adaptive_difficulty_applies_mass_and_friction():
    """apply_parameters must apply mass_ratio and friction, not just gravity."""
    from unittest.mock import MagicMock
    from surg_rl.dynamics.adaptive_difficulty import AdaptiveDifficultyController, DifficultyConfig
    from surg_rl.dynamics.base_controller import ParameterSnapshot

    config = DifficultyConfig()
    controller = AdaptiveDifficultyController(difficulty_config=config)
    controller.start()
    controller.reset()

    snapshot = ParameterSnapshot(
        physics={"gravity_variation": 0.1, "mass_ratio": 1.2, "friction": 0.8},
        visual={}, dynamics={}, episode=1, step=0,
    )
    simulator = MagicMock()

    controller.apply_parameters(snapshot, simulator)

    # Should have attempted to apply mass_ratio and friction
    assert simulator.set_mass_ratio.called or simulator.set_friction.called, \
        "apply_parameters did not apply mass_ratio or friction"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dynamics.py::test_adaptive_difficulty_applies_mass_and_friction -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/dynamics/adaptive_difficulty.py tests/test_dynamics.py
git commit -m "fix: apply mass_ratio and friction in AdaptiveDifficultyController"
```

---

### Task 4: Fix PyBullet Gravity Retrieval in AdaptiveDifficulty

**Bug:** `apply_parameters` calls `p.getDynamicsInfo(0, -1, ...)` hoping to read gravity. `getDynamicsInfo` returns mass/friction data, not gravity.

**Files:**
- Modify: `src/surg_rl/dynamics/adaptive_difficulty.py`
- Test: `tests/test_dynamics.py`

- [ ] **Step 1: Find getDynamicsInfo usage**

Run: `grep -n "getDynamicsInfo" src/surg_rl/dynamics/adaptive_difficulty.py`

- [ ] **Step 2: Remove incorrect getDynamicsInfo call**

Remove the `getDynamicsInfo` call entirely. Gravity should be read from the scene definition or from a stored baseline, not from `getDynamicsInfo`.

Replace with:
```python
        # Default gravity
        current_gravity = [-9.81]  # Will be overridden by snapshot
```

Or better, read from simulator's stored scene definition if available:
```python
        if hasattr(simulator, "_scene_definition") and simulator._scene_definition is not None:
            if hasattr(simulator._scene_definition, "physics") and simulator._scene_definition.physics is not None:
                current_gravity = simulator._scene_definition.physics.gravity
            else:
                current_gravity = [0.0, 0.0, -9.81]
        else:
            current_gravity = [0.0, 0.0, -9.81]
```

- [ ] **Step 3: Add test**

```python
def test_adaptive_difficulty_gravity_without_getdynamicsinfo():
    """apply_parameters must not call getDynamicsInfo for gravity."""
    from unittest.mock import MagicMock
    from surg_rl.dynamics.adaptive_difficulty import AdaptiveDifficultyController, DifficultyConfig
    from surg_rl.dynamics.base_controller import ParameterSnapshot

    config = DifficultyConfig()
    controller = AdaptiveDifficultyController(difficulty_config=config)
    controller.start()
    controller.reset()

    snapshot = ParameterSnapshot(
        physics={"gravity_variation": 0.1},
        visual={}, dynamics={}, episode=1, step=0,
    )
    simulator = MagicMock()
    simulator._physics_client = 0
    mock_pb = MagicMock()
    mock_pb.getDynamicsInfo = MagicMock(side_effect=AssertionError("getDynamicsInfo should not be called for gravity"))
    simulator._pb = mock_pb
    simulator._scene_definition = None

    controller.apply_parameters(snapshot, simulator)
    mock_pb.getDynamicsInfo.assert_not_called()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_dynamics.py::test_adaptive_difficulty_gravity_without_getdynamicsinfo -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/dynamics/adaptive_difficulty.py tests/test_dynamics.py
git commit -m "fix: remove incorrect getDynamicsInfo call for gravity in AdaptiveDifficultyController"
```

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-24-dynamics-controller-fixes.md`.

**Execution options:**
1. **Subagent-Driven** — Dispatch fresh subagents per task
2. **Inline Execution** — Execute in this session

Which approach?
