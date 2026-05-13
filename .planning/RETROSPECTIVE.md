# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

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

### Cumulative Quality

| Milestone | Tests | Coverage | Notable |
|-----------|-------|----------|---------|
| v0.1.0 | 607 | — | Foundation |
| v0.2.0 | 775 | — | +168 tests, distributed training |
| v0.3.0 | 826 | — | +51 tests, production infra |
| v0.3.1 | 833 | — | +7 tests, gap closure |
| v0.3.2 | 910 | — | +77 tests, advanced simulation |

### Top Lessons (Verified Across Milestones)

1. **Test boundaries between systems, not just within them** — verified v0.3.1 (5 audit gaps found) and v0.3.2 (3 integration bugs caught)
2. **Plan for dependency quirks from day one** — PyBullet soft body fragility, PhiFlow Python 3.13+ issues, tetgen degenerate tet handling
3. **Audit before you archive** — milestone audit cycle (v0.3.1 established, v0.3.2 validated) catches cross-phase issues unit tests miss
