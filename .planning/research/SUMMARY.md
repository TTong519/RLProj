# Project Research Summary

**Project:** Surg-RL
**Domain:** Surgical-robotics RL training system — carried-forward tech-debt closure
**Researched:** 2026-06-24
**Confidence:** HIGH

## Executive Summary

v0.6.0 is a **closure milestone, not a feature milestone**: it pays down four carried-forward tech-debt items by flipping stubs to real implementations and recording one deferred licensing decision. Three of the four items (DreamerV3, 3D fluids, difficulty schema) require **zero new runtime dependencies** — the existing pins (`dreamerv3~=1.5.0`, `phiflow>=3.4.0`, Pydantic v2) already support the real paths. The only stack addition is a single **dev-only** extra, `pytest-kind>=22.11.1`, which de-stubs the K8s PVC e2e test with a session-scoped `kind_cluster` fixture.

The recommended approach respects ten documented architectural invariants (INV-1..INV-10). Every closure item is **additive**: `dim_3d=False` default preserves 2D fluids; `difficulty_overrides: dict[DifficultyLevel, DifficultyLevelConfig] | None` defaults to `None` so existing scene JSON loads unchanged; `CurriculumScheduler` gets new `set_difficulty_level`/`advance_level` alongside (not replacing) the continuous `advance_stage`; the DreamerV3 subprocess JSON-over-stdio protocol, `_JsonStdout` wrapper, and `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` isolation all stay. The Phase 30 sentinel test is **flipped, not deleted** — that flip IS the closure signal.

Top risks concentrate in two items. **Real DreamerV3** (highest risk): sentinel-flip must invert not delete, JAX must never leak into the parent, the dreamerv3 logger must go to stderr (not stdout — corrupts the JSON pipe), and the CI smoke test must assert structural properties (finite/decreasing loss, checkpoint exists) NOT the spike's converged `MSE<0.01` thresholds. **3D fluids**: cubic memory blow-up (NxNxN) if the 2D `grid_size` is reused, plus two-way coupling instability on thin instruments; mitigation is a separate smaller 3D default, `coupling_mode="one_way"` default for 3D, and a `union(*geoms)` SDF regression test in 3D. TASK-02's main risk is re-introducing the v0.4.2 Pydantic cross-package cycle — mitigated by leaf-module placement + `model_rebuild()`.

## Key Findings

### Recommended Stack

No new runtime dependencies. The existing pins are current and capable — `dreamerv3~=1.5.0` is the latest (and only) PyPI release, PhiFlow 3.4.0 natively supports 3D (dimensionality inferred from `Box`/`StaggeredGrid` shape, not a library flag), and the DifficultyLevelConfig schema is pure Pydantic v2. The only `pyproject.toml` change is one dev-only extra.

**Core technologies:**
- `dreamerv3~=1.5.0` (vendored `embodied` framework): real agent wiring via `embodied.run.train(make_agent, make_replay, make_env, ...)` + `dreamerv3.Agent(embodied.jax.Agent)` exposing `init_train/train/policy/report/save/load` — no dep change, just stub→real.
- `phiflow>=3.4.0`: 3D Eulerian fluids via 3D `Box(x,y,z)` + `StaggeredGrid`; `make_incompressible` + `union(*geoms)` workaround are dimension-agnostic — no version bump.
- Pydantic v2: `DifficultyLevelConfig` reusing the v0.4.2 `from __future__ import annotations` + string forward-ref + `model_rebuild()` cycle-resolution pattern — no new package.
- `pytest-kind>=22.11.1` (NEW, dev-only `[k8s-test]` extra): session-scoped `kind_cluster` fixture + `kubectl(*args)` helper for the PVC e2e test. Replaces the raw-subprocess stub. Rejected: `pytest-k8s` (30+ MB `kubernetes` client, heavy for one test) and raw `subprocess.run` (loses fixture lifecycle).

### Expected Features

Four closure items, each a stub→real flip or an additive schema extension — no greenfield features.

