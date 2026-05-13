# Phase 19: Schema Foundation — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 19-schema-foundation
**Areas discussed:** Model naming & placement, Model depth & structure, Lazy import guard pattern, Dependency version pinning

---

## Model naming & placement

### Question 1: How should Phase 19 models relate to existing ones?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend in-place | Add v0.4.0-specific fields to existing MeshAsset/TaskConfig with Optional defaults. New models in same schema.py. | ✓ |
| Separate file per module | Create schema_assets.py, schema_tasks.py, etc. Existing models untouched. | |
| v04_ prefixed models | MeshAssetV04, TaskConfigV04 alongside originals. | |

**User's choice:** Extend in-place (Recommended)

### Question 2: Where should BenchmarkConfig, MultiAgentConfig, DreamerConfig live?

| Option | Description | Selected |
|--------|-------------|----------|
| All in schema.py | Single file, 1282 → ~1600 lines | ✓ |
| Separate v0.4 schema module | New module, schema.py untouched | |

**User's choice:** All in schema.py

**Notes:** Single-file schema convention preserved. MeshAsset and TaskConfig are extended with Optional defaults — backward compatible.

---

## Model depth & structure

### Question 1: How rich should Phase 19 models be?

| Option | Description | Selected |
|--------|-------------|----------|
| Skeletal | Minimal fields, ~50 lines each. Agents fill in later. | ✓ |
| Full-spec, all-optional | Define full field set matching ROADMAP success criteria, all None defaults. | |
| Empty shells + custom dict | Mostly empty BaseModel with extra dict for arbitrary fields. | |

**User's choice:** Skeletal (Recommended)

### Question 2: What skeletal v0.4.0 fields does existing TaskConfig need?

| Option | Description | Selected |
|--------|-------------|----------|
| task_type enum only | task_type: Literal[...] | None = None | ✓ |
| task_type + difficulty | Same plus difficulty: Literal["easy", "medium", "hard"] | None | |
| task_type + generic params | Skeletal but with task_params: dict[str, Any] | |

**User's choice:** task_type enum only

### Question 3: More depth questions or next area?

**Answer:** Let OpenCode decide

---

## Lazy import guard pattern

### Question 1: Where and how should lazy import guards live?

| Option | Description | Selected |
|--------|-------------|----------|
| HAS_* module-level flags | Follow existing HAS_ROS2 pattern | |
| Point-of-use try/except | Simple try/except at import point only | |
| LazyImport helper class | Generic class deferring ImportError until first access | ✓ |

**User's choice:** LazyImport helper class

### Question 2: Where should the LazyImport helper live?

| Option | Description | Selected |
|--------|-------------|----------|
| utils/lazy_imports.py | Single module with LazyImport class + instances | |
| Per-module __init__.py | Each optional group gets its own __init__.py using shared LazyImport | ✓ |
| Let OpenCode decide | | |

**User's choice:** Per-module __init__.py

**Notes:** New packages: `src/surg_rl/assets/__init__.py`, `src/surg_rl/benchmark/__init__.py`, `src/surg_rl/marl/__init__.py`, `src/surg_rl/dreamer/__init__.py`. Each uses a shared `LazyImport` class from `surg_rl/utils/`.

---

## Dependency version pinning

### Question 1: How should the 4 new optional dependency groups pin their versions?

| Option | Description | Selected |
|--------|-------------|----------|
| >= like existing deps | Follow existing pyproject.toml pattern for all | |
| ~= compatible release | ~= for all new deps, blocks major version breaks | |
| Mixed: ~= for JAX, >= for rest | JAX volatile, everything else stable | ✓ |

**User's choice:** Mixed: ~= for JAX, >= for rest

### Question 2: Should dreamerv3 also get ~= pinning?

| Option | Description | Selected |
|--------|-------------|----------|
| ~= for JAX + dreamerv3 | Both pre-1.0/early-stage with volatile APIs | ✓ |
| JAX only | Only JAX, dreamerv3 uses >= | |

**User's choice:** ~= for JAX + dreamerv3

**Notes:** `>= `: trimesh, pettingzoo, supersuit, matplotlib, seaborn, pandas, rliable, optax. `~= `: jax, dreamerv3.

---

## OpenCode's Discretion

- Exact skeletal field set for `MeshAsset` extensions (mesh loading, decimation, fallback)
- Exact skeletal field sets for `BenchmarkConfig`, `MultiAgentConfig`, `DreamerConfig`
- `LazyImport` class implementation details (attribute forwarding, logging, `.available` property)
- Whether `LazyImport` lives in `surg_rl/utils/lazy_imports.py` or `surg_rl/utils/__init__.py`
- Exact pyproject.toml formatting and optional group ordering

## Deferred Ideas

None — discussion stayed within phase scope.
