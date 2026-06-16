---
status: resolved
trigger: "the full ppo training demo does not work, throws error as follows: ... ValueError: Error: more than 6 dofs in body 'surgical_arm_1' Element name 'surgical_arm_1', id 1, line 12 ... RuntimeError: Failed to load MuJoCo model: Error: more than 6 dofs in body 'surgical_arm_1' Element name 'surgical_arm_1', id 1, line 12"
created: 2026-06-14
updated: 2026-06-14
---

# Debug Session: ppo-demo-mujoco-dof-limit

## Symptoms

**Expected behavior:** PPO training demo runs to completion, training a model on the suturing_demo.json scene.

**Actual behavior:** Demo crashes at training start with `RuntimeError: Failed to load MuJoCo model: Error: more than 6 dofs in body 'surgical_arm_1'`.

**Error trace:**
```
Failed to load MuJoCo model: Error: more than 6 dofs in body 'surgical_arm_1'
Element name 'surgical_arm_1', id 1, line 12
  File ".../simulators/mujoco_simulator.py", line 159, in load_scene
    self._model = self._mujoco.MjModel.from_xml_path(str(self._mjcf_path))
ValueError: Error: more than 6 dofs in body 'surgical_arm_1'
```

Stack: `demos/demo.py:411 main() → run_training() → manager.train() → _create_environment() → SurgicalEnv.__init__() → simulator.load_scene() → mujoco.MjModel.from_xml_path() → ValueError`

**Timeline:** Discovered 2026-06-14. Demo had been verified at small step counts (200 timesteps on a different scene) in an earlier session, but the default-args run (100k steps, suturing_demo.json) crashes on scene load.

**Reproduction:**
```bash
PYTHONPATH=src python demos/demo.py --headless
# (or: --headless --steps 100000)
```

**Pre-crash warnings (also visible in log):**
- `Missing assets for scene scenes/suturing_demo.json: ['Robot URDF: assets/robots/surgical_arm.urdf', 'Instrument mesh: assets/instruments/suturing_needle.obj']`
- `Asset missing for 'surgical_arm_1': assets/robots/surgical_arm.urdf. Using primitive fallback.`
- `trimesh not installed — using primitive fallback for instrument 'curved_suturing_needle'`

## Current Focus

hypothesis: confirmed — see Evidence. Root cause is in `src/surg_rl/simulators/scene_builder.py` lines 616-672 (`_add_robot_to_mjcf`): all of `robot.joints` and the gripper `end_effectors` joint are added as direct children of a single `<body>` element. With 7 revolute joints + 1 gripper slide joint from the failing scene, that body gets 8 DOFs and MuJoCo rejects it (max 6 per body).
test: applied (Evidence section) — generated MJCF shows 8 joints on one body for suturing_demo.json; simple_suturing.json (no `joints` field, falls to default 1-joint path) shows 2 joints and works.
expecting: confirmed. Now applying fix: nest joints across multiple child `<body>` elements so each body has ≤ 6 DOFs.
next_action: apply fix in `_add_robot_to_mjcf`, then verify `demos/demo.py --headless --steps 200` runs without the crash, then full default `--steps 100000`.

## Evidence

- timestamp: 2026-06-14
  checked: `PYTHONPATH=src python demos/demo.py --headless --steps 100`
  found: Reproduced crash at `mujoco_simulator.py:159` with `ValueError: Error: more than 6 dofs in body 'surgical_arm_1'` at line 12
  implication: bug is deterministic for the default-args invocation

- timestamp: 2026-06-14
  checked: `src/surg_rl/simulators/scene_builder.py` lines 583-679 (`_add_robot_to_mjcf`)
  found: Single `<body name="surgical_arm_1">` (line 606) gets ALL `robot.joints` added as direct children (lines 616-627) AND the gripper slide joint from `end_effectors` (lines 663-672). No nesting — every joint is a sibling under the same body.
  implication: any scene with > 5 joints in `robot.joints` will trip the 6-DOF limit (after the gripper is added)

- timestamp: 2026-06-14
  checked: generated MJCF for `scenes/suturing_demo.json` (8 joints: joint_1..joint_7 hinges + gripper slide) vs `scenes/simple_suturing.json` (2 joints: default hinge + gripper slide)
  found: Failing scene has 7 revolute joints listed in `robot.joints` plus 1 end_effector → 8 joints emitted on one body. Working scene has zero `joints` field → falls through to default 1-joint path (line 628-638) → only 2 joints on the body.
  implication: differential confirmed — scenes with no `joints` field work; scenes with explicit 7-DOF `joints` field crash

- timestamp: 2026-06-14
  checked: `scenes/suturing_demo.json` line 78 `urdf_path: "assets/robots/surgical_arm.urdf"`
  found: URDF is missing (no such file in repo per AGENTS.md), so scene_builder takes the primitive-fallback path. The error is the primitive-fallback generator, not the URDF loader.
  implication: even when a real URDF existed, the primitive fallback path is still wrong and must be fixed

- timestamp: 2026-06-14
  checked: MuJoCo's per-body DOF constraint
  found: MuJoCo rejects any body with > 6 DOF joints; common workaround is to chain bodies so each child body inherits the parent's transform but carries its own ≤ 6 DOFs
  implication: fix must split joints across nested `<body>` elements