**Must have (table stakes):**
- Real DreamerV3 training loop (actor/critic/world-model steps, checkpoint resume, eval) replacing the 5 stub functions (`_build_agent`/`_train_loop`/`_evaluate`/`_save_checkpoint`/`_load_checkpoint`)
- `DifficultyLevelConfig` per-level overrides (tissue_stiffness / target_precision_tolerance / tool_position_noise / time_limit) applied additively over `interpolate_params()`
- Discrete curriculum progression (EASY→MEDIUM→HARD) as an additive `progression_mode`, never replacing the continuous 4-stage `DEFAULT_STAGES`
- Scene-level `difficulty_blocks` parsing + env-construction wiring with precedence truth-table
- 3D Eulerian fluid solver (`dim_3d=True`) with the 2D path staying green
- Real K8s PVC checkpoint-persistence e2e (write → pod restart → read on a bound PVC)

**Should have (competitive):**
- DreamerV3 checkpoint namespace per task/obs-type + auto-discovery (already partially present)
- `coupling_mode` parameter (one_way default in 3D, two_way opt-in) for fluid/solid coupling stability
- License-citation ADR artifact for the organ-mesh decision (procedural-as-default)

**Defer (v2+ / out of scope):**
- DreamerV3 convergence-threshold validation on the full 6-task suite with cutting dynamics (flagged uncertain; smoke-vs-convergence split defers but does not resolve)
- GPU fluid acceleration (CPU-first per existing decision)
- surgtoolloc organ meshes — research confirmed it is the WRONG choice (endoscopic video with tool-presence labels, NOT organ geometry; challenge guidelines also prohibit commercial use)

### Architecture Approach

Single integration seams per item, all additive, all preserving existing invariants. (a) DreamerV3: one seam at `subprocess.py:125-129` (`_build_agent` stub) — 5 stub functions get real implementations; the JSON pipe protocol, `_JsonStdout` wrapper, `DreamerSubprocess` parent, and `GymToEmbodiedWrapper` are unchanged; Phase 30 sentinel flips negative→positive. (b) Difficulty schema: 3-part chain — `DifficultyLevelConfig` (new leaf Pydantic model) → additive `CurriculumScheduler.set_difficulty_level`/`advance_level` → scene-level `difficulty_overrides: dict[DifficultyLevel, DifficultyLevelConfig] | None` on `TaskConfig`. (c) 3D fluid: `FluidConfig.dim_3d: bool = False` + 3-tuple resolution; `FluidSimulator.__init__` branches on `dim_3d`; `fluid_step()` hook stays no-op; `force_computation.py` 3D bbox branch is the highest-complexity sub-task. (d) PVC e2e: kubectl subprocess approach (no python-client dep) + new `k8s/overlays/e2e/` overlay; organ-mesh licensing = ADR document, not code.

**Major components:**
1. `src/surg_rl/dreamer/subprocess.py` — replace 5 stub functions; flip Phase 30 sentinel
2. `src/surg_rl/rl/difficulty.py` (leaf) + `schema.py` + `curriculum.py` + `environment.py` — DifficultyLevelConfig + discrete progression + scene blocks
3. `src/surg_rl/simulators/fluid_simulator.py` + `force_computation.py` — dim_3d branch + 3D bbox coupling
4. `tests/.../test_pvc_e2e.py` + `k8s/overlays/e2e/` + organ-mesh ADR — PVC e2e + licensing decision

### Critical Pitfalls

1. **DreamerV3 sentinel flip must INVERT, not delete** — the Phase 30 test asserts the *expected* `RuntimeError("Agent not configured")`; flip it to assert positive completion AND add a guard that fails if `_build_agent` ever returns `None` again. (highest risk; GPU-gated)
2. **JAX must never leak into the parent process** — any `import jax`/`import dreamerv3` in the parent re-introduces the GPU OOM that process isolation was designed to prevent; keep parent↔child on JSON-over-stdio and set `XLA_PYTHON_CLIENT_MEM_FRACTION` before JAX's first import; dreamerv3 logger must go to stderr (not stdout — corrupts the JSON pipe).
3. **3D fluid cubic memory blow-up + thin-instrument coupling instability** — `dim_3d=True` must ship with a smaller 3D default `grid_size` + validator, one-way coupling default in 3D, and a `union()`-in-3D NaN-regression test. Default `dim_3d=False`.
4. **Pydantic v2 cross-package cycle re-introduction** — `DifficultyLevelConfig` must be a leaf module wired with the established `model_rebuild()` pattern; override precedence must be TDD'd as a truth table against the existing 4-source chain in `_setup_rewards`.
5. **CurriculumScheduler regression** — discrete progression must be ADDITIVE (`progression_mode` flag), never replace the continuous `DEFAULT_STAGES`; the full v0.4.0+v0.4.2 curriculum suite must pass unchanged as the additive gate. Naming drift: `difficulty_blocks` (PROJECT.md) vs `difficulty_levels` (STATE.md) — pick `difficulty_blocks` and reconcile in Phase 36.

