# Phase 38: 3D Fluid Flag (dim_3d=True) - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds a `dim_3d=True` path to the Eulerian grid fluid solver (PhiFlow
backend) so simulation authors can opt into 3D Eulerian grid fluids, while the
validated 2D xz-slice path stays **byte-identical** to v0.5.0. Pure solver +
schema work; non-GPU; independent of the 36→37 difficulty chain and of Phase 39
(parallelizable via worktrees). Requirements: FLUID-01, FLUID-02, FLUID-03.

**What this phase delivers:**
1. A `FluidConfig.dim_3d: bool = False` flag + a separate 3D
   `grid_size: tuple[int, int, int] | None` field (SC#1 / FLUID-01). When
   `dim_3d=True`, `FluidSimulator` constructs a 3D `Box(x, y, z)` +
   `StaggeredGrid` and runs `make_incompressible` + pressure projection in 3D.
   When `dim_3d=False` (default), the existing 2D `Box(x=dx, y=dz)` +
   `resolution=(nx, ny)` path is untouched and produces byte-identical output.
2. A `FluidCouplingMode` str-Enum (`ONE_WAY` default / `TWO_WAY` opt-in) on
   `FluidConfig` (SC#2 / FLUID-02). `one_way` treats obstacles as static SDFs
   (no solid-velocity feedback into the fluid) and runs stably on thin
   instruments via substepping + per-axis force clamping. `two_way` feeds
   obstacle velocity back into the fluid solve, is opt-in, and is documented as
   unstable on thin instruments.
3. A memory-bounded 3D grid: `grid_size` is **required** when `dim_3d=True`
   (hard `ValidationError` if omitted), each dimension capped at 64 (vs the 2D
   128 cap), with a documented recommended value of 24³ in the field description
   (SC#3 / FLUID-03).
4. 3D obstacle/solid coupling: thin instruments represented as cylinder shafts
   + box tips (merged via the existing `union(*geoms)` workaround); a
   higher-level `FluidSimulator.add_instrument(pose, dims)` method constructs
   the SDF and calls `add_obstacle`. 3D `compute_obstacle_forces` integrates the
   pressure gradient over obstacle-mask cells → `(fx, fy, fz)` with a per-axis
   independent clamp.
5. A NaN-regression test for the `union(*geoms)` workaround **parametrized over
   (`dim_3d=False`, `dim_3d=True`) × (single, overlapping) obstacles**, asserting
   finite velocity + pressure after N steps (SC#4 / FLUID-03).
6. `BaseSimulator.fluid_step(dt)` still fires for both `dim_3d` modes — the
   env-driven no-op hook is unchanged; the v0.5.0 5-test `fluid_step` regression
   suite passes unchanged (SC#5).
7. A `render_fluid_3d` that renders a chosen 2D slice (z-layer) of the 3D field
   via the existing `render_fluid_2d` machinery (slice-of-3D fallback; not a
   true volume renderer).

**What this phase does NOT deliver:**
- A true 3D volume / iso-surface renderer (deferred — no SC requires it).
- Wiring `add_obstacle` / `add_instrument` or force application into the
  production `SurgicalEnv` episode loop (obstacle coupling stays
  FluidSimulator-level; SC#2 stability is exercised at the solver level, matching
  the existing 2D test pattern). The env stays unmodified beyond the unchanged
  `fluid_step` hook.
- GPU fluid acceleration (PhiFlow CPU-first; PROJECT.md decision).
- Any change to the 2D `resolution` field, its `_cap_resolution` validator, the
  2D `Box(x=dx, y=dz)` mapping, or the 2D `compute_obstacle_forces` global-sum +
  scalar-magnitude-clamp behavior (those stay byte-identical to v0.5.0).
- Difficulty-chain work (Phases 36/37), K8s PVC e2e (Phase 39), real DreamerV3
  (Phase 40).

</domain>

<decisions>
## Implementation Decisions

### FluidConfig schema: dim_3d + grid_size
- **D-01:** Add `dim_3d: bool = Field(default=False, description="Enable 3D
  Eulerian grid fluids")` to `FluidConfig`. Default `False` keeps the 2D path
  byte-identical (SC#1 additive-regression gate).
- **D-02:** Add a **separate** `grid_size: tuple[int, int, int] | None =
  Field(default=None, description="3D grid resolution (Nx, Ny, Nz); REQUIRED
  when dim_3d=True. Recommended 24³ = (24, 24, 24). Each dim capped at 64.")`.
  Do NOT overload the existing `resolution: tuple[int, int]` field — it stays
  2-tuple-only and its `_cap_resolution` validator is unchanged.
- **D-03:** `grid_size` is **required when `dim_3d=True`**. A
  `model_validator` (or `field_validator`) raises a `ValidationError` if
  `dim_3d=True` and `grid_size is None`. This hard-error IS the memory-blow-up
  guard (SC#3): it forces a conscious 3D size choice rather than silently
  filling a cubic default.
- **D-04:** `grid_size` allows **anisotropic** `(Nx, Ny, Nz)` 3-tuples (each
  dimension independently bounded) so authors can save memory on thin domains
  (e.g. `64×32×64`). Not cubic-only.
- **D-05:** 3D per-dimension cap = **64** (64³ = 262k cells). The 2D per-dim
  cap stays 128. A separate, smaller 3D cap satisfies SC#3's "smaller" wording.
  Min 4 per dimension (mirrors the 2D min). The cap is enforced by a new
  `_cap_grid_size` validator distinct from `_cap_resolution`.

### 3D domain + axis mapping
- **D-06:** 3D uses the **direct physical→grid mapping** `(x, y, z) → (x, y, z)`
  with `Box(x=dx, y=dy, z=dz)` built from the **full** `BoundingBox.get_dimensions()`
  (all three dims). The 2D path keeps its existing physical `(x, z) → grid (x, y)`
  mapping (`Box(x=dx, y=dz)`, dims[0] and dims[2]) unchanged. The two paths are
  deliberately distinct; do not "unify" them (would perturb the 2D regression).

### FluidSimulator 3D construction + step
- **D-07:** `FluidSimulator.__init__` branches on `config.dim_3d`:
  - `dim_3d=False`: existing 2D construction (byte-identical).
  - `dim_3d=True`: `Box(x=dx, y=dy, z=dz)` + `StaggeredGrid(0.0, extrapolation.ZERO,
    domain, x=Nx, y=Ny, z=Nz)` using `config.grid_size`. Follows the PhiFlow 3D
    `Wake_Flow` pattern (`StaggeredGrid((vx,vy,vz), boundary, x=Nx, y=Ny, z=Nz,
    bounds=Box(...))` + `make_incompressible(v, obstacle, Solve(...))`).
- **D-08:** `step(dt)` is dim-aware: `advect.mac_cormack` + `make_incompressible`
  run on the 3D grid when `dim_3d=True`. The `union(*geoms)` multi-obstacle
  workaround is preserved for both paths. The `Solve(rel_tol=1e-4, abs_tol=1e-4,
  max_iterations=500)` settings are reused unchanged.

### Coupling mode
- **D-09:** Add a `FluidCouplingMode(str, Enum)` with `ONE_WAY = "one_way"` and
  `TWO_WAY = "two_way"` to `schema.py`, mirroring the existing
  `FluidBoundaryType` str-Enum style. Add
  `coupling_mode: FluidCouplingMode = Field(default=FluidCouplingMode.ONE_WAY)`
  to `FluidConfig`.
- **D-10:** Operational semantics:
  - `ONE_WAY`: obstacles are **static SDFs** (zero velocity); fluid
    pressure-gradient → forces on solid (computed + clamped); **solid motion
    does NOT feed back into the fluid**. No added-mass term → stable on thin
    instruments (matches the research consensus that one-way/partitioned
    coupling is stable for thin/light solids when there is no velocity
    feedback).
  - `TWO_WAY`: obstacles carry a velocity field fed back into the fluid solve
    (PhiFlow `Obstacle.velocity`); forces are bidirectional. Opt-in; documented
    as **unstable on thin instruments** (added-mass instability). The same
    per-axis clamp is applied as a best-effort brake, not a stability guarantee.
- **D-11:** `one_way` stability on thin instruments is enforced by:
  (a) static-SDF obstacles (no velocity feedback — the structural reason it is
  stable), (b) **substepping** via the new `coupling_substeps` field, and
  (c) a **per-axis independent force clamp** in 3D `compute_obstacle_forces`.
  No cut-cell / SPD monolithic solver is introduced (out of scope; two-way
  instability is acknowledged, not solved).

### Substepping configuration
- **D-12:** Add `coupling_substeps: int = Field(default=4, ge=1, le=16,
  description="Internal coupling substeps per env step on the 3D obstacle path;
  reuses substep_dt as the per-substep dt.")` to `FluidConfig`. Used **only** on
  the 3D obstacle path (`dim_3d=True` with obstacles). The existing `substep_dt`
  is reused as the per-substep dt (no new dt field).
- **D-13:** Default `coupling_substeps = 4` (the explicit N choice in discussion
  supersedes the option label's "default 2"). `one_way` runs
  `coupling_substeps` internal coupling steps per env step; `two_way` documents
  instability regardless of the substep count.

### 3D obstacle SDF + construction API
- **D-14:** Thin instruments are represented as **cylinder shafts + box tips**,
  merged via `union(*geoms)` as today. Cylinders are the natural thin-instrument
  shape and match the PhiFlow 3D `Wake_Flow` example
  (`infinite_cylinder(x=, y=, radius=, inf_dim='z')` / `cylinder`).
- **D-15:** Add a higher-level `FluidSimulator.add_instrument(self, pose, dims)`
  method that constructs the cylinder-shaft + box-tip SDF from a pose + dims and
  calls `add_obstacle(geometry, name)`. The raw `add_obstacle(geometry, name)`
  API is kept unchanged (2D tests + 2D byte-identical path rely on it). The
  builder logic lives on `FluidSimulator` (not a free helper) per the user's
  choice; planner confirms exact signature (`pose`/`dims` shapes).

### 3D force computation
- **D-16:** `compute_obstacle_forces` extends to 3D returning `(fx, fy, fz)`
  (fy now nonzero). The 3D path uses **obstacle-mask integration** — integrate
  the pressure gradient over each obstacle's mask cells × cell volume, per axis.
  This diverges from the 2D path's global-sum semantics; that is intentional
  (3D is a new path; the 2D global-sum + scalar-magnitude-clamp behavior is
  preserved byte-identical for SC#1). Planner confirms how the obstacle mask is
  obtained from PhiFlow (e.g. `geometry.approximate_fraction` / mask sampling).
- **D-17:** 3D force clamp is **per-axis independent**: each of `fx`, `fy`, `fz`
  is clamped independently to the per-axis cap (e.g. 1e4). A spike on one axis
  does not shrink the others. The 2D path keeps its existing scalar
  vector-magnitude clamp (`sqrt(fx²+fz²)` → scale) unchanged for byte-identical
  output.

### Visualization
- **D-18:** Add `render_fluid_3d(field, z_layer=...)` that extracts a 2D
  z-layer slice from the 3D velocity/pressure field and delegates to the
  existing `render_fluid_2d` machinery (slice-of-3D fallback). This is NOT a
  true 3D volume / iso-surface renderer. `render_fluid_2d` stays for the 2D
  path. A true 3D renderer is deferred.

### Regression gates
- **D-19:** SC#1 2D byte-identical regression: the existing 2D
  `test_fluid_simulator.py` suite passes unchanged (no edits beyond
  additions); a dedicated 2D baseline test pins velocity/pressure output for
  `dim_3d=False` against v0.5.0. The 3D additions are additive only.
- **D-20:** SC#4 NaN-regression test is a **single parametrized test** over
  `(dim_3d=False, dim_3d=True) × (single obstacle, multiple overlapping
  obstacles)`, running N steps through `step()` with the `union(*geoms)`
  workaround and asserting velocity + pressure are finite (no NaN/Inf) for every
  case. Covers both paths in one parametrized suite.
- **D-21:** SC#2 stability is exercised at the **FluidSimulator level**
  (integration test): add thin-instrument obstacles via `add_instrument`, run N
  steps with `ONE_WAY`, assert no NaN / no blow-up; a `TWO_WAY` variant asserts
  it is opt-in and documents instability. NOT a full `SurgicalEnv` episode test
  (would require env wiring not currently in place — scope creep).
- **D-22:** SC#5 `fluid_step` hook: the v0.5.0 5-test `test_fluid_step.py` suite
  passes unchanged. The hook remains an env-driven no-op in both backends;
  fluid is driven by `env._fluid_simulator.step()` which becomes dim-aware.

### Claude's Discretion
- Exact `model_validator` vs `field_validator` choice for the
  `dim_3d=True ⇒ grid_size required` cross-field rule (D-03) and the
  `_cap_grid_size` validator (D-05).
- Exact `add_instrument(pose, dims)` signature and how `pose`/`dims` map to
  cylinder shaft + box tip geometry (D-15).
- Exact PhiFlow mechanism for obtaining the obstacle mask in 3D
  obstacle-mask integration (D-16) — planner verifies against the installed
  PhiFlow API.
- Exact `render_fluid_3d` signature (which field, slice axis, layer index)
  and how the 3D field slice is extracted and fed to `render_fluid_2d` (D-18).
- Whether `FluidCouplingMode` / `coupling_substeps` / `grid_size` live on
  `FluidConfig` directly (assumed) vs a nested `Fluid3DConfig` sub-model —
  planner decides, provided the 2D `FluidConfig` fields and their defaults are
  untouched (byte-identical 2D regression).
- Exact N (step count) for the SC#2 and SC#4 regression tests, provided it is
  large enough to surface NaN/blow-up.
- Naming of internal dim-3D branches and the `coupling_substeps` Literal/bounds,
  provided semantics match the decisions above.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — v0.6.0 milestone scope; "3D fluid flag" target item;
  Key Architecture Decisions: "PhiFlow over Mantaflow", "CPU-first fluids (GPU
  deferred)", "2D fluids only (xz-plane); 3D behind dim_3d=True flag, not yet
  implemented", "PhiFlow multi-obstacle union() bug requires merged SDF
  workaround — documented pitfall". These are LOCKED — do not re-litigate.
- `.planning/ROADMAP.md` §"Phase 38: 3D Fluid Flag (dim_3d=True)" (lines
  ~111–124) — goal, 5 success criteria, "Depends on: Nothing" (independent;
  parallelizable via worktrees alongside 36/37/39).
- `.planning/REQUIREMENTS.md` — FLUID-01, FLUID-02, FLUID-03 acceptance
  criteria; the explicit "Two-way 3D fluid/solid coupling as default →
  Unstable on thin instruments; one-way is the 3D default, two-way is opt-in"
  exclusion (line ~73).
- `.planning/STATE.md` — current milestone state; Phase 37 closeout context
  (clean baseline this phase builds on).

### Prior phase artifacts (patterns to mirror)
- `.planning/phases/36-difficulty-schema-discrete-curriculum/36-CONTEXT.md` —
  the **additive-regression gate** pattern (new code is additive; existing
  tests pass unchanged beyond additions) and the **Pydantic v2 leaf-model +
  `model_rebuild()` cycle-resolution** discipline. Phase 38 mirrors the
  additive-regression gate for the 2D byte-identical SC#1.
- `.planning/phases/35-advanced-tech-debt/` — delivered the `fluid_step` hook
  (DEBT-03) and the PhiFlow `union()` workaround documentation (DEBT-05); the
  surfaces this phase extends.

### Code references (the validated 2D surfaces this phase MUST NOT perturb)
- `src/surg_rl/scene_definition/schema.py:1500-1532` — `FluidBoundaryType`
  str-Enum + `FluidConfig` (the `resolution` field + `_cap_resolution`
  validator: min 4, cap 128, len==2). `dim_3d`/`grid_size`/`FluidCouplingMode`/
  `coupling_substeps` are ADDED here; `resolution` + `_cap_resolution` stay
  byte-identical.
- `src/surg_rl/fluids/fluid_simulator.py` — `FluidSimulator` (2D `Box(x=dx,
  y=dz)` + `StaggeredGrid`, `step()` with `union(*geoms)` workaround at line
  ~118, `add_obstacle`, `make_incompressible` + `Solve(rel_tol=1e-4,
  abs_tol=1e-4, max_iterations=500)`). The 3D branch + `add_instrument` are
  added here; the 2D branch stays byte-identical.
- `src/surg_rl/fluids/force_computation.py` — `compute_obstacle_forces` (2D
  global-sum integration → `(fx, 0, fz)` + scalar magnitude clamp at 1e4). The
  3D obstacle-mask + per-axis-clamp path is added; the 2D path stays
  byte-identical.
- `src/surg_rl/fluids/visualizer.py` — `render_fluid_2d` (the 2D renderer
  `render_fluid_3d` delegates to via a z-layer slice).
- `src/surg_rl/fluids/__init__.py` — `__all__` export list (add
  `render_fluid_3d`; keep `render_fluid_2d`).
- `src/surg_rl/simulators/base_simulator.py:336` — `BaseSimulator.fluid_step(dt)`
  no-op hook (DEBT-03); unchanged — SC#5.
- `src/surg_rl/simulators/mujoco_simulator.py:1275` +
  `src/surg_rl/simulators/pybullet_simulator.py:1937` — the explicit no-op
  `fluid_step` overrides; unchanged.
- `src/surg_rl/rl/environment.py:771-789,851-862` — `SurgicalEnv` fluid wiring
  (`env._fluid_simulator.step()` driven from `step()`; `_setup_fluid` builds
  `FluidSimulator(fluid_cfg)`). Becomes dim-aware via the unchanged
  `FluidSimulator` constructor; no env edit beyond what the dim-aware ctor
  already handles. NOTE: `add_obstacle` is NOT called in production today — do
  not add env-level obstacle wiring in this phase (D-21).

### Testing references
- `tests/test_fluids/test_fluid_simulator.py` — existing 2D
  `FluidSimulator` tests (init, obstacles, visualization, divergence); the
  additive-regression gate this phase must keep green; the pattern for the new
  3D + NaN-parametrized tests.
- `tests/test_fluid_step.py` — the v0.5.0 5-test `fluid_step` hook suite
  (SC#5); must pass unchanged.
- `tests/test_fluids/test_schema.py` — `FluidConfig` schema tests; extend for
  `dim_3d`/`grid_size`/`coupling_mode`/`coupling_substeps` validators.
- `pytest.ini` — marker registry.

### External references (PhiFlow 3D patterns)
- PhiFlow `Wake_Flow` 3D example —
  https://tum-pbs.github.io/PhiFlow/examples/grids/Wake_Flow.html — canonical
  3D `StaggeredGrid((vx,vy,vz), boundary, x=Nx, y=Ny, z=Nz, bounds=Box(x,y,z))`
  + `make_incompressible(v, obstacle, Solve(...))` + `infinite_cylinder`
  obstacle pattern. Planner should mirror this for D-07/D-08/D-14.
- PhiFlow `make_incompressible` API —
  https://tum-pbs.github.io/PhiFlow/phi/physics/fluid.html — signature
  `make_incompressible(velocity, obstacles=(), solve=Solve(), active=None,
  order=2, ...)` → `(velocity, pressure)`.
- PhiFlow `Staggered_Grids` doc —
  https://tum-pbs.github.io/PhiFlow/Staggered_Grids.html — face-sampled
  velocity, non-uniform values tensor (informs D-16 mask extraction).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FluidConfig` (`scene_definition/schema.py:1507`) — the Pydantic v2 model this
  phase extends additively (`dim_3d`, `grid_size`, `FluidCouplingMode`,
  `coupling_substeps`). The `resolution` field + `_cap_resolution` validator
  are reused unchanged for the 2D path.
- `FluidSimulator` (`fluids/fluid_simulator.py`) — the solver this phase makes
  dim-aware. `step()` already contains the `union(*geoms)` workaround (D-08/D-20
  reuse it for both dims) and the `Solve(...)` settings.
- `compute_obstacle_forces` (`fluids/force_computation.py`) — the 2D
  pressure-gradient force routine; 3D obstacle-mask + per-axis-clamp path is
  added alongside, 2D preserved.
- `render_fluid_2d` (`fluids/visualizer.py`) — the 2D renderer `render_fluid_3d`
  delegates to via a z-layer slice (D-18).
- `BaseSimulator.fluid_step` hook (`simulators/base_simulator.py:336`) — the
  env-driven no-op hook; unchanged for SC#5.
- `BoundingBox.get_dimensions()` (`scene_definition/schema.py:207`) — returns
  `(dx, dy, dz)`; 3D `Box(x=dx, y=dy, z=dz)` uses all three; 2D uses dims[0]
  and dims[2] (unchanged).

### Established Patterns
- **Additive-regression gate** (Phase 36): new code is additive; existing
  v0.5.0 tests pass unchanged (no edits beyond additions). Drives SC#1/SC#5.
- **str-Enum on schema** (e.g. `FluidBoundaryType`): `FluidCouplingMode` mirrors
  this style (D-09).
- **Per-field Pydantic v2 validators** (`_cap_resolution`): the new
  `_cap_grid_size` + the `dim_3d⇒grid_size required` rule mirror this (D-05/D-03).
- **`union(*geoms)` multi-obstacle SDF workaround** (DEBT-05, documented in
  `fluid_simulator.py` module docstring): reused for both 2D and 3D; SC#4 adds
  the NaN-regression test covering both.
- **Lazy PhiFlow imports inside methods** (`from phi.flow import ...` inside
  `__init__`/`step`): keeps PhiFlow import-optional; the 3D branch follows the
  same lazy-import discipline.

### Integration Points
- `FluidConfig` (schema) → consumed by `FluidSimulator.__init__`
  (`fluid_simulator.py:66`) and `compute_obstacle_forces`
  (`force_computation.py:16`). New fields flow through these two call sites.
- `SurgicalEnv._setup_fluid` (`environment.py:851-862`) builds
  `FluidSimulator(fluid_cfg)` — the dim-aware constructor handles 3D without env
  edits. `SurgicalEnv.step()` (`environment.py:771-789`) calls
  `env._fluid_simulator.step()` which becomes dim-aware.
- `fluids/__init__.py` `__all__` — add `render_fluid_3d` (and `add_instrument`
  is a method, not an export).
- The `fluid_step` hook chain (`base_simulator` → `mujoco_simulator` /
  `pybullet_simulator` no-op overrides → `SurgicalEnv.step()` invocation) is
  unchanged; SC#5 regression suite guards it.

</code_context>

<specifics>
## Specific Ideas

- The user explicitly chose **substepping + per-axis clamp** (over the
  clamp-only option) for `one_way` stability — so the 3D obstacle path MUST
  implement both `coupling_substeps` internal substeps AND a per-axis
  independent force clamp, not just the existing scalar magnitude clamp.
- The user explicitly chose **obstacle-mask integration** for 3D forces (over
  mirroring the 2D global-sum). This is a deliberate divergence from the 2D
  force semantics; the 2D global-sum path is preserved only for byte-identical
  regression. Downstream agents should NOT try to "unify" the two force paths.
- The `coupling_substeps` default is **4**, not 2 — the explicit N choice in
  discussion supersedes the "default 2" label on the config-approach option.
- `grid_size` is **required** (hard error) when `dim_3d=True` — SC#3's "default
  grid_size" wording is satisfied by the required-error guard + a documented
  *recommended* 24³ value in the field description, NOT by a silent auto-fill.
  Downstream agents must not add a silent default that hides the cubic cost.
- The 2D physical `(x,z) → grid (x,y)` mapping and the 3D physical `(x,y,z) →
  grid (x,y,z)` mapping are deliberately different; do not align them.
- PhiFlow 3D pattern to mirror is the `Wake_Flow` example
  (`infinite_cylinder` obstacle + `Box(x,y,z)` + `StaggeredGrid(x,y,z)` +
  `make_incompressible(v, obstacle, Solve('scipy-direct'))`). Planner should
  verify the installed PhiFlow version supports the 3D `Solve` backend used.

</specifics>

<deferred>
## Deferred Ideas

- **True 3D volume / iso-surface fluid renderer** — `render_fluid_3d` this
  phase is only a 2D z-layer slice fallback delegating to `render_fluid_2d`.
  A real volume/iso renderer is a new capability; belongs in a future phase
  (e.g. a v0.7.0 visualization depth phase).
- **Wiring `add_instrument` + force application into the production
  `SurgicalEnv` episode loop** — currently `add_obstacle` is not called in
  production; SC#2 stability is exercised at the FluidSimulator level. Full
  env-level instrument/fluid coupling (applying computed forces to instrument
  bodies) is a larger capability and belongs in its own phase.
- **Two-way coupling stability fix (cut-cell / SPD monolithic solver)** —
  `two_way` is opt-in and documented unstable on thin instruments this phase;
  making it stable is a research-grade capability (Zarifi & Batty 2017; Qiu et
  al. 2015) and out of scope.
- **GPU fluid acceleration** — PhiFlow CPU-first (PROJECT.md); GPU backend can
  be added when needed.
- **Unifying the 2D global-sum and 3D obstacle-mask force paths** — intentionally
  distinct; not a goal.
- **Anisotropic-domain auto-sizing of `grid_size` from `bounds` aspect ratio** —
  authors set `grid_size` explicitly this phase; an auto-suggest helper could be
  added later.

</deferred>

---

*Phase: 38-3d-fluid-flag-dim-3d-true*
*Context gathered: 2026-06-26 via roadmap + requirements + prior phase artifacts + codebase scout + PhiFlow 3D/coupling research + user discussion*