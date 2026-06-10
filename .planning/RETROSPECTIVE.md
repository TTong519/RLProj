# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v0.4.0 — Training Infrastructure & Realism

**Shipped:** 2026-06-09
**Phases:** 6 (19–24) | **Plans:** 21 | **Requirements:** 23/23 v1 complete

### What Was Built
- Pydantic v2 schema foundation: 5 new config models (MeshAsset, TaskConfig, BenchmarkConfig, MultiAgentConfig, DreamerConfig) with `None` defaults; 4 new optional dependency groups (`[assets]`, `[benchmark]`, `[marl]`, `[dreamer]`)
- trimesh-based real surgical assets: 9 instrument URDFs with V-HACD collision decomposition, 4 organ OBJ meshes through tetgen deformable pipeline, procedural fallback for missing assets
- 6 surgical task types × 3 difficulty levels via TaskResult Pydantic v2 hierarchy + TaskRewardRouter; CurriculumScheduler extended additively
- PettingZoo `MultiAgentSurgicalEnv` dual-arm training (thin adapter over canonical `SurgicalEnv`); SuperSuit wrappers for SB3; shared and independent policy modes
- SB3 benchmarking framework: `ExperimentRunner` with multiprocessing seed sweeps, IQM + mean±std via rliable, publication plots/tables, per-backend MuJoCo/PyBullet reporting
- DreamerV3 feasibility spike + process-isolated training: `GymToEmbodiedWrapper`, JAX subprocess with `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`, 64×64 RGBA pixel and state observation modes
- Gap closure Plan 24-05: added KNOT_TIER, NEEDLE instrument types; implemented knot_tying, needle_insertion, dissection task types

