# Requirements: Surg-RL v0.3.1

**Defined:** 2026-05-04
**Milestone:** v0.3.1 — Audit Gap Closure
**Core Value:** End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation

## v1 Requirements

Requirements for v0.3.1 release. Each maps to roadmap phases.

### Infrastructure Wiring

- [x] **GAP-01**: `Dockerfile.ros2` image is built and pushed to GHCR by release workflow (`release.yml`)
- [x] **GAP-02**: Training Job uses CUDA image (`ghcr.io/surg-rl/surg-rl/cuda:v0.3.0`) when GPU resources are requested
- [x] **GAP-03**: initContainer health check uses ROS2 topic probe instead of TCP port check
- [x] **GAP-04**: `bridge_node` and `replay_node` registered as console_scripts in `pyproject.toml` for ros2 launch discovery
- [x] **GAP-05**: `config.py:_mps_available()` imports from `gpu.py` instead of duplicating Metal detection logic

## Out of Scope

| Feature | Reason |
|---------|--------|
| Helm chart | Kustomize overlays sufficient; deferred |
| New features | v0.3.1 is a gap-closure patch only |
| E2E K8s integration tests | Requires real K8s cluster; documented as manual-only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GAP-01 | Phase 14 | Pending |
| GAP-02 | Phase 14 | Pending |
| GAP-03 | Phase 14 | Pending |
| GAP-04 | Phase 14 | Pending |
| GAP-05 | Phase 14 | Pending |

**Coverage:**
- v1 requirements: 5 total
- Mapped to phases: 5
- Unmapped: 0 ✓

---

*Requirements defined: 2026-05-04*
*Last updated: 2026-05-04 after initial definition*
