# RL Training Pipeline Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Fix RL training, environment, observation, action, and callback bugs.

**Architecture:** Each fix is localized to one file.

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/surg_rl/rl/environment.py` | Gymnasium env: seeding, target, observation randomization |
| `src/surg_rl/rl/observation.py` | Observation builder: unseeded noise, segmentation dtype, depth shape |
| `src/surg_rl/rl/action.py` | Action builder: TANH scaling, relative actions, DISCRETE |
| `src/surg_rl/rl/callbacks.py` | SB3 callbacks: checkpoint/eval for off-policy algorithms |
| `src/surg_rl/rl/training.py` | TrainingManager: uppercase algorithm names, unused tb_log |

---

### Task 1: Fix SurgicalEnv Seeding with np.random

**Bug:** `reset()` calls `super().reset(seed=seed)` correctly but then poisons global RNG with `np.random.seed(seed)` and uses `np.random.uniform(...)`.

**Files:**
- Modify: `src/surg_rl/rl/environment.py`
- Test: `tests/test_rl.py`

- [ ] **Step 1: Read reset()**

Run: `grep -n "def reset" src/surg_rl/rl/environment.py`

- [ ] **Step 2: Replace np.random with self.np_random**

Find all uses of `np.random.uniform`, `np.random.normal`, etc. in `environment.py` and replace with `self.np_random.uniform`, `self.np_random.normal`.

- [ ] **Step 3: Add test**

```python
def test_env_seeding_is_reproducible():
    """Seeded envs must produce identical target positions."""
    from unittest.mock import MagicMock, patch
    from surg_rl.rl.environment import SurgicalEnv, SurgicalEnvConfig

    config = SurgicalEnvConfig(
        scene_path="scenes/minimal_scene.json",
        seed=42,
    )
    # Mock simulator to avoid loading scene
    with patch("surg_rl.rl.environment.MuJoCoSimulator") as MockSim:
        sim = MagicMock()
        sim.get_observation.return_value = MagicMock(
            robot_state=np.zeros(7),
            end_effector_pos=np.array([0.0, 0.0, 0.0]),
            end_effector_quat=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        MockSim.return_value = sim

        env1 = SurgicalEnv(config)
        env2 = SurgicalEnv(config)

        obs1, info1 = env1.reset(seed=42)
        obs2, info2 = env2.reset(seed=42)

        assert np.allclose(obs1["target_pos"], obs2["target_pos"])
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_rl.py::test_env_seeding_is_reproducible -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/rl/environment.py tests/test_rl.py
git commit -m "fix: use self.np_random instead of global np.random in SurgicalEnv"
```

---

### Task 2: Fix Unseeded Noise in Observation Builder

**Bug:** `extract_observation()` applies Gaussian noise with `np.random.normal(...)` instead of a seeded RNG.

**Files:**
- Modify: `src/surg_rl/rl/observation.py`
- Test: `tests/test_rl.py`

- [ ] **Step 1: Find extract_observation noise**

Run: `grep -n "np.random.normal" src/surg_rl/rl/observation.py`

- [ ] **Step 2: Add seeded RNG to ObservationBuilder**

In `__init__`, add:
```python
        self._rng = np.random.default_rng(seed=0)
```

Add a `seed` parameter or setter:
```python
    def seed(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed=seed)
```

Replace `np.random.normal(...)` with `self._rng.normal(...)`.

- [ ] **Step 3: Add test**

```python
def test_observation_noise_is_reproducible():
    """Observation noise must be reproducible with the same seed."""
    from surg_rl.rl.observation import ObservationBuilder, ObservationConfig

    config = ObservationConfig()
    builder = ObservationBuilder(config=config)
    builder.seed(42)

    obs = MagicMock()
    obs.robot_state = np.array([1.0, 2.0, 3.0])
    obs.end_effector_pos = np.array([0.1, 0.2, 0.3])
    obs.end_effector_quat = np.array([1.0, 0.0, 0.0, 0.0])
    obs.force_torque = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    obs.tissue_state = {}

    spec = builder._specs[0]
    result1 = builder._apply_noise(spec, np.array([1.0, 2.0, 3.0]))

    builder.seed(42)
    result2 = builder._apply_noise(spec, np.array([1.0, 2.0, 3.0]))

    assert np.allclose(result1, result2)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_rl.py::test_observation_noise_is_reproducible -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/rl/observation.py tests/test_rl.py
git commit -m "fix: use seeded RNG for observation noise instead of np.random"
```

---

### Task 3: Fix TANH Action Scaling

**Bug:** `process_action()` applies `np.tanh(action)` but never maps `(-1, 1)` to actual action-space bounds `[low, high]`.

**Files:**
- Modify: `src/surg_rl/rl/action.py`
- Test: `tests/test_rl.py`

- [ ] **Step 1: Find process_action**

Run: `grep -n "process_action" src/surg_rl/rl/action.py`

- [ ] **Step 2: Add proper TANH mapping**

In `process_action()`, in the `TANH` branch, after `np.tanh(action)`, add mapping:

```python
        if self.config.scaling == ActionScaling.TANH:
            action = np.tanh(action)
            # Map from (-1, 1) to (low, high)
            low, high = self.get_action_space().low, self.get_action_space().high
            action = low + (action + 1.0) / 2.0 * (high - low)
```

- [ ] **Step 3: Add test**

```python
def test_tanh_scaling_maps_to_action_bounds():
    """TANH scaling must map (-inf, inf) input to actual action bounds."""
    from surg_rl.rl.action import ActionBuilder, ActionConfig, ActionScaling
    import numpy as np

    config = ActionConfig(scaling=ActionScaling.TANH)
    builder = ActionBuilder(config=config)
    space = builder.get_action_space()

    # Large input values should be squashed to bounds
    action = np.ones(space.shape) * 10.0
    scaled = builder.process_action(action)

    assert np.all(scaled >= space.low - 1e-6)
    assert np.all(scaled <= space.high + 1e-6)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_rl.py::test_tanh_scaling_maps_to_action_bounds -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/rl/action.py tests/test_rl.py
git commit -m "fix: map TANH-scaled actions to actual action-space bounds"
```

---

### Task 4: Fix CheckpointCallback for Off-Policy Algorithms

**Bug:** `CheckpointCallback` and `EvaluationCallback` use `locals_dict.get("num_collected_steps", 0)` which only exists in on-policy algorithms. For SAC/TD3/DDPG, the key is absent, so step is always 0.

**Files:**
- Modify: `src/surg_rl/rl/callbacks.py`
- Test: `tests/test_rl.py`

- [ ] **Step 1: Find num_collected_steps usage**

Run: `grep -n "num_collected_steps" src/surg_rl/rl/callbacks.py`

- [ ] **Step 2: Use self.num_timesteps instead**

Replace:
```python
        locals_dict = self.locals
        step = locals_dict.get("num_collected_steps", 0)
```

With:
```python
        step = self.num_timesteps
```

In both `CheckpointCallback` and `EvaluationCallback`.

- [ ] **Step 3: Add test**

```python
def test_checkpoint_callback_uses_self_num_timesteps():
    """CheckpointCallback must use self.num_timesteps, not locals."""
    from unittest.mock import MagicMock, patch
    from surg_rl.rl.callbacks import CheckpointCallback

    callback = CheckpointCallback(save_freq=100, save_path="/tmp")
    callback.num_timesteps = 200
    callback.locals = {}  # Empty locals simulates off-policy

    with patch.object(callback, "_save_model") as mock_save:
        callback._on_step()
        mock_save.assert_called_once()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_rl.py::test_checkpoint_callback_uses_self_num_timesteps -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/rl/callbacks.py tests/test_rl.py
git commit -m "fix: use self.num_timesteps in CheckpointCallback and EvaluationCallback"
```

---

### Task 5: Fix Algorithm Name Case Consistency

**Bug:** `_create_model` uses `algo_config.name.upper() in ("PPO", "A2C")` but then `algo_config.name in ("SAC", ...)` for off-policy. Per project rules, names should always be compared uppercase.

**Files:**
- Modify: `src/surg_rl/rl/training.py`
- Test: `tests/test_rl.py`

- [ ] **Step 1: Find algorithm branching**

Run: `grep -n 'algo_config.name' src/surg_rl/rl/training.py`

- [ ] **Step 2: Make off-policy comparison uppercase**

Replace:
```python
        elif algo_config.name in ("SAC", "TD3", "DDPG"):
```

With:
```python
        elif algo_config.name.upper() in ("SAC", "TD3", "DDPG"):
```

- [ ] **Step 3: Add test**

```python
def test_algorithm_name_case_insensitive():
    """Algorithm names must be compared case-insensitively."""
    from surg_rl.rl.training import TrainingManager, TrainingConfig, AlgorithmConfig
    from unittest.mock import MagicMock, patch

    config = TrainingConfig(
        scene_path="scenes/minimal_scene.json",
        algorithm=AlgorithmConfig(name="sac"),  # lowercase
        total_timesteps=100,
    )
    manager = TrainingManager(config)

    env = MagicMock()
    env.observation_space = MagicMock()
    env.action_space = MagicMock()

    with patch("surg_rl.rl.training.SAC") as MockSAC:
        MockSAC.return_value = MagicMock()
        manager._create_model(env)
        MockSAC.assert_called_once()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_rl.py::test_algorithm_name_case_insensitive -v`

- [ ] **Step 5: Commit**

```bash
git add src/surg_rl/rl/training.py tests/test_rl.py
git commit -m "fix: compare algorithm names uppercase consistently"
```

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-04-24-rl-pipeline-fixes.md`.

**Execution options:**
1. **Subagent-Driven** — Dispatch fresh subagents per task
2. **Inline Execution** — Execute in this session

Which approach?
