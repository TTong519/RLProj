# Feature Research

**Domain:** Surg-RL v0.6.0 — Carried-Forward Tech-Debt Closure (4 items)
**Researched:** 2026-06-24
**Confidence:** HIGH (in-repo context for 3 of 4 items); MEDIUM for DreamerV3 real-integration API surface (external `dreamerv3` package, JAX)

## Scope Note

This is a **closure milestone**, not a feature milestone. The "feature landscape" below is scoped strictly to the four deferred items carried forward from v0.4.0–v0.5.0. Already-built features (DifficultyLevel enum, TaskRewardRouter, interpolate_params, additive CurriculumScheduler, DreamerV3 subprocess spike, 2D PhiFlow fluids, K8s manifests) are treated as fixed dependencies and are NOT re-researched.

---

## Feature Landscape

### Item 1: Real DreamerV3 Integration (flip the `_build_agent` stub)

The Phase 24 subprocess (`src/surg_rl/dreamer/subprocess.py`) currently returns `None` from `_build_agent`, `_train_loop` yields a single zero-metric dict, `_evaluate` returns zeros, and `_save_checkpoint`/`_load_checkpoint` are `pass`. The Phase 30 E2E test asserts the resulting `RuntimeError("Agent not configured")` as a sentinel — that test must flip to assert positive completion when the stub is replaced.

#### Table Stakes (closure item must deliver)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Real `_build_agent(config)` returning a live agent | The subprocess exists only to host a real agent; `None` is the debt | HIGH | Wire `dreamerv3` (danijar JAX, PyPI v1.5.0) or `nm512/dreamerv3-torch`. Agent built from DreamerConfig dict; must respect `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` already set. |
| World-model + actor-critic training step | DreamerV3 learns a world model (RSSM) then trains actor-critic from imagined rollouts — a `train_step` that only updates one is not DreamerV3 | HIGH | `agent.train(batch)` drives both; `_train_loop` must yield real `loss`, `reconstruction_loss`, `reward_loss` per step, not the current single zero yield. |
| Checkpoint save/load round-trip | Auto-discovery from `models/dreamerv3/{task}_{obs_type}/` already exists in the parent; the subprocess side must actually persist and restore agent + optimizer + replay state | MEDIUM | `dreamerv3` saves to `--logdir`; resume = same logdir. Subprocess must translate `path` arg → agent save/load. |
| Eval reporting (`_evaluate`) | DMV3-01 feasibility thresholds (MSE < 0.01, reward MAE < 0.5) are already in the contract | MEDIUM | Return real `reconstruction_mse`, `reward_mae`, `success_rate` over `n_episodes`. |
| Flip the Phase 30 sentinel test | The E2E test currently asserts `RuntimeError` — it MUST start failing when real integration lands, and be rewritten to assert positive completion | LOW | Sentinel flip is the closure signal; macOS still skipif (no GPU), CI GPU host runs. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Pixel (64×64 RGBA) AND state obs modes both work end-to-end | The subprocess already declares both modes; only pixel is spike-validated | MEDIUM | GymToEmbodiedWrapper already adapts; verify state path trains (not just pixel). |
| Imagination-based actor-critic (not SB3 policy gradient) | This is the whole point of DreamerV3 vs PPO/SAC — world-model-imagined training | HIGH | Inherent to the `dreamerv3` package; just must not be bypassed. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Replacing the SB3 stack with DreamerV3 | "One RL framework to rule them all" | Breaks 6-task benchmarking, MARL, and 1,325 passing tests; DreamerV3 is research spike, not default | Keep DreamerV3 process-isolated; SB3 stays default |
| 3D video prediction for DreamerV3 | "Match the 3D fluid work" | Explicitly Out of Scope (PROJECT.md); 2D pixel reconstruction is the feasibility assessment | 2D pixel obs only |
| Training DreamerV3 from recorded demos (DMV3-06) | Useful but v2 | Requires offline dataset infrastructure not in this milestone | Defer to v2 as already decided |
| `r2dreamer` (PyTorch, ~5x faster) | Faster than `nm512/dreamerv3-torch` | Newer, less battle-tested; JAX path already chosen for process isolation + XLA memory fraction | Stick with danijar/dreamerv3 (JAX) per existing architecture decision |