### What Worked
- **Schema-first foundation unblocked parallel work** — Phases 21 (Tasks) and 22 (MARL) both depended on Phase 20 (Assets), not on each other, and ran independently
- **Optional dependency groups with lazy imports** — `import surg_rl` works without any of trimesh, pettingzoo, dreamerv3 installed; this kept the test suite fast and CI green throughout
- **Additive extension patterns** — TaskResult, MultiAgentConfig, DreamerConfig all added as `None`-defaulted fields on existing models; CurriculumScheduler was extended (not replaced); the Phase 3 `apply_parameters` fix was preserved
- **Process isolation as a first-class design choice** — DreamerV3's JAX subprocess pattern eliminated an entire class of GPU memory conflict issues that would have been a multi-week debug
- **UAT-driven gap closure** — Phase 24's UAT caught a coverage gap (only 3 of 6 task types implemented in `_create_scene_for_task`); Plan 24-05 closed it surgically with one new plan instead of a full phase redo
- **Plan 23-01 retrospective SUMMARY at milestone close** — caught a documentation gap (artifacts existed, summary didn't); the validation was straightforward since downstream plans had consumed the artifacts successfully

### What Was Inefficient
- **Plan 23-01 SUMMARY was missing at close** — artifacts on disk and consumed by downstream plans, but the documentation gap would have been a process failure if not caught. Future milestones should enforce SUMMARY creation as a `gsd-execute-phase` invariant, not a best-effort
- **MARL plan scope creep** — Plan 22-02 added `ObservationFilter` beyond original scope to handle arm-specific observation routing; this was a necessary extension but should have been called out as a delta in the plan
- **DreamerV3 task type set grew post-spike** — original Plan 24-01 implemented 3 task types (suturing, grasping, cutting); Plan 24-05 added 3 more (knot_tying, needle_insertion, dissection) to match Phase 21's task curriculum. The coverage expansion should have been a v0.4.0 goal from the start, not a gap closure
- **PhiFlow quirks carried forward from v0.3.2** — 2D-only constraint and multi-obstacle union() bug remained documented pitfalls. Not a regression but a reminder that library decisions persist
- **Phase 20 organ mesh licensing research deferred** — the question of where to source 4 organ OBJ meshes (procedural vs surgtoolloc) was acknowledged but not resolved; deferred to v0.5.0

### Patterns Established
- **Schema-first with `None` defaults** — When adding a new feature module to an existing codebase, define all Pydantic v2 config models with `None` defaults in a single foundational phase. This lets downstream phases add fields without breaking the schema contract
- **Adapter pattern over duplication** — `MultiAgentSurgicalEnv` is a separate class that owns exactly ONE `SurgicalEnv` and delegates all sim logic. Never duplicate simulation code in the MARL/curriculum/benchmark layers
- **Process isolation for incompatible runtimes** — When two libraries (JAX, PyTorch) share GPU memory in ways that conflict, run one in a subprocess with a memory fraction cap. JSON-line stdin/stdout with ACK handshakes is sufficient for control protocols
- **Reset-in-action protocol for embodied envs** — When wrapping a Gymnasium env for an embodied-style API, embed the reset signal in the action dict (`action['reset'] = True`) rather than adding a separate control channel. The `is_first`/`is_last`/`is_terminal` flags in the observation dict complete the protocol
- **Dual statistical aggregation** — When reporting benchmark results, show both mean±1σ and IQM+CI. Different readers have different priors; giving both is more honest than picking one
- **UAT-driven gap closure** — When verification surfaces coverage gaps that are clearly within the milestone scope, close them with a single plan rather than rolling the milestone forward. Plan 24-05 closed Test 12 in one focused diff
- **Per-backend reporting, never cross-backend aggregation** — When a system supports multiple simulation backends, report results per backend. Cross-backend determinism is a claim that requires extraordinary evidence; per-backend is a defensible default

### Key Lessons
1. **Schema-first pays dividends in parallel execution** — Phases 21 and 22 ran concurrently because Phase 20's schema made their contracts explicit. The cost of one foundational phase is small relative to the savings
2. **Process isolation is cheaper than memory debugging** — A 30-minute subprocess protocol design saved what would have been a multi-week JAX+PyTorch memory investigation
3. **Adapter patterns enforce boundaries** — When the boundary is explicit (a class that owns exactly one of something), it's visible. When it's implicit (functions that share state), it's not
4. **UAT gaps are milestones within milestones** — A gap closure plan (24-05) is cheaper than rolling a phase forward when the gap is well-scoped
5. **Retrospective SUMMARY creation works as a backstop** — When an executor forgets to write a SUMMARY, the artifacts on disk + downstream consumption are usually enough to write a retrospective. But this should be a backstop, not a primary path
6. **Document deferred items at every milestone boundary** — The carry-forward list of deferred items (cut cooldown test, fluid hook, PhiFlow quirks, etc.) needs to be visible at milestone close so they don't get lost

### Cost Observations
- Model mix: 70% deepseek-v4-pro (planning/research/verification), 30% kimi-k2.6 (execution)
- Sessions: ~6-7
- Notable: DeepSeek handled schema design and verification reasoning well; Kimi k2.6 was effective for routine implementation. The gap closure Plan 24-05 was a 1-session scope, demonstrating that small plans can ship quickly when the goal is clear

---

## Milestone: v0.3.2 — Advanced Simulation Features

**Shipped:** 2026-05-06
**Phases:** 4 | **Plans:** 9 | **Commits:** 16

### What Was Built
- Platform-agnostic tetrahedral mesh generation with tetgen 0.8.4 replacing PyVista/VTK (200MB dep savings)
- FEM deformable objects: MuJoCo MJCF `<flex>` + PyBullet Neo-Hookean with auto-derived material params
- Real-time volumetric tetrahedral mesh cutting engine with 5 canonical tet-plane cases, cross-backend MuJoCo/PyBullet integration
- Eulerian grid fluid solver (PhiFlow 3.4.0) with two-way solid coupling for bleeding/irrigation visualization

### What Worked
- In-memory tetgen → MJCF bridge eliminated file I/O dependency, discovered and fixed during milestone audit
- Pure NumPy cutting engine was zero-dependency, fast, and testable in isolation before simulator integration
- Cross-phase integration audit caught 3 bugs (PyBullet AttributeError, missing FluidSimulator init, missing tetgen bridge) that unit tests alone wouldn't find
- Phase 18 plans inlined directly (no separate PLAN.md files) — efficient for a standalone subsystem with clear research

### What Was Inefficient
- PhiFlow 3.4.0 has quirks on Python 3.13+ (PhiML tensor extraction, multi-obstacle union() bug) requiring workarounds
- Phase 15→16 MuJoCo bridge was initially file-only (.node/.ele files) — in-memory path added retroactively
- Phase 16-02 pre-existing test_rl_observation_action needed shape update (50→200) that wasn't caught by the plan
- Tetgen's default `-q` quality mesh refinement produces degenerate tets that caused cutting edge failures
- `removeBody()` being unsafe for PyBullet soft bodies forced full scene reload pattern — fragile but unavoidable

### Patterns Established
- **In-memory bridge pattern:** When two subsystems (tetgen, MJCF) need a data contract, prefer numpy arrays over file I/O
- **Milestone audit before archive:** Cross-phase integration audit catches bugs unit tests miss; run before completing milestone
- **Inline plans for standalone subsystems:** When a phase has clear research and no cross-phase ambiguity, inline plans save overhead
- **Wave-0 Nyquist validation:** Reconstructing VALIDATION.md from PLAN.md + RESEARCH.md ensures every truth claim has a test

### Key Lessons
1. Cross-phase integration is where bugs hide — unit tests verify components, but the seams between them need explicit testing
2. Pure NumPy engines are the right default for scientific computing in Python — zero deps, fast, no binary compatibility issues
3. PhiFlow is powerful but not production-grade — treat it as a reference implementation, plan for potential replacement
4. Pre-existing test assumptions (shape sizes, default configs) need explicit documentation when new phases change them
5. In-memory data flow (numpy arrays) should be the default contract between pipeline stages; files are fallback, not primary

### Cost Observations
- Model mix: 60% deepseek-v4-pro (planning/research), 40% kimi-k2.6 (execution)
- Sessions: ~4-5
- Notable: DeepSeek was highly effective for research and architectural decisions; Kimi k2.6 handled code execution efficiently

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v0.1.0 | 5 | 12 | Initial stabilization, foundational patterns |
| v0.2.0 | 4 | 19 | Distributed training + real robot integration |
| v0.3.0 | 4 | 18 | Production deployment (Docker, K8s, Metal) |
| v0.3.1 | 1 | 1 | Audit gap closure — first milestone audit cycle |
| v0.3.2 | 4 | 9 | Advanced simulation — inline plans, in-memory bridges |
| v0.4.0 | 6 | 21 | Schema-first, optional deps, MARL + DreamerV3, benchmarking |

### Cumulative Quality

| Milestone | Tests | Coverage | Notable |
|-----------|-------|----------|---------|
| v0.1.0 | 607 | — | Foundation |
| v0.2.0 | 775 | — | +168 tests, distributed training |
| v0.3.0 | 826 | — | +51 tests, production infra |
| v0.3.1 | 833 | — | +7 tests, gap closure |
| v0.3.2 | 910 | — | +77 tests, advanced simulation |
| v0.4.0 | TBD | — | +schema+MARL+benchmarking, deferred items carried forward |

### Top Lessons (Verified Across Milestones)

1. **Test boundaries between systems, not just within them** — verified v0.3.1 (5 audit gaps found), v0.3.2 (3 integration bugs caught), v0.4.0 (MARL/DreamerV3 cross-process concerns)
2. **Plan for dependency quirks from day one** — PyBullet soft body fragility, PhiFlow Python 3.13+ issues, tetgen degenerate tet handling, JAX+PyTorch GPU memory conflict
3. **Audit before you archive** — milestone audit cycle (v0.3.1 established, v0.3.2 validated, v0.4.0: UAT-driven gap closure) catches cross-phase issues unit tests miss
4. **Schema-first with `None` defaults unblocks parallel work** — v0.4.0 Phases 21 (Tasks) and 22 (MARL) ran in parallel because Phase 19 schema made contracts explicit
5. **Adapter patterns over duplication** — `MultiAgentSurgicalEnv` owns one `SurgicalEnv` and delegates; the boundary is visible. Implicit shared state hides bugs
