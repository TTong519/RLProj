# Phase 19: Schema Foundation — Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Define Pydantic v2 models for all five v0.4.0 feature modules and declare their optional dependency groups in `pyproject.toml` — no feature work starts until its schema exists. This phase produces zero runtime behavior, zero new imports during `import surg_rl`, and zero regression in the existing 910 tests.

</domain>

<decisions>
## Implementation Decisions

### Model naming & placement
- **D-01:** Extend existing `MeshAsset` and `TaskConfig` in-place within `schema.py` using `Optional` defaults — no `v04_` prefixes, no separate schema modules
- **D-02:** `BenchmarkConfig`, `MultiAgentConfig`, and `DreamerConfig` all live in `schema.py` alongside the existing 23 models — no new files in `scene_definition/`

### Model depth & structure
- **D-03:** Skeletal models only — define minimal field sets (~50 lines per model) that downstream phases need for routing. All new fields default to `None`. Phases 20–24 extend models with additional fields as needed.
- **D-04:** `TaskConfig` gets **exactly one new field**: `task_type: Literal["suturing", "knot_tying", "needle_insertion", "grasping", "cutting", "dissection"] | None = None`. No difficulty enum, no method stubs, no task_params dict — Phase 21 owns those.

### Lazy import guard pattern
- **D-05:** Use a `LazyImport` helper class (defers `ImportError` to first attribute access) instead of the existing `HAS_*` module-level boolean pattern used in `ros2/__init__.py`
- **D-06:** Per-module structure — each optional dependency group gets its own `__init__.py` package (`src/surg_rl/assets/__init__.py`, `src/surg_rl/benchmark/__init__.py`, `src/surg_rl/marl/__init__.py`, `src/surg_rl/dreamer/__init__.py`) containing a `LazyImport` instance for its primary dependency

### Dependency version pinning
- **D-07:** `>= ` for stable libraries: `trimesh>=4.5.0`, `pettingzoo>=1.24.0`, `supersuit>=3.9.0`, `matplotlib>=3.7.0`, `seaborn>=0.12.0`, `pandas>=2.0.0`, `rliable>=1.0.8`, `optax>=0.1.7`
- **D-08:** `~= ` for volatile APIs: `jax~=0.4.20`, `dreamerv3~=1.5.0` — both have history of breaking changes in minor versions

### OpenCode's Discretion
- Exact skeletal field set for `MeshAsset` extensions (mesh loading, decimation, fallback fields consistent with ASET-01..ASET-05)
- Exact skeletal field sets for `BenchmarkConfig`, `MultiAgentConfig`, `DreamerConfig` based on ROADMAP success criteria for Phases 22–24
- `LazyImport` class implementation details (attribute forwarding, logging optional warnings, `.available` property)
- Whether `LazyImport` lives in `surg_rl/utils/lazy_imports.py` or `surg_rl/utils/__init__.py`
- Exact `pyproject.toml` formatting and optional group ordering

</decisions>

<specifics>
## Specific Ideas

- The existing `HAS_ROS2` pattern is considered legacy — new optional groups should not replicate it. The `LazyImport` approach is preferred as cleaner and more Pythonic.
- Model extension in schema.py must preserve backward compatibility: every existing test, every existing `SceneDefinition.model_dump()` call, every enum serialization path must work unchanged.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 19 — success criteria (3 items: models exist, pyproject.toml groups declared, lazy imports work)
- `.planning/REQUIREMENTS.md` — ASET-05, TASK-01, MARL-03, BENCH-04, DMV3-04 all reference schema models defined here

### Existing schema & dependencies
- `src/surg_rl/scene_definition/schema.py` — all 23 existing Pydantic v2 models (1282 lines). `MeshAsset` at line 224, `TaskConfig` at line 1047, `SceneDefinition` at line 1158
- `pyproject.toml` — existing optional dependency groups pattern (`[llm]`, `[meshing]`, `[simulation]`, `[vision]`, `[tracking]`, `[distributed]`, `[ros2]`)

### Lazy import patterns
- `src/surg_rl/ros2/__init__.py` — existing `HAS_ROS2` module-level flag (legacy pattern — not to be replicated for new groups)

### Architecture & conventions
- `.planning/codebase/ARCHITECTURE.md` — layer diagram, data flow, `SceneDefinition` as single source of truth
- `.planning/codebase/STACK.md` — optional dependency groups table, dependency inventory
- `.planning/codebase/INTEGRATIONS.md` — external services and integration patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Pose`, `Position`, `Orientation`, `AssetReference` base models — reused by `MeshAsset` extensions
- `SimulatorType`, `HardwareBackend` enums — existing pattern for new enums (e.g. task type Literal)
- `BaseModel` with `Field(default_factory=...)` pattern — used for nested config sub-models
- `model_validator(mode="after")` pattern — used when validation spans multiple fields

### Established Patterns
- Pydantic v2 `BaseModel` for all config objects — consistent since Phase 1
- `Field(default=None)` for all optional fields — the `None` default convention
- `Field(description=...)` on every field — docstring-quality descriptions
- Enum classes before models, base models before config models — file ordering convention in schema.py
- `>= ` for core dependencies, platform-specific extras handled separately

### Integration Points
- `pyproject.toml` `[project.optional-dependencies]` — add 4 new groups: `[assets]`, `[benchmark]`, `[marl]`, `[dreamer]`
- `src/surg_rl/` package — 4 new packages with `__init__.py` files using `LazyImport`
- `surg_rl/utils/` — new `LazyImport` class
- All existing tests — must pass with zero modifications after Phase 19

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 19-schema-foundation*
*Context gathered: 2026-05-13*
