# Pitfalls Research

**Domain:** Surgical-robotics reinforcement learning training system
**Researched:** 2026-04-29
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: PyBullet Quaternion Order Bug

**What goes wrong:** Primitive robot fallbacks in PyBullet are silently mis-oriented because `createMultiBody` expects `[x, y, z, w]` but the code passes `[w, x, y, z]`. This means any scene relying on primitive robot geometry has incorrect orientation.

**Why it happens:** MuJoCo and PyBullet use different quaternion conventions. The MuJoCo convention (`[w, x, y, z]`) leaked into PyBullet primitive creation.

**How to avoid:** Audit all quaternion handoff points. Use namedtuple or dataclass with clear field names (`qx, qy, qz, qw`). Add unit tests that verify orientation after `reset()`.

**Warning signs:** Robots appear rotated 90° in PyBullet but correct in MuJoCo. Tests pass orientation checks on MuJoCo but fail on PyBullet.

**Phase to address:** Phase 1 (Critical Bugs) — this is a correctness bug affecting all PyBullet users.

---

### Pitfall 2: Simulator State Leakage Between Episodes

**What goes wrong:** PyBullet `reset()` never resets joint positions/velocities. The next episode starts with stale joint state from the previous episode, biasing training data.

**Why it happens:** `pybullet_simulator.py:reset()` only resets base poses but skips `resetJointState` calls for all movable joints.

**How to avoid:** Every `reset()` must iterate all joints and call `resetJointState` with initial qpos/qvel. Add a regression test that asserts zero joint velocity after reset.

**Warning signs:** Training loss plateaus unexpectedly. Agent actions have diminishing effect over episodes.

**Phase to address:** Phase 1 (Critical Bugs) — this corrupts RL training data silently.

---

### Pitfall 3: Collision Penalty Sign Inversion

**What goes wrong:** The reward function factory uses `abs()` to guard negative weights, but the root cause is that `RewardConfig` allows negative config values to be passed as positive weights. This inverts the intended penalty into a bonus.

**Why it happens:** Sign contract between config schema and reward factory is unclear. `RewardConfig` has no validator ensuring `collision_penalty >= 0`.

**How to avoid:** Add Pydantic validators to `RewardConfig` that reject negative penalty values. Make the factory fail fast on invalid signs instead of silently patching with `abs()`.

**Warning signs:** Agent learns to collide (higher reward) rather than avoid collisions. `CollisionPenalty` tests may not catch this if only the weight sign is tested, not the composite behavior.

**Phase to address:** Phase 1 (Critical Bugs) — this breaks reward semantics.

---

### Pitfall 4: VecEnv API Mismatch in Evaluation

**What goes wrong:** `TrainingManager.evaluate()` assumes 5-tuple Gymnasium `step()` API (`obs, reward, terminated, truncated, info`) but SB3 `VecEnv` returns 4-tuple (`obs, reward, done, info`). This crashes when `n_envs > 1`.

**Why it happens:** `evaluate()` was tested only with `DummyVecEnv(n_envs=1)` where the 4-tuple/5-tuple behavior coincides. No multi-env evaluation tests exist.

**How to avoid:** Detect env type (`isinstance(env, VecEnv)`) and branch accordingly. Add integration tests that evaluate with `n_envs=2`.

**Warning signs:** Crash on `evaluate()` after training with multiple workers. Error: `_queue.Empty` or tuple unpack failure.

**Phase to address:** Phase 1 (Critical Bugs) — this breaks multi-environment evaluation.

---

### Pitfall 5: PyBullet Soft-Body Scene Reload Cost

**What goes wrong:** `PyBulletSimulator.reset()` reloads the entire scene when soft bodies exist because `removeBody()` is unsafe for soft bodies. This is O(n) per episode and becomes a bottleneck at scale.

**Why it happens:** PyBullet soft-body API lacks a safe remove operation. The workaround (full reload) is correct but expensive.

**How to avoid:** Cache soft-body mesh data in memory to avoid re-reading `.vtk`/`.obj` files. Use PyBullet's `changeDynamics()` to reset soft-body state without reloading. If neither works, document the limitation and provide a "rigid tissue" mode.

