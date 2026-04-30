# Phase 01-Critical-Bug-Fixes — Plan 01-02 Task 2: Curriculum Dynamics Parameter Application

## Objective
Fix `CurriculumScheduler.apply_parameters()` to stop silently dropping sampled **dynamics** parameters (`action_noise`, `joint_noise`, `delay`).

## What Changed

### `src/surg_rl/dynamics/curriculum.py`
- Added active dynamics parameter storage fields in `__init__`:
  - `_active_action_noise`
  - `_active_joint_noise`
  - `_active_delay`
- Extended `apply_parameters` with a **Dynamics** block that:
  1. Checks each of `action_noise`, `joint_noise`, `delay` in `snapshot.dynamics`
  2. Calls the simulator setter (e.g. `simulator.set_action_noise`) if it exists
  3. Falls back to logging a `debug` message and storing the value on the scheduler for downstream consumption
- Method still returns `True` on success and `False` only on unhandled exception.

### `tests/test_dynamics.py`
- Added `TestCurriculumScheduler.test_curriculum_applies_dynamics_params`:
  - Creates a `ParameterSnapshot` with `physics={"gravity_x": 0.0}` and `dynamics={"action_noise": 0.05}`
  - Uses a mock simulator that only exposes `setGravity`
  - Asserts:
    - `simulator.setGravity.called`
    - `scheduler._active_action_noise == 0.05`

## Test Execution
```text
$ PYTHONPATH=src pytest tests/test_dynamics.py -k "curriculum" -x -q
20 passed, 47 deselected

$ PYTHONPATH=src pytest tests/test_dynamics.py -x -q
67 passed in 0.06s
```

## Commit
`fix(phase-01-02): apply curriculum dynamics overrides in apply_parameters`
