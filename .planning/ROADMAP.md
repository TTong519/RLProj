# Roadmap: Surg-RL

## Milestones

- ✅ **v0.1.0 Core Pipeline** — Phases 1-5 (shipped 2026-05-02)
- ✅ **v0.2.0 Scaling, Rendering & Real Robot** — Phases 6-9 (shipped 2026-05-03)
- 📋 **v0.3.0 Deployment & Production** — Phases 10-12 (planned)

## Phases

<details>
<summary>✅ v0.1.0 Core Pipeline (Phases 1-5) — SHIPPED 2026-05-02</summary>

- [x] Phase 1: Critical Bug Fixes (3 plans)
- [x] Phase 2: Action Space & Gripper (3 plans)
- [x] Phase 3: Simulator Robustness (2 plans)
- [x] Phase 4: Task Geometry & Real Assets (2 plans)
- [x] Phase 5: Experiment Tracking (2 plans)

</details>

<details>
<summary>✅ v0.2.0 Scaling, Rendering & Real Robot (Phases 6-9) — SHIPPED 2026-05-03</summary>

- [x] Phase 6: Universal Hardware Acceleration (3 plans)
- [x] Phase 7: Real-time Rendering (3 plans)
- [x] Phase 8: Distributed Training with Ray/RLlib (6 plans)
- [x] Phase 9: ROS2 Bridge for Real Hardware (7 plans)

</details>

### 📋 v0.3.0 Deployment & Production (Planned)

**Goal:** Containerize for production, deploy to Kubernetes, support multi-architecture builds, and integrate `ros2_control` for real hardware control.

- [ ] Phase 10: Kubernetes deployment manifests
- [ ] Phase 11: Multi-platform Docker (arm64/amd64 buildx)
- [ ] Phase 12: ros2_control hardware_interface + launch files

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Critical Bug Fixes | v0.1.0 | 3/3 | Complete | 2026-05-02 |
| 2. Action Space & Gripper | v0.1.0 | 3/3 | Complete | 2026-05-02 |
| 3. Simulator Robustness | v0.1.0 | 2/2 | Complete | 2026-05-02 |
| 4. Task Geometry & Assets | v0.1.0 | 2/2 | Complete | 2026-05-02 |
| 5. Experiment Tracking | v0.1.0 | 2/2 | Complete | 2026-05-02 |
| 6. Hardware Acceleration | v0.2.0 | 3/3 | Complete | 2026-05-03 |
| 7. Real-time Rendering | v0.2.0 | 3/3 | Complete | 2026-05-03 |
| 8. Distributed Training | v0.2.0 | 6/6 | Complete | 2026-05-03 |
| 9. ROS2 Bridge | v0.2.0 | 7/7 | Complete | 2026-05-03 |
| 10. Kubernetes | v0.3.0 | 0/— | Not started | — |
| 11. Multi-platform Docker | v0.3.0 | 0/— | Not started | — |
| 12. ros2_control | v0.3.0 | 0/— | Not started | — |

---

## Notes

- **Optional dependency groups** (`[distributed]`, `[ros2]`) keep core install lightweight.
- **ROS2 is Linux-only** — macOS gracefully degrades with Docker instructions.
- **Ray 2.10+** requires Python ≥3.9; compatible with ≥3.10.
- **GPU detection** uses torch.cuda + nvidia-smi/rocminfo as primary channels.

---

*Roadmap updated: 2026-05-03 after v0.2.0 milestone closure*