**Warning signs:** Episode time increases linearly with scene complexity. `reset()` dominates profiling output.

**Phase to address:** Phase 3 (Simulator Robustness) — optimization, not correctness.

---

### Pitfall 6: Unimplemented Action Types Surviving to Runtime

**What goes wrong:** `ActionBuilder` defines `JOINT_TORQUES`, `ENDEFFECTOR_POSE`, `ENDEFFECTOR_DELTA` but they raise `NotImplementedError` at runtime. Users configuring these action types get cryptic crashes.

**Why it happens:** Early alpha placeholders that were never prioritized. No validation blocks them at config time.

**How to avoid:** Add a Pydantic validator to `ActionConfig` that rejects unsupported `ActionType` values. Or implement them. Either way, fail at scene load time, not during `step()`.

**Warning signs:** User reports "my config is valid but training crashes on step 1."

**Phase to address:** Phase 2 (Gripper + Action Types) — complete the action space.

---

### Pitfall 7: API Key Exposure via `.env.example`

**What goes wrong:** `.env.example` contains `LLM_API_KEY=your_api_key_here`. Users copy it without replacing the placeholder, and the literal string leaks to LLM provider error logs.

**Why it happens:** No validation that the key is non-empty or a real-looking key before use. No masking in logs.

**How to avoid:** Replace `.env.example` with `LLM_API_KEY=` (empty). Add validator in `Settings` that rejects placeholder values. Mask key in all logs (only show last 4 chars).

**Warning signs:** Anthropic/OpenAI error logs contain literal `"your_api_key_here"`. Security audit flags credential exposure.

**Phase to address:** Phase 1 (Critical Bugs) — security.

---

### Pitfall 8: Curriculum `apply_parameters` No-Op

**What goes wrong:** `CurriculumScheduler.apply_parameters()` returns `True` without actually applying stage overrides. The curriculum advances, but the simulation parameters never change.

**Why it happens:** The method was stubbed during early implementation and never completed. Since it returns `True`, no test catches it as a failure.

**How to avoid:** Implement the override logic (stage → parameter mapping). Add a test that asserts a parameter value changes after `apply_parameters()`.

**Warning signs:** Agent trains at the same difficulty regardless of curriculum stage. Success rate doesn't improve as expected.

**Phase to address:** Phase 3 (Simulator Robustness) — dynamics layer gap.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Primitive mesh fallbacks | No asset licensing, lightweight repo | Low visual fidelity, no realistic tissue | v1 only; replace with real meshes in v2 |
| `hasattr` backend detection | Simple, no enums needed | Breaks if backend internals change | v1; add `BackendType` enum in v2 |
| `abs()` in reward factory | Prevents crash on bad config | Hides sign contract violations | Never — fix root cause in config validators |
| Unimplemented action types in enum | Future-proof API | Runtime crashes for users | Never — either implement or remove from enum |
| `.env.example` with placeholder | Self-documenting template | Security exposure | Never — use empty value + validator |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Ollama local server | Forget to start Ollama before running `surg-rl generate` | Check connection in `generate` command; warn user if unreachable |
| MuJoCo renderer | Call `render()` in headless environment without checking `DISPLAY` | Check `mujoco.Renderer` availability; degrade to no-render mode |
| PyBullet soft body | Load soft body before `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` | Always call `resetSimulation` with deformable flag first |
| SB3 `VecEnv` | Use `env.step()` directly with `SubprocVecEnv` | Use SB3's `make_vec_env()` helper; handle 4-tuple vs 5-tuple |
| Pydantic `model_dump()` | Serialize to YAML without converting enums | Use `model_dump(mode="json")` first; then pass to `yaml.dump` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| ASCII VTK writer | Scene save takes seconds for large meshes | Switch to binary VTK or skip ASCII intermediate | Soft-body scenes with >10k tetrahedra |
| Python loop mesh generation | Procedural mesh creation stalls for high-res shapes | Vectorize with NumPy or use trimesh | Resolutions >64³ cells |
| Synchronous rendering | Training loop blocked by `render()` calls | Use offscreen renderer; decouple render from step | Any training with `render_freq > 0` |
| Fresh env per evaluation | `evaluate()` creates new env each call | Reuse vectorized env across evaluations | Evaluation frequency >0 with `n_envs > 1` |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| API key in `.env.example` | Leaks to logs, version control | Empty value + validator + log masking |
| No key validation | Placeholder sent to providers, causing billing surprises | Regex validate key format per provider |
| Key in error messages | Anthropic/OpenAI exceptions include key in traceback | Sanitize exceptions before logging |
| No rate limiting | Accidental infinite loop in generation exhausts API budget | Add built-in rate limit (max requests/minute) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Static demos | Demo shows nothing moving; user thinks it's broken | Add animated primitive movement or document "joint control not yet implemented" |
| `NotImplementedError` at runtime | User's config passes validation but crashes on first step | Validate action types at config load time |
| No progress indicator during training | Long training looks frozen | Add SB3 callback with Rich progress bar |
| Missing assets silently fail | Scene loads with boxes instead of robot mesh | Warn user: "Mesh X not found; using primitive fallback" |

