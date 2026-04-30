# Surg-RL

## What This Is

A comprehensive surgical-robotics reinforcement learning training system. It generates and simulates surgical scenes from text/images via LLM/VLM, then trains RL agents (PPO, SAC, TD3, DDPG, A2C) in MuJoCo or PyBullet with domain randomization, curriculum learning, and adaptive difficulty. Built for robotics researchers and surgical training simulators.

## Core Value

End-to-end pipeline from a text description or JSON scene definition to a trained RL policy in a realistic surgical simulation — with automatic primitive fallbacks when real assets are missing.

## Requirements

### Validated

- ✓ Scene definition schema (Pydantic v2) — supports robots, tissues, instruments, physics, tasks, domain randomization
- ✓ Scene loader with JSON/YAML parsing, LRU cache, and asset validation
- ✓ LLM/VLM scene generation via OpenAI, Anthropic, and Ollama + 8 pre-built surgical task templates
- ✓ Dual-backend simulation (MuJoCo 3.x and PyBullet ≥3.2.5) with unified `BaseSimulator` API
- ✓ Procedural mesh generation (box, sphere, cylinder) and VTK I/O for soft bodies
- ✓ Domain randomization (physics / visual / dynamics)
- ✓ Curriculum scheduler (Easy → Medium → Hard → Expert)
- ✓ Adaptive difficulty controller (performance-driven scaling)
- ✓ Gymnasium-compatible `SurgicalEnv` with observation/action/reward builders
- ✓ SB3 training pipeline wired for 5 algorithms with callbacks and TensorBoard logging
- ✓ Typer CLI (`surg-rl`) with version, config, setup, generate, train, evaluate commands
- ✓ 487 passing tests across 13 test modules with ~92% coverage
- ✓ Documentation (Getting Started, API Reference, Scene Format, Architecture, Dynamics API, Testing)

### Active

- [ ] Implement real robot joint control (objects currently static in demos)
- [ ] Implement gripper actuation for both backends
- [ ] Implement unimplemented action types: `JOINT_TORQUES`, `ENDEFFECTOR_POSE`, `ENDEFFECTOR_DELTA`
- [ ] Fix 8 critical bugs captured in unexecuted fix plans (quaternion order, joint reset, physics=None, collision penalty, vision prompt JSON, curriculum apply_parameters, LightConfig validator, VecEnv evaluate)
- [ ] Add real asset meshes/URDFs alongside current primitive fallbacks
- [ ] Bind task geometry from objectives to observation fields (needle_pos, entry_point, exit_point, incision_progress)
- [ ] Add real-time rendering during RL training (currently synchronous and blocks training loop)
- [ ] Improve vectorized evaluation reuse (currently creates fresh env each call)

### Out of Scope

- Mobile app — Web/library-first, mobile applications are a different product
- Real-time multi-user networked surgery — Single-agent training scope
- FDA certification / medical-grade safety validation — Research and simulation tool, not clinical device
- Unity/Unreal rendering backends — MuJoCo and PyBullet rendering is sufficient

## Context

This repository was rapidly prototyped as an alpha build. It has comprehensive abstractions but several critical bugs remain documented in unexecuted fix plans under `docs/superpowers/plans/`. The codebase is well-tested (487 passing tests) but has known gaps: 8 critical bugs, unimplemented action types, and missing real asset files. PyBullet soft-body support is functional on macOS but marked as xfail for CI runners.

The `.planning/codebase/` map was created 2026-04-29 and serves as the brownfield discovery record for all existing architecture, stack, conventions, and concerns.

## Constraints

- **Tech stack**: Python ≥3.10, MuJoCo / PyBullet, Gymnasium, Stable-Baselines3, Pydantic v2, Typer, Rich
- **Assets**: No real mesh/URDF files exist in `assets/` — we use procedural `.obj` and `.vtk` fallbacks
- **Test stability**: PyBullet soft-body tests xfail on darwin/CI; known issue not to remove
- **API key exposure**: `.env.example` has placeholder key; no masking in logs

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pydantic v2 as system schema | Strong typing, validation, and serialization across JSON/YAML configs | ✓ Good — single source of truth |
| Dual simulator backends (MuJoCo + PyBullet) | MuJoCo for performance, PyBullet for soft-body deformable physics | ✓ Good — flexibility at cost of maintenance |
| Procedural primitive fallbacks instead of real assets | Lightweight repo, avoids licensing and distribution of surgical meshes | ⚠️ Revisit — visual fidelity limits production use |
| LLM/VLM-based scene generation | Natural language input reduces barrier to scene creation | ✓ Good — reduces config boilerplate |
| No site-wide install (editable only) | Matches research-tool convention where users modify source | ✓ Good — prevents stale-site issues |
| Backend detection via duck typing (`hasattr`) | Avoids explicit simulator-type enums in controller layer | ⚠️ Revisit — fragile, breaks with internal API changes |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-29 after initialization*
