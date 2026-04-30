# AGENTS.md — surg-rl

**Repository:** Surgical robotics RL training system. MuJoCo / PyBullet backends, Pydantic v2, Stable-Baselines3. Python >=3.10.

## Quick commands

```bash
# Install (editable with dev deps)
pip install -e ".[dev]"
```

**Without editable install**, always prefix with `PYTHONPATH=src` or use `python -m surg_rl.cli`:
```bash
PYTHONPATH=src python -m surg_rl.cli version
PYTHONPATH=src python demos/demo.py --headless --steps 0
```

```bash
# Single file / pattern — pytest.ini auto-adds src/ to pythonpath,
# but *direct python script invocations* need PYTHONPATH=src explicitly.
PYTHONPATH=src pytest tests/test_simulators.py -v
PYTHONPATH=src pytest tests/test_mesh_generation.py -v
PYTHONPATH=src pytest tests/ -m "not integration" -v  # skip integration

# Lint / typecheck order: ruff -> black -> mypy
ruff check src/ tests/
black --check src/ tests/
mypy src/surg_rl

# CLI entrypoint (requires editable install; otherwise use PYTHONPATH=src python -m surg_rl.cli)
surg-rl version
surg-rl train --scene scenes/simple_suturing.json --algorithm PPO --timesteps 100000
surg-rl evaluate --model models/ppo_model.zip

# Demo (always --headless on headless machines)
python demos/demo.py --headless --steps 10000
```

## Architecture (real entrypoints)

```
src/surg_rl/
├── scene_definition/   # schema.py (Pydantic v2), loader.py (JSON/YAML + cache)
├── scene_generation/   # text_parser.py, vision_parser.py, scene_composer.py, templates.py, base_parser.py
├── simulators/         # base_simulator.py (ABC), mujoco_simulator.py, pybullet_simulator.py,
│                       # scene_builder.py (MJCF/URDF gen, primitive .obj fallback)
├── dynamics/           # parameter_randomizer.py, curriculum.py, adaptive_difficulty.py,
│                       # environment_controller.py
├── rl/                 # environment.py (Gymnasium), training.py (SB3),
│                       # observation.py, action.py, rewards.py, callbacks.py
├── utils/              # config.py, logging.py (Rich), mesh_generation.py, vtk_io.py
└── cli.py              # Typer app
```

Package is NOT installed site-wide by default. Use editable install (`pip install -e ".[dev]"`) to make `surg-rl` CLI available.

## Pydantic v2 (hard-earned quirks)

- `Model.model_construct(**data)` is the **only** way to truly skip validation. `Model(**data)` and `Model.model_validate(data)` are equivalent — both validate.
- In `model_validator(mode="after")`, mutate via `self.model_copy(update={...})`; do not mutate `self` in place. Pydantic may copy the model internally and discard the mutation.
- `model_dump()` returns **Enum objects**, not `.value` strings. Convert before YAML serialization (`yaml.dump` will raise `RepresenterError`).

## Simulator backend quirks

- **MuJoCo** stores model as `_model` (private). Test for backend with `hasattr(simulator, "_model")`.
- **PyBullet** stores client as `_physics_client`. Test with `hasattr(simulator, "_physics_client")`.
- `simulator.load_scene(scene)` must be called before `reset()` or `step()`, or it raises `RuntimeError`.
- Scene assets (URDFs / meshes) **do not exist** in `assets/`. `scene_builder` generates primitive `.obj` fallbacks on the fly. Never assume a real asset file exists.

## PyBullet soft body

- `load_scene` must call `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` **before any soft body is loaded**, even on a fresh connect. PyBullet silently fails otherwise.
- `removeBody()` is unsafe for soft bodies. `reset()` reloads the full scene when `_soft_body_ids` is non-empty.
- `_get_vtk_mesh_path()` generates procedural tetrahedral `.vtk` meshes (pure NumPy → `surg_rl/utils/vtk_io.py`). It falls back to triangulated `.obj` if `.vtk` generation fails.

## Testing conventions

- **pytest.ini** already sets `pythonpath = src`, so `pytest tests/` works without `PYTHONPATH=src`. Direct python scripts still need it.
- Prefer **feature-specific test files** over cross-cutting ones to reduce merge conflicts: `test_soft_body.py` > `test_simulators.py`.
- PyBullet soft-body tests are `@pytest.mark.xfail(sys.platform in ("darwin",) or os.environ.get("CI") == "true")`. On macOS this currently produces **XPASS** (it works). Do not remove `xfail`; CI runners remain unstable.
- YAML invalid test strings must be **actually** invalid, not merely looking wrong: `"key: [invalid"` (unclosed bracket) is good; `"key: value\n  nested: invalid"` is valid YAML (multiline scalar) and bad.
- When appending test classes to an existing file from parallel work, first `read` the file to check for overlapping class names and import ordering.
- Integration tests require `pytest.mark.integration`. The suite includes mocked integration tests (`test_cli_integration.py`) that monkey-patch LLM calls.

## Optional field guards (common crash sites)

Always guard before accessing nested attributes on these:
- `InstrumentConfig.pose` — default `None`
- `SceneDefinition.task` — default `None`
- `TissueConfig.physics.pybullet` — default factory exists, so the `.pybullet` itself is always present, but its override fields (`mass`, `scale`, `sim_mesh_path`) default to `None`

## Parallel development (from CLAUDE.md)

- Never use `sed` or `echo -e` to inject multi-line Python blocks. Use `python -c "..."` or the `Edit` tool.
- After parallel agents finish, merge in dependency order: **schema → simulators → scene_generation → rl → tests**. Run `pytest` after each merge.
- Before spawning parallel agents, check `git ls-files` for collision-prone files.

## Environment setup

Copy `.env.example` to `.env`. Key variables:
- `LLM_PROVIDER` / `LLM_API_KEY` — scene generation (openai, anthropic, ollama)
- `DEFAULT_SIMULATOR` — `mujoco` or `pybullet`
- `RANDOMIZATION_ENABLED` — toggle domain randomization

## GSD Project Context

Project is managed with GSD. Key planning artifacts:
- `.planning/PROJECT.md` — living project context, requirements, decisions
- `.planning/REQUIREMENTS.md` — v1/v2 requirements with REQ-IDs and traceability
- `.planning/ROADMAP.md` — 5-phase roadmap (critical bugs → action space → robustness → assets → infrastructure)
- `.planning/STATE.md` — current phase, progress, blockers, deferred items
- `.planning/config.json` — workflow preferences (yolo, standard granularity, parallel, inherit model)
- `.planning/research/` — domain research (STACK, FEATURES, ARCHITECTURE, PITFALLS, SUMMARY)
- `.planning/codebase/` — existing codebase map (from pre-init /gsd-map-codebase)

Next up after new-project: `/gsd-plan-phase 1` to begin Phase 1 (Critical Bug Fixes).