## Eliminated

(none yet)

## Resolution

**Root cause:** In `src/surg_rl/simulators/scene_builder.py` `_add_robot_to_mjcf`, all `robot.joints` plus the gripper slide joint (added when `end_effectors` is non-empty) were emitted as direct children of a single `<body>` element. `scenes/suturing_demo.json` declares 7 revolute joints and 1 end_effector → 8 DOFs on one body. MuJoCo rejects any body with more than 6 DOFs, raising `ValueError: more than 6 dofs in body 'surgical_arm_1'`.

**Fix:** When the total DOF count (regular joints + gripper slide) exceeds 6, the builder now chains the joints across nested child `<body>` elements. Joints are split into chunks of 5 (leaving room for the gripper slide in the last chunk), and each chunk lives on its own body. Intermediate chain bodies are kinematic anchors with a tiny `<inertial>` (mass 1e-3, diaginertia 1e-6) so MuJoCo's `mjMINVAL` mass check passes. The root body still owns the visual `<geom>` and base pose. The flat structure is preserved for the common ≤6 DOF case.

**Verification:**
- `demos/demo.py --headless --steps 200` no longer crashes; training actually starts (SB3 emits "Wrapping the env with a `Monitor` wrapper" and "Wrapping the env in a DummyVecEnv") and reaches "Demo complete".
- `demos/demo.py --headless --steps 1000` (closer to the default 100k) starts training successfully.
- `--scene scenes/simple_suturing.json` still works (2-DOF robot stays flat under the new path).
- All 1126 unit tests pass (no regressions). Three new regression tests in `tests/test_scene_builder.py::TestRobotDofSplitting` cover the 7-DOF case, the chain-body emission, and the flat structure preserved for ≤6 DOF.
- `ruff check` shows no new errors from the change (one pre-existing unused-variable error at line 1026 was already present on main).

**Files changed:**
- `src/surg_rl/simulators/scene_builder.py` — `_add_robot_to_mjcf` now chains joints across nested bodies when total DOFs > 6
- `tests/test_scene_builder.py` — added `TestRobotDofSplitting` with 3 regression tests

---

## Follow-up: ppo-demo-mujoco-qacc-nan (commit 36ccf6d)

After commit (8ea74e9) the DOF-limit error was gone, but every step still
emitted `WARNING: Nan, Inf or huge value in QACC at DOF 0` followed by
`NaN detected in simulation state` termination. The DOF split alone was
not enough — the kinematic structure was still rank-deficient.

**Two new contributors identified:**

1. **Rank deficiency from co-axial hinges.** The chunked structure put
   5 hinges on one body and 3 on the chain body, all with `axis="0 1 0"`.
   Even with one body per joint, identical-axis hinges at zero offset
   are kinematically degenerate. Reproduced in isolation: 5 hinges on a
   single box body with all-zero controls → QACC NaN on the first step
   under any integrator.
2. **Actuator type ignored `control_mode`.** The builder always emitted
   `<motor gear=100>`. The env's `(-π, π)` action is meant to be a joint
   position setpoint, but `<motor>` treats `data.ctrl` as a generalized
   force → `force = 100·π ≈ 314 N·m` per step on a 1 mg body. Even after
   the chain body was added, kp=100 with the same body inertia still
   produced QACC NaN.
3. **`<option>` ignored `PhysicsConfig`.** `integrator` and
   `solver_iterations` from the scene JSON were not forwarded. MuJoCo
   fell back to Euler + Newton defaults.

**Final fix (commit 36ccf6d):**

- Restructured the primitive fallback to always emit a kinematic chain
  of nested bodies — **one body per joint** — instead of chunking
  multiple joints onto a single body. This makes the kinematic tree
  rank-independent of the joint count.
- Joint axes cycle through `[0 0 1, 0 1 0, 1 0 0, 0 1 0, 0 0 1, 1 0 0]`
  so adjacent hinges are never parallel.
- Each link body has `<inertial mass="0.05" diaginertia="1e-4 1e-4 1e-4">`.
  Root body has `<inertial mass="1.0" diaginertia="1e-2 1e-2 1e-2">`
  to feel anchored.
- Actuator type now depends on `robot.control_mode`:
  - `position` → `<position kp=10 ctrlrange=...>`
  - `velocity` → `<velocity kv=5  ctrlrange=...>`
  - `torque` / `effort` (or unset) → `<motor gear=100>` (backward compat)
- `<option>` now includes `integrator` and `iterations` (MuJoCo's
  attribute name; not `solver_iterations`) from `PhysicsConfig`.

**Verification:**
- `demos/demo.py --headless --steps 1000` — completes; no QACC NaN
  warnings; mean reward ~22M; episodes last the full 2000 steps.
- `demos/demo.py --scene scenes/simple_suturing.json --headless --steps 200`
  — backward compatible.
- Full test suite: **1131 passed, 14 skipped** (was 1126; +5 new tests
  covering the chain structure and control-mode actuators).
- New `TestControlModeActuators` with 4 tests for `position`, `torque`,
  `velocity` actuator types and `<option>` field forwarding.
