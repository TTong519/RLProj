# Stack Research

**Domain:** Surgical-robotics reinforcement learning training system
**Researched:** 2026-04-29
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | >=3.10, <=3.13 | Application language | Scientific-computing lingua franca; SB3 and MuJoCo target 3.10+ |
| MuJoCo | >=3.0.0 | Primary physics simulator | State-of-the-art for robotics; superior rendering (3.x Renderer API) and contact dynamics |
| PyBullet | >=3.2.5 | Secondary simulator (soft-body) | Open-source; only viable open-source soft-body (deformable) physics for surgical tissue |
| Gymnasium | >=0.29.0 | RL environment API | Industry standard successor to OpenAI Gym; SB3-compatible |
| Stable-Baselines3 | >=2.0.0 | RL algorithms | PPO, SAC, TD3, DDPG, A2C in one library with strong community support |
| Pydantic v2 | >=2.0.0 | Schema validation / settings | Runtime validation for JSON/YAML scene definitions; `pydantic-settings` for `.env` config |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| NumPy | >=1.24.0 | Array math | Everywhere; simulator state, observation spaces, mesh generation |
| SciPy | >=1.11.0 | Scientific utilities | Sparse matrices, spatial transforms, signal filtering |
| Pillow | >=10.0.0 | Image I/O | Vision parser pipeline (image preprocessing) |
| OpenCV | >=4.8.0 | Vision preprocessing | Camera image capture, frame transforms |
| Rich | >=13.0.0 | Console output / logging | Styled tables, progress bars, structured logging |
| Typer | >=0.9.0 | CLI framework | `surg-rl` command with subcommands |
| PyYAML | >=6.0 | YAML serialization | Scene save/load alongside JSON |
| tqdm | >=4.65.0 | Progress bars | Training loops and long-running generation |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Test runner | `pythonpath = src`; use `pytest tests/` |
| pytest-cov | Coverage | Target >90% per module |
| pytest-asyncio | Async test support | Scene generation parsers are async |
| black | Formatting | Line length 100; target py310–py312 |
| ruff | Linting | Select E,F,I,N,W,UP,B,C4,SIM; ignore E501 |
| mypy | Type checking | `disallow_untyped_defs = true`; pydantic plugin |
| pre-commit | Git hooks | Import-corruption guard + affected-test runner |

### Optional Dependency Groups

| Group | Packages | Purpose |
|-------|----------|---------|
| `llm` | openai, anthropic | Cloud LLM scene generation |
| `vision` | torch, torchvision, transformers | Local VLM inference |
| `docs` | sphinx, sphinx-rtd-theme, myst-parser | Documentation generation |

## Installation

```bash
# Core + dev
pip install -e ".[dev]"

# Optional LLM support
pip install -e ".[llm]"

# Optional vision support
pip install -e ".[vision]"

# Optional docs support
pip install -e ".[docs]"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| MuJoCo | NVIDIA Isaac Sim | Need photorealistic rendering + massive parallelization; much heavier dependency |
| PyBullet | MuJoCo (soft-body flex) | MuJoCo 3.x has `mjtObj.mjOBJ_FLEX` but PyBullet soft-body is more mature for deformable tissue in surgical contexts |
| Stable-Baselines3 | RLlib (Ray) | Need distributed multi-GPU training at massive scale; SB3 is simpler for single-machine research |
| Typer | Click | Legacy projects already using Click; Typer is cleaner for new CLIs |
| Pydantic v2 | dataclasses + marshmallow | Pydantic v2 is faster and has better IDE support; stick with it |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Poetry / Pipenv | Project uses setuptools with `pyproject.toml`; no lockfile discipline needed in research context | pip + venv |
| OpenAI Gym (legacy) | Deprecated; SB3 has already migrated to Gymnasium | Gymnasium >=0.29.0 |
| Python <3.10 | Union pipe syntax, match/case, better typing; SB3 and MuJoCo drop support below 3.10 | Python 3.10–3.12 |
| Docker (for now) | No containerization in repo; adds complexity for a research CLI tool | venv + editable install |
| Isaac Sim as default | 20GB+ dependency, requires NVIDIA GPU, overkill for surgical-RL research baseline | MuJoCo + PyBullet |

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| stable-baselines3>=2.0.0 | gymnasium>=0.29.0 | SB3 2.x explicitly requires Gymnasium |
| mujoco>=3.0.0 | numpy>=1.24.0 | MuJoCo 3.x uses NumPy C-API; avoid <1.24 |
| pydantic>=2.0.0 | pydantic-settings>=2.0.0 | Settings must be v2-compatible |
| pybullet>=3.2.5 | macOS / Linux / Windows | macOS soft-body may XPASS on some versions; CI xfail still required |

## Sources

- MuJoCo official docs — 3.x Renderer API verified against `mujoco_simulator.py`
- Stable-Baselines3 docs — Gymnasium >=0.29.0 requirement confirmed
- PyBullet Quickstart Guide — `RESET_USE_DEFORMABLE_WORLD` and soft-body gotchas
- AGENTS.md (project-local) — Pydantic v2 quirks and simulator backend conventions
- `.planning/codebase/STACK.md` — existing codebase inventory

---
*Stack research for: surgical-robotics RL training system*
*Researched: 2026-04-29*