### Item 2: TASK-02 Per-Level Difficulty Schema

The v0.4.2 build delivered the `DifficultyLevel` enum + `get_params_for_difficulty()` wrappers + `TaskConfig.difficulty_level` field, but three D-29-03 exclusions remain: (a) `DifficultyLevelConfig` override model, (b) discrete `CurriculumScheduler` level progression EASY→MEDIUM→HARD, (c) scene-level `difficulty_blocks: list[3]` in scene JSON.

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `DifficultyLevelConfig` Pydantic v2 model with `tissue_stiffness / target_precision_tolerance / tool_position_noise / time_limit` overrides | Named per-level overrides are more maintainable than positional float interpolation; this is the documented D-29-03 exclusion | MEDIUM | Optional fields with `None` defaults (schema-first pattern). Applied additively over `interpolate_params()` — never replace the Phase 3/21 fix. |
| Discrete curriculum progression (EASY→MEDIUM→HARD) | Continuous float difficulty already exists; discrete steps are the missing half | MEDIUM | `CurriculumScheduler` currently additive over continuous float. Add a discrete mode that advances `DifficultyLevel` enum on `success_threshold` met, preserving continuous path for backward compat. |
| Scene-level `difficulty_blocks: list[3]` in scene JSON | Lets a scene author express EASY/MEDIUM/HARD variants inline rather than 3 scene files | MEDIUM | `list[3]` exactly (EASY/MEDIUM/HARD index by enum value 0.0/0.5/1.0). Pydantic v2 field on `SceneDefinition` or `TaskConfig`; loader picks the block matching active difficulty. |
| Override application order: scene block → `DifficultyLevelConfig` → `interpolate_params()` | Predictable precedence is table stakes for a config system | LOW | Document the merge order; test all three layers compose. |
| EASY=0.0=loose, HARD=1.0=strict consistency audit across all 6 PARAM_BOUNDS | Phase 29 blocker note flagged possible inverted bounds | LOW | Audit `PARAM_BOUNDS` in all 6 task reward classes; fix any `lo > hi` and add a test asserting direction. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-task `DifficultyLevelConfig` subclasses | Each task can override task-specific fields (e.g. CuttingReward adds `cut_depth_tolerance`) | MEDIUM | Optional; generic `DifficultyLevelConfig` base + per-task extension. |
| Round-trip: scene JSON → env → reward params → YAML export | Authoring reproducibility | LOW | Follows existing `experiments/{name}.yaml` pattern. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Continuous float difficulty removal | "Discrete is simpler" | Breaks backward compat and the additive-scheduler contract | Keep both; discrete selects a float level (0.0/0.5/1.0) that feeds the existing continuous path |
| Auto-generating `difficulty_blocks` from a single scene | "Don't make authors write 3 blocks" | Generates low-quality defaults; authors know their task | Require explicit blocks; provide a CLI generator as a stretch tool, not default |
| Per-step difficulty mutation | "Adaptive difficulty mid-episode" | Conflicts with episode-level curriculum contract; destabilizes reward signal | Per-episode advancement only (existing `CurriculumScheduler` contract) |

### Item 3: 3D Fluid Flag (`dim_3d=True`)