## Implications for Roadmap

Based on research, suggested phase structure (continuing from v0.5.0 Phase 35 → start at Phase 36):

### Phase 36: TASK-02 Difficulty Schema + Discrete Curriculum
**Rationale:** Lowest-risk, non-GPU-gated, pure Pydantic v2 + additive scheduler; unblocks Phase 37; combines the schema + discrete-progression sub-items to avoid a `curriculum.py` merge conflict.
**Delivers:** `DifficultyLevelConfig` leaf model + `difficulty_overrides` on `TaskConfig` + additive `CurriculumScheduler.set_difficulty_level`/`advance_level` + naming reconciliation.
**Addresses:** TASK-02 per-level schema (partial — scene blocks in Phase 37).
**Avoids:** Pydantic v2 cycle re-introduction (leaf-module + `model_rebuild()`); additive-curriculum regression.

### Phase 37: Scene-Level difficulty_blocks + Env Wiring + Fixtures
**Rationale:** Depends on Phase 36; loader needs no change (Pydantic validates); work is fixtures + `SurgicalEnv._setup_rewards` wiring + precedence truth-table test + load-all-6-scenes regression.
**Delivers:** Scene-level `difficulty_blocks` parsing, env-construction override application, precedence truth-table test.
**Uses:** DifficultyLevelConfig from Phase 36.
**Implements:** `_setup_rewards` override-precedence chain.

### Phase 38: 3D Fluid Flag (`dim_3d=True`)
**Rationale:** Independent of the difficulty chain; PhiFlow 3D API HIGH-confidence; additive (`dim_3d=False` default); parallelizable with 37/39 via worktrees.
**Delivers:** `FluidConfig.dim_3d` + 3D `Box`/`StaggeredGrid` branch + 3D `force_computation` bbox + dual-mode parametrized test.
**Avoids:** Cubic memory blow-up (separate 3D default + validator); thin-instrument coupling instability (one-way default).

### Phase 39: K8s PVC e2e + Organ-Mesh Licensing Decision
**Rationale:** Independent; (d1) test plumbing + (d2) ADR combine cleanly; low-risk landing before the GPU-gated DreamerV3 phase; parallelizable with 37/38.
**Delivers:** De-stubbed PVC checkpoint-persistence e2e (`pytest-kind` + `kubectl wait --for=condition=Bound`) + `k8s/overlays/e2e/` + organ-mesh licensing ADR (procedural-as-default; surgtoolloc rejected with cited rationale).
**Uses:** `pytest-kind>=22.11.1` (new dev-only extra).

### Phase 40: Real DreamerV3 Integration + Sentinel Flip
**Rationale:** LAST — GPU-gated (CI GPU host; macOS skips per INV-8), highest external-API risk; benefits from the clean baseline of landed (b)(c)(d). Sentinel flip is the milestone closure signal.
**Delivers:** 5 real stub implementations against `embodied.run.train` / `dreamerv3.Agent`; Phase 30 sentinel inverted to positive-path + regression guard; CI GPU matrix entry.
**Avoids:** JAX-in-parent OOM; stdout-logger JSON-pipe corruption; smoke-vs-convergence conflation (CI asserts structural properties, not converged thresholds).

### Phase Ordering Rationale