## "Looks Done But Isn't" Checklist

- [ ] **Gripper actuation:** TODO comment exists at `pybullet_simulator.py:1094`; not implemented
- [ ] **Joint control in demos:** README says "objects remain static" — true but not obvious to new users
- [ ] **Action types:** 3 of 6 action types raise `NotImplementedError`
- [ ] **Task geometry binding:** Observation fields (`needle_pos`, `entry_point`) are stubs
- [ ] **Curriculum apply_parameters:** Returns `True` but does nothing
- [ ] **evaluate() with VecEnv:** Only tested with `n_envs=1`
- [ ] **PyBullet state restore:** `get_state()` stores less than MuJoCo; not equivalent across backends
- [ ] **Soft-body remove safety:** `removeBody()` unsafe; workaround is full scene reload

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Quaternion order bug | LOW | Swap quaternion component order in `pybullet_simulator.py:195-200`. Add regression test. |
| State leakage | LOW | Add `resetJointState` loop in `reset()`. Test zero velocity after reset. |
| Collision sign | LOW | Add Pydantic validator. Remove `abs()` from factory. Fix existing configs. |
| VecEnv evaluate | MEDIUM | Handle 4-tuple in `evaluate()`. Add multi-env integration test. |
| Soft-body reload | MEDIUM | Cache mesh data. Explore `changeDynamics` reset. Document limitation. |
| Unimplemented actions | MEDIUM | Implement or remove from enum. Add config-time validation. |
| API key exposure | LOW | Change `.env.example`. Add validator. Mask logs. |
| Curriculum no-op | LOW | Implement parameter mapping. Add test for value change. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Quaternion order bug | Phase 1 | Run all simulator tests on PyBullet; verify orientation correctness |
| State leakage | Phase 1 | Regression test: reset → assert zero joint velocity |
| Collision sign | Phase 1 | Test that `CollisionPenalty` produces negative reward with positive config |
| VecEnv evaluate | Phase 1 | Integration test with `SubprocVecEnv(n_envs=2)` |
| API key exposure | Phase 1 | Security scan: grep logs for key patterns |
| Unimplemented actions | Phase 2 | Test all `ActionType` values with real simulator |
| Gripper actuation | Phase 2 | Demo shows gripper closing/opening |
| Soft-body reload | Phase 3 | Benchmark `reset()` time; target <100ms |
| Curriculum no-op | Phase 3 | Test parameter delta after curriculum advance |
| Task geometry binding | Phase 4 | E2E test with suturing scene; assert needle_pos observation |

## Sources

- `CONCERNS.md` (codebase map) — 39 documented gaps and critical bugs
- `BUGFIX_LOG.md` — 24 historical bug commits
- `docs/superpowers/plans/` — 5 unexecuted fix plans (critical bugs, simulator robustness, RL pipeline, dynamics, scene-gen CLI)
- PyBullet forums — quaternion convention and soft-body API limitations
- MuJoCo forums — `mjOBJ_FLEX` experimental status
- AGENTS.md — testing conventions and field guard notes

---
*Pitfalls research for: surgical-robotics RL training system*
*Researched: 2026-04-29*