The 2D Eulerian solver (PhiFlow 3.4.0, MAC grid, pressure projection, two-way solid coupling) is implemented for the xz-slice. `dim_3d=True` is a documented stub flag (PROJECT.md Out-of-Scope line currently lists "3D fluid simulation" — but the v0.6.0 milestone explicitly brings it IN scope as a closure item).

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| 3D MAC grid (NxNxN instead of NxN) | 3D fluids require a 3D staggered grid | HIGH | PhiFlow supports 3D natively; mostly a dimensionality switch + voxel-resolved obstacle SDFs. |
| 3D pressure projection (Poisson solve) | Incompressibility enforcement in 3D | HIGH | Larger linear system; CPU cost ~NxNxN. Keep CPU-first per existing decision. |
| 3D two-way solid coupling | Solids immerse in a volume, not a slice | HIGH | Existing 2D coupling generalizes; obstacle SDFs become 3D. |
| `dim_3d` flag respected end-to-end | Flag exists but is a stub | LOW | Plumb flag from `SceneDefinition`/fluid config → solver selection. |
| 2D path preserved unchanged | 2D is the default and the validated path | LOW | Guard all 3D branches; 2D tests must stay green. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Volumetric bleeding/irrigation | 2D slice is a visual approximation; 3D is physically faithful for surgical fluids | HIGH | Marquee differentiator for the fluid work. |
| Adaptive grid resolution (coarse 3D far-field, fine 3D near instrument) | Keeps 3D CPU cost tractable | HIGH | Stretch; not required for closure. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| GPU fluid acceleration | "3D is slow on CPU" | Explicitly Out of Scope (PROJECT.md); PhiFlow CPU-first decision | CPU-first; GPU deferred |
| Navier-Stokes turbulence model | "More realistic fluids" | Overkill for surgical bleeding/irrigation; stability risk | Stick with pressure-projection Eulerian (existing 2D model generalized) |
| Particle-based (SPH/PCISPH) fluids | "Lagrangian is more detailed" | Different solver entirely; throws away PhiFlow work | Keep Eulerian grid; SPH explicitly not chosen in v0.3.2 |
| 3D DreamerV3 video prediction coupling | "Fluid-aware world model" | Cross-couples two closure items; 3D video prediction is Out of Scope | Keep fluids and DreamerV3 independent |

### Item 4: K8s PVC e2e + Organ-Mesh Licensing Decision

K8s manifests (Training Job, KubeRay, ConfigMap/Secrets/PVC) exist; the checkpoint-persistence e2e test is stubbed (Phase 35 scaffolding deferred to v0.6.0). Organ-mesh licensing was a Phase 20 / v0.5.0 research spike with the decision deferred.

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| De-stubbed checkpoint-persistence e2e test | Stubbed tests are the debt | MEDIUM | Assert: pod writes checkpoint to PVC → pod restarts → checkpoint readable from new pod. Use kind/minikube with a hostPath or dynamic PVC. |
| PVC actually mounts in the Training Job manifest | Manifest declares PVC; e2e must prove it mounts RWX/RWO | LOW | Verify `volumeClaimTemplates` or static PVC binding. |
| Checkpoint survives pod failure | Core persistence claim | MEDIUM | Kill pod, verify checkpoint persists on PVC, new pod resumes from it. |
| Organ-mesh licensing decision recorded | A decision is the deliverable, not necessarily new code | LOW | Record in STATE.md + PROJECT.md Key Architecture Decisions. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Procedural organ mesh generation | No licensing exposure; reproducible; deterministic from seed | MEDIUM | Already partially used as primitive fallback; formalize as the licensed path. |
| Multi-backend PVC (RWX for KubeRay, RWO for single TrainingJob) | Production-grade persistence | MEDIUM | Stretch; RWX needs NFS/CephFS provisioner in CI. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Using SurgToolLoc dataset for organ meshes | "It's a surgical dataset" | **SurgToolLoc is endoscopic VIDEO with tool presence labels — it does NOT provide organ meshes.** Mismatch at the data-modality level. | Procedural generation; or find a true mesh dataset (e.g. MeshSDF/ShapeNet medical subsets) — but those have their own licensing concerns |
| SurgToolLoc commercial use | "Public dataset" | Challenge guidelines explicitly prohibit commercial use; license terms beyond the challenge are unclear (no clean CC-BY/CC0 stated) | Procedural generation = no license risk |
| Helm chart for PVC | "Helm is standard" | Explicitly Out of Scope (PROJECT.md); Kustomize overlays sufficient | Kustomize stays |
| Real ROS2 DDS multicast e2e in K8s | "Full e2e" | Platform-level DDS issue; acknowledged Out of Scope | Document workaround |