- Dependency chain: DifficultyLevelConfig (36) → scene blocks + env wiring (37) — discrete progression needs something to advance TO.
- Independence: 3D fluids (38), K8s PVC + licensing (39) are fully independent of the difficulty chain and of each other → parallelizable via worktrees alongside 36/37.
- Risk ordering: DreamerV3 (40) is GPU-gated and highest external-API risk → last, so macOS dev on the other 4 items isn't blocked by GPU-host availability.
- Pitfall avoidance: additive-curriculum invariant gated by the full v0.4.0+v0.4.2 curriculum suite; 3D fluids gated by `union()`-in-3D NaN test; DreamerV3 gated by inverted sentinel + parent-import guard.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 40 (Real DreamerV3):** external `dreamerv3` factory composition (`make_agent`/`make_replay`/`make_stream`/`make_logger` + `encoder.mlp_keys`/`cnn_keys` for custom envs) — official `example.py` is 404-unreachable; signatures inferred from DeepWiki + `embodied.run.train` source. Also CI GPU host provisioning strategy.
- **Phase 38 (3D fluid — `force_computation` 3D branch):** 2D pressure-gradient bbox integration generalization to a z-axis slice needs design validation. PhiFlow 3D API itself is HIGH confidence.
- **Phase 39 (Organ-mesh licensing ADR):** needs the specific SurgToolLoc/EndoVis MICCAI license clause text cited (legal-text research, not code).

Phases with standard patterns (skip research-phase):
- **Phase 36:** Pydantic v2 + additive scheduler — reuses v0.4.2 cycle-resolution pattern.
- **Phase 37:** fixture + `_setup_rewards` wiring.
- **Phase 39 (PVC e2e test plumbing only):** `pytest-kind` is well-documented; standard kubectl-e2e 4-step pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Only `pytest-kind` added; 3/4 items zero new deps; versions verified via PyPI/Context7 |
| Features | HIGH | In-repo stub locations + prior milestone deliverables confirmed by direct code inspection |
| Architecture | HIGH | Integration seams verified in codebase; DreamerV3 external API at MEDIUM |
| Pitfalls | HIGH | Built on 3 milestones of documented Phase 24/26/29/30 context; SurgToolLoc license terms MEDIUM-HIGH (recommend phase-1 citation artifact) |

**Overall confidence:** HIGH (3 of 4 items are in-repo stub→real flips verified by direct code inspection; DreamerV3 external API at MEDIUM)

### Gaps to Address

- DreamerV3 factory composition — validate against the installed `dreamerv3` package during Phase 40 planning.
- CI GPU host provisioning — design the matrix entry that runs the GPU-skipif tests (else milestone audit fails on 100%-skipped).
- `force_computation.py` 3D bbox branch — design validation of z-axis slice integration.
- SurgToolLoc license clause text — quote the exact redistribution terms in the ADR.
- Naming drift: `difficulty_blocks` vs `difficulty_levels` — pick `difficulty_blocks` and update STATE.md in Phase 36.

## Sources

### Primary (HIGH confidence)
- In-repo code inspection: `src/surg_rl/dreamer/subprocess.py` (`_build_agent` stub at 125-131), `tests/dreamer/test_dreamerv3_subprocess_e2e.py` (Phase 30 sentinel), `src/surg_rl/rl/difficulty.py`, `schema.py`, `curriculum.py`, `environment.py` (`_setup_rewards` precedence chain), `fluid_simulator.py` + `force_computation.py`, `k8s/` overlays + PVC stub
- `.planning/STATE.md`, `.planning/PROJECT.md`, `.planning/MILESTONES.md` — prior decisions (v0.4.0 Phase 24 spike, v0.4.2 Phase 29/30 DifficultyLevel + sentinel)

### Secondary (MEDIUM confidence)
- [danijar/dreamerv3](https://github.com/danijar/dreamerv3) + [PyPI dreamerv3](https://pypi.org/project/dreamerv3/) — v1.5.0 is latest/only release; vendored `embodied` framework
- [DeepWiki DreamerV3 Agent Architecture / Interface](https://deepwiki.com/danijar/dreamerv3/4-agent-architecture) — factory composition signatures (official `example.py` 404)
- [PhiFlow StaggeredGrids](https://tum-pbs.github.io/PhiFlow/Staggered_Grids.html) + [fluid API](https://tum-pbs.github.io/PhiFlow/phi/physics/fluid.html) + [Wake Flow 3D example](https://tum-pbs.github.io/PhiFlow/examples/grids/Wake_Flow.html) — 3D API dimension-agnostic
- [pytest-kind v22.11.1 on PyPI](https://pypi.org/project/pytest-kind/) — `kind_cluster` fixture + `kubectl` helper

### Tertiary (LOW confidence)
- SurgToolLoc/EndoVis MICCAI license clause text — modality mismatch (tool-presence labels, not organ geometry) verified; exact legal terms need phase-1 citation artifact

---
*Research completed: 2026-06-24*
*Ready for roadmap: yes*