# Feature Research

**Domain:** Surgical robotics RL training system
**Researched:** 2026-04-29
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Scene definition (JSON/YAML) | Every simulator needs a declarative scene format | LOW | Already implemented via Pydantic v2 schema |
| Scene loader with validation | Invalid scenes crash simulators; validation prevents cryptic errors | LOW | LRU cache + asset validation in place |
| Multi-backend simulation | Researchers expect at least one mainstream physics engine | MEDIUM | MuJoCo + PyBullet both functional |
| RL environment wrapper | Gymnasium is the standard interface for SB3 and other RL libs | LOW | `SurgicalEnv` with `make_vec_env()` exists |
| Training pipeline (SB3) | Users expect `model.learn()` out of the box | MEDIUM | 5 algorithms + callbacks + TensorBoard |
| Domain randomization | Table stakes for sim-to-real transfer in robotics | MEDIUM | Physics/visual/dynamics randomization implemented |
| CLI | Research tools need command-line ergonomics | LOW | Typer-based `surg-rl` with version/config/generate/train/evaluate |
| Demos & examples | Users need to see it work in 5 minutes | LOW | `demo.py`, `train_demo.py`, `eval_demo.py`, plus Python API examples |
| Tests | Trust in research code requires test coverage | MEDIUM | 487 tests at ~92% coverage |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LLM/VLM scene generation | Describe a surgery in natural language → get a scene | MEDIUM | OpenAI, Anthropic, Ollama support; 8 built-in templates |
| Curriculum learning | Progressive difficulty for faster convergence | MEDIUM | 4-stage curriculum with auto-advancement |
| Adaptive difficulty | Performance-driven difficulty tuning per episode | MEDIUM | Linear, exponential, proportional, threshold strategies |
| Soft-body physics | Deformable tissue is critical for surgical realism | HIGH | PyBullet with procedural `.vtk` tetrahedral meshes |
| Dual-backend unified API | Switch MuJoCo ↔ PyBullet without changing scene definition | MEDIUM | `BaseSimulator` ABC + duck-typing backend detection |
| Observation noise injection | Realistic sensor noise for robust policies | LOW | Built into `ObservationBuilder` |
| Composite reward functions | Task-specific reward shaping (suturing, dissection, needle passing) | MEDIUM | 10+ built-in reward components |

### Anti-Features (Things to Deliberately NOT Build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time web dashboard | "I want to monitor training from my phone" | Adds web stack (JS, websockets, auth); not core to RL training | TensorBoard + local CLI logs |
| Cloud training orchestration | "Train on AWS/GCP" | Cost/complexity overkill for research code; users have their own infrastructure | Local SB3 + optional manual cluster |
| Real patient data support | "Use real surgical videos" | HIPAA, GDPR, medical-device compliance; turns research tool into liability | Keep synthetic / procedural only |
| Game-like 3D UI | "Make it look like a video game" | Rendering fidelity is secondary to physics accuracy; MuJoCo Renderer is sufficient | Use MuJoCo/PyBullet built-in viewers |
| Built-in mesh asset library | "Ship with surgical models" | Licensing nightmares; meshes are domain-specific and vary by institution | Procedural primitives + user-provided assets |

## Feature Dependencies

```
Scene Generation (LLM/VLM)
    └──requires──> Scene Definition (schema + loader)
                       └──requires──> Simulator Backend
                                          └──requires──> RL Environment
                                                            └──requires──> Training Pipeline

Domain Randomization ──enhances──> RL Environment
Curriculum Learning ──enhances──> Training Pipeline
Adaptive Difficulty ──enhances──> Training Pipeline
Soft-Body Physics ──conflicts──> MuJoCo (PyBullet only)
```

### Dependency Notes

- **Scene Generation requires Scene Definition:** LLM output must validate against Pydantic schema before simulator can load it.
- **Simulator Backend requires Scene Definition:** Both MuJoCo and PyBullet consume `SceneDefinition` via `SceneBuilder`.
- **RL Environment requires Simulator:** `SurgicalEnv` wraps `BaseSimulator` + `EnvironmentController`; no simulator = no environment.
- **Training Pipeline requires RL Environment:** SB3 algorithms call `env.step()` and `env.reset()`.
- **Soft-Body Physics conflicts with MuJoCo:** Current MuJoCo soft-body support (`mjOBJ_FLEX`) is experimental; PyBullet's soft-body is more mature. Users choose backend per scene.

## MVP Definition

### Launch With (v1)

- [x] Scene definition (JSON/YAML schema + loader) — foundational for everything
- [x] Simulator backends (MuJoCo + PyBullet) — must run physics
- [x] RL environment (Gymnasium wrapper) — must be trainable
- [x] Training pipeline (SB3, 5 algorithms, callbacks, TensorBoard) — core value
- [x] CLI (generate, train, evaluate) — user interface
- [x] Domain randomization + curriculum learning — sim-to-real table stakes
- [x] Tests (>90% coverage) — trust signal
- [ ] Gripper actuation (currently TODO) — essential for manipulation tasks
- [ ] Joint control in demos (currently static) — otherwise demos are not illustrative
- [ ] Fix 8 critical bugs with unexecuted fix plans — stability

### Add After Validation (v1.x)

- [ ] VLM image → scene (vision generation) — currently text-only is robust; image path needs more validation
- [ ] Real asset mesh loading (URDF/DAE/OBJ from external files) — currently primitive fallback only
- [ ] Multi-agent scenes (multiple robots cooperating) — architecture supports it but not tested
- [ ] Task geometry binding from objectives — currently stub observations

### Future Consideration (v2+)

- [ ] NVIDIA Isaac Sim backend — photorealistic rendering, massive parallelization
- [ ] ROS2 integration — publish simulator state to ROS topics
- [ ] Real hardware teleoperation — map trained policy to physical surgical robot
- [ ] Cloud training metrics + experiment tracking (Weights & Biases, MLflow) — currently only TensorBoard

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Scene definition + loader | HIGH | LOW | P1 |
| Simulator backends | HIGH | MEDIUM | P1 |
| RL environment + training | HIGH | MEDIUM | P1 |
| CLI | MEDIUM | LOW | P1 |
| Gripper actuation | HIGH | LOW | P1 |
| Fix critical bugs | HIGH | LOW | P1 |
| Domain randomization | MEDIUM | MEDIUM | P1 |
| Curriculum learning | MEDIUM | MEDIUM | P2 |
| Adaptive difficulty | MEDIUM | MEDIUM | P2 |
| LLM scene generation | MEDIUM | MEDIUM | P2 |
| Soft-body physics | HIGH | HIGH | P2 |
| Vision → scene generation | LOW | MEDIUM | P3 |
| Real meshes/URDF | LOW | HIGH | P3 |
| Multi-agent | LOW | HIGH | P3 |

## Competitor Feature Analysis

| Feature | dVRK (JHU) | SimSpark / RobotMesh | Surg-RL Approach |
|---------|------------|----------------------|------------------|
| LLM scene generation | ❌ None | ❌ None | ✅ Natural language → JSON scene |
| MuJoCo + PyBullet dual | ❌ dVRK uses custom | ❌ Varies by project | ✅ Unified `BaseSimulator` API |
| Curriculum + adaptive difficulty | ❌ Manual tuning | ❌ Manual tuning | ✅ Built-in scheduler + controller |
| Soft-body tissue | ⚠️ Limited | ❌ Rigid-body only | ✅ PyBullet soft-body with `.vtk` |
| SB3 integration | ❌ Custom ROS | ❌ Custom | ✅ One-line `train()` with 5 algorithms |
| Scene templates | ❌ None | ❌ None | ✅ 8 pre-built surgical tasks |
| Open-source license | ✅ LGPL | ✅ Varies | ✅ MIT |

## Sources

- dVRK (da Vinci Research Kit) documentation — surgical robotics baseline
- MuJoCo Menagerie — robot model zoo, confirms MuJoCo surgical relevance
- PyBullet examples — soft-body robotics use cases
- Stable-Baselines3 docs — algorithm coverage and Gymnasium compatibility
- AGENTS.md + README.md — existing feature inventory

---
*Feature research for: surgical-robotics RL training system*
*Researched: 2026-04-29*