---

## Feature Dependencies

```
[Real DreamerV3 _build_agent]
    └──requires──> [existing JAX subprocess + GymToEmbodiedWrapper + pixel/state obs]
    └──requires──> [dreamerv3 package install (CI GPU host)]
    └──flips──> [Phase 30 sentinel test]

[DifficultyLevelConfig overrides]
    └──requires──> [existing DifficultyLevel enum + interpolate_params]
    └──requires──> [existing TaskRewardRouter + TaskConfig.difficulty_level]
    └──enhances──> [scene-level difficulty_blocks: list[3]]

[Discrete curriculum progression]
    └──requires──> [existing additive CurriculumScheduler]
    └──requires──> [DifficultyLevelConfig overrides (to know what each level means)]
    └──preserves──> [continuous float path for backward compat]

[3D fluid dim_3d=True]
    └──requires──> [existing 2D PhiFlow solver + MAC grid + pressure projection]
    └──requires──> [BaseSimulator.fluid_step hook (shipped Phase 31)]
    └──preserves──> [2D path unchanged]

[K8s PVC e2e]
    └──requires──> [existing K8s manifests (TrainingJob + PVC)]
    └──requires──> [kind/minikube in CI with PVC provisioner]
    └──independent of──> [organ-mesh licensing decision]

[Organ-mesh licensing decision]
    └──independent of──> [K8s PVC e2e]
    └──resolves──> [Phase 20 / v0.5.0 research spike]
```

### Dependency Notes

- **Real DreamerV3 requires the existing subprocess**: The Phase 24 process isolation, `_JsonStdout` wrapper, `GymToEmbodiedWrapper`, and auto-discovery checkpoints are all already built. The closure only replaces the `_build_agent`/`_train_loop`/`_evaluate`/`_save_checkpoint`/`_load_checkpoint` stubs. Do NOT rebuild the subprocess harness.
- **DifficultyLevelConfig requires the v0.4.2 enum**: `DifficultyLevel` (EASY=0.0/MEDIUM=0.5/HARD=1.0) and `interpolate_params()` are the foundation; `DifficultyLevelConfig` is an override layer ON TOP, applied additively (D-29-03: never replace `interpolate_params()`).
- **Discrete curriculum requires DifficultyLevelConfig**: Without named per-level overrides, a discrete progression has nothing to advance TO beyond the existing float values. Implement DifficultyLevelConfig first.
- **3D fluids require the Phase 31 `fluid_step` hook**: The base-simulator hook (shipped in v0.5.0 Phase 31) is the integration point; 3D solver plugs in via the same hook.
- **K8s PVC e2e and organ-mesh licensing are independent**: The licensing decision is recorded in docs/state; the PVC e2e is CI plumbing. They can be parallelized across worktrees.

---

## MVP Definition

### Launch With (v0.6.0 — all four closure items)

- [ ] Real `_build_agent` returning a live `dreamerv3` agent; `_train_loop` yields real per-step losses; `_evaluate` returns real MSE/MAE/success_rate; checkpoint save/load round-trips; Phase 30 sentinel test flipped to assert positive completion
- [ ] `DifficultyLevelConfig` Pydantic v2 override model (`tissue_stiffness`/`target_precision_tolerance`/`tool_position_noise`/`time_limit`); applied additively over `interpolate_params()`
- [ ] Discrete `CurriculumScheduler` level progression EASY→MEDIUM→HARD on `success_threshold`; continuous float path preserved
- [ ] Scene-level `difficulty_blocks: list[3]` in scene JSON; loader selects block by active difficulty
- [ ] PARAM_BOUNDS direction audit across all 6 task reward classes (EASY=loose, HARD=strict)
- [ ] 3D Eulerian solver behind `dim_3d=True` (3D MAC grid + pressure projection + two-way coupling); 2D path unchanged and green
- [ ] De-stubbed K8s PVC checkpoint-persistence e2e (write → pod restart → read)
- [ ] Organ-mesh licensing decision recorded (procedural generation recommended; see Anti-Features)

### Add After Validation (v0.7.0+)

- [ ] Per-task `DifficultyLevelConfig` subclasses with task-specific override fields
- [ ] Adaptive 3D grid resolution (coarse far-field, fine near instrument)
- [ ] RWX PVC for KubeRay multi-pod checkpoint sharing
- [ ] CLI generator for `difficulty_blocks` from a single scene (stretch tool, not default)

### Future Consideration (v2+)

- [ ] DreamerV3 offline training from recorded demos (DMV3-06)
- [ ] GPU fluid acceleration (PhiFlow GPU backend)
- [ ] Task chains (grasp→cut→suture, TASK-05)
- [ ] RLlib centralized critic for MARL (MARL-05)

---

## Closure-Item Complexity Summary

| Item | Complexity | Why |
|------|-----------|-----|
| Real DreamerV3 integration | HIGH | External `dreamerv3` API surface; real training loop with world-model + actor-critic; GPU-gated CI; sentinel test flip |
| TASK-02 per-level schema | MEDIUM | Three coordinated sub-items (override model + discrete progression + scene blocks); must preserve existing additive/continuous contracts |
| 3D fluid flag | HIGH | Dimensionality lift of a validated 2D solver; 3D pressure solve cost; must keep 2D path green |
| K8s PVC e2e + licensing | MEDIUM (e2e LOW–MED; decision LOW) | e2e is CI plumbing; licensing decision is a doc artifact — but the decision resolves a long-standing spike |

## Sources

- In-repo: `.planning/PROJECT.md`, `.planning/STATE.md` (D-29-03 exclusions, Phase 30 sentinel), `.planning/MILESTONES.md` (v0.4.0 Phase 24, v0.4.2 Phase 29/30), `src/surg_rl/dreamer/subprocess.py` (`_build_agent` stub at ~L127-131), `src/surg_rl/dynamics/curriculum.py` (CurriculumStageConfig)
- [danijar/DreamerV3 (JAX)](https://github.com/danijar/DreamerV3) — HIGH confidence; official `dreamerv3` PyPI v1.5.0, train_eval loop, RSSM world model + actor-critic from imagined trajectories, checkpoint resume via same `--logdir`
- [DreamerV3 Training with Evaluation (DeepWiki)](https://deepwiki.com/danijar/dreamerv3/5.3-training-with-evaluation) — MEDIUM confidence; documents `trainfn`/`reportfn`/`should_train` scheduler, `save_every`, `eval_envs`
- [nm512/dreamerv3-torch](https://github.com/nm512/dreamerv3-torch) — MEDIUM confidence; PyTorch alternative (not chosen; JAX path already decided); maintainers recommend `r2dreamer` now
- [SurgToolLoc Challenge Guidelines](https://surgtoolloc23.grand-challenge.org/challenge-guidelines/) — HIGH confidence; **no commercial use** (Guideline #2), publication gated on challenge results (Guideline #13)
- [SurgToolLoc Data Description](https://surgtoolloc23.grand-challenge.org/data-description/) — HIGH confidence; **dataset is endoscopic video + tool presence labels, NOT organ meshes** — key finding that disqualifies SurgToolLoc as an organ-mesh source
- [Zia et al., 2023 (arXiv:2305.07152)](https://arxiv.org/abs/2305.07152) — MEDIUM confidence; SurgToolLoc dataset paper; license terms beyond challenge unclear