---
focus: integrations
created: 2026-04-29
---

# Integrations

## Summary
Surg-RL integrates with three families of external systems: (1) **LLM/VLM providers** (OpenAI, Anthropic, Ollama) for AI-powered scene generation from text and images; (2) **Physics simulation backends** (MuJoCo, PyBullet) for surgical environment execution; and (3) **RL training infrastructure** (Stable-Baselines3, Gymnasium, optional PyTorch vision stack). No databases, auth providers, webhooks, or traditional cloud services are used.

## LLM / VLM Providers

### OpenAI
- **Client SDK:** `openai>=1.0.0` (OpenAI Python SDK v1+)
- **Used in:** `src/surg_rl/scene_generation/text_parser.py`, `src/surg_rl/scene_generation/vision_parser.py`
- **Models referenced:** `gpt-4-turbo-preview` (text), `gpt-4-vision-preview` (vision)
- **API key source:** `LLM_API_KEY` env var → `Settings.llm_api_key`
- **Endpoints used:** `chat.completions.create` (async via `openai.AsyncOpenAI`)

### Anthropic
- **Client SDK:** `anthropic>=0.18.0`
- **Used in:** `src/surg_rl/scene_generation/text_parser.py`, `src/surg_rl/scene_generation/vision_parser.py`
- **Models referenced:** Claude family (default model configurable)
- **API key source:** Same `LLM_API_KEY` env var
- **Endpoints used:** `messages.create` (async via `anthropic.AsyncAnthropic`)

### Ollama (Local / Self-Hosted)
- **Client:** Custom lightweight wrapper using `httpx` (no dedicated SDK)
- **Used in:** `src/surg_rl/scene_generation/text_parser.py` (lines 135–194, 221–280), `src/surg_rl/scene_generation/vision_parser.py` (lines 138–202)
- **Models referenced:** `llama3.2` (text), `llava` (vision)
- **Base URL:** `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- **Endpoints used:** `POST /api/generate` (text + vision with `images` array)

## Simulation Backends

### MuJoCo
- **Package:** `mujoco>=3.0.0`
- **Used in:** `src/surg_rl/simulators/mujoco_simulator.py` (860 lines)
- **Key API surfaces:**
  - `mujoco.MjModel.from_xml_path()` — MJCF loading
  - `mujoco.MjData()` — simulation state
  - `mujoco.Renderer()` — offscreen rendering (MuJoCo 3.x API)
  - `mujoco.viewer.launch_passive()` — interactive GUI
  - `mjtObj.mjOBJ_FLEX` — soft-body/flex support
- **Scene format:** MJCF (XML) generated procedurally by `scene_builder.py`
- **Config:** `MUJOCO_TIMESTEP` env var (default 0.002)

### PyBullet
- **Package:** `pybullet>=3.2.5`
- **Used in:** `src/surg_rl/simulators/pybullet_simulator.py` (1299 lines)
- **Key API surfaces:**
  - `pybullet.connect()` — physics client (DIRECT / GUI)
  - `resetSimulation(RESET_USE_DEFORMABLE_WORLD)` — soft-body world init
  - `loadURDF()`, `loadSoftBody()` — asset loading
  - `stepSimulation()`, `getCameraImage()` — stepping & rendering
- **Scene format:** URDF/SDF generated procedurally; VTK tetrahedral meshes for soft bodies
- **Config:** `PYBULLET_TIMESTEP` env var (default 1/240 ≈ 0.00417)
- **Caveat:** `removeBody()` unsafe for soft bodies; `reset()` reloads full scene when soft bodies exist

## Reinforcement Learning Framework

### Stable-Baselines3
- **Package:** `stable-baselines3>=2.0.0`
- **Used in:** `src/surg_rl/rl/training.py`, `src/surg_rl/rl/callbacks.py`, `src/surg_rl/rl/environment.py`
- **Algorithms supported:** PPO, SAC, TD3, DDPG, A2C
- **Key SB3 components:**
  - `stable_baselines3.PPO/SAC/TD3/DDPG/A2C`
  - `stable_baselines3.common.callbacks.BaseCallback`
  - `stable_baselines3.common.vec_env.DummyVecEnv`, `SubprocVecEnv`
- **Logging integration:** TensorBoard (`RL_TENSORBOARD_LOG` env var)

### Gymnasium
- **Package:** `gymnasium>=0.29.0`
- **Used in:** `src/surg_rl/rl/environment.py` (main `SurgicalEnv`)
- **Role:** Standard environment interface wrapping simulator + dynamics controller for SB3 consumption

## Image Processing & Vision (Optional)
- **Pillow** (`pillow>=10.0.0`) — Image read/write in vision parser pipeline
- **OpenCV** (`opencv-python>=4.8.0`) — Vision preprocessing
- **PyTorch stack** (`torch>=2.0.0`, `torchvision>=0.15.0`, `transformers>=4.35.0`) — Optional VLM inference (install via `pip install -e ".[vision]"`)

## Environment / Configuration Integration
- **python-dotenv** — Loads `.env` into Pydantic Settings (`src/surg_rl/utils/config.py`)
- **Pydantic Settings** (`pydantic-settings`) — Reads env vars, validates types, provides defaults
- **YAML config** — `configs/default_config.yaml` used as reference/template (loaded via PyYAML in some flows)

## Key Files by Integration

### LLM/VLM
- `src/surg_rl/scene_generation/text_parser.py` — OpenAI / Anthropic / Ollama text parser
- `src/surg_rl/scene_generation/vision_parser.py` — OpenAI / Anthropic / Ollama vision parser
- `src/surg_rl/scene_generation/base_parser.py` — Shared parser base class
- `src/surg_rl/scene_generation/prompts/text_prompts.py` — LLM prompts for text→scene
- `src/surg_rl/scene_generation/prompts/vision_prompts.py` — VLM prompts for image→scene
- `src/surg_rl/utils/config.py` — Settings model with LLM provider / API key / Ollama URL fields
- `.env.example` — Documented env var template for all LLM integrations

### Simulation
- `src/surg_rl/simulators/mujoco_simulator.py` — MuJoCo backend
- `src/surg_rl/simulators/pybullet_simulator.py` — PyBullet backend
- `src/surg_rl/simulators/scene_builder.py` — MJCF / URDF procedural generation
- `src/surg_rl/utils/mesh_generation.py` — Procedural primitive mesh generation (NumPy)
- `src/surg_rl/utils/vtk_io.py` — VTK unstructured grid I/O for PyBullet soft-body meshes

### RL Training
- `src/surg_rl/rl/training.py` — SB3 algorithm mapping, `TrainingManager`
- `src/surg_rl/rl/callbacks.py` — SB3 `BaseCallback` subclasses
- `src/surg_rl/rl/environment.py` — `SurgicalEnv` (Gymnasium wrapper)
- `src/surg_rl/rl/observation.py` — Observation space builders
- `src/surg_rl/rl/action.py` — Action space builders
- `src/surg_rl/rl/rewards.py` — Reward function definitions

## External Services Matrix
| Service | Type | Auth | Used For |
|---------|------|------|----------|
| OpenAI API | REST API | API key (`LLM_API_KEY`) | Text & vision scene generation |
| Anthropic API | REST API | API key (`LLM_API_KEY`) | Text & vision scene generation |
| Ollama (local) | HTTP API | None | Local LLM/VLM inference |
| MuJoCo binaries | Native lib | None (open-source) | Physics simulation |
| PyBullet binaries | Native lib | None (open-source) | Physics simulation |
| TensorBoard (local) | Local dashboard | None | RL training visualization |

## Notable Absences
- **No databases** — Scene data is stored as JSON/YAML files; no SQLite, PostgreSQL, MongoDB, or Redis usage.
- **No auth / identity providers** — No OAuth, SSO, or JWT integrations.
- **No webhooks** — No incoming or outgoing webhook handlers.
- **No cloud storage** — No AWS S3, GCS, or Azure Blob references.
- **No CI/CD pipelines** — `.github/` contains only issue/PR templates; no GitHub Actions workflows.
- **No containerization** — No Dockerfile or docker-compose files.

## Configuration Variables for Integrations
From `.env.example`:

| Variable | Default | Integration |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM/VLM provider selection |
| `LLM_MODEL` | `gpt-4-turbo-preview` | OpenAI text model |
| `LLM_API_KEY` | — | OpenAI / Anthropic auth |
| `VLM_MODEL` | `gpt-4-vision-preview` | OpenAI vision model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama text model |
| `OLLAMA_VISION_MODEL` | `llava` | Ollama vision model |
| `DEFAULT_SIMULATOR` | `mujoco` | Default physics backend |
| `MUJOCO_TIMESTEP` | `0.002` | MuJoCo step size |
| `PYBULLET_TIMESTEP` | `0.004166667` | PyBullet step size |
| `RL_TENSORBOARD_LOG` | `./logs/tensorboard` | SB3 TensorBoard path |
| `RL_DEVICE` | `auto` | SB3 compute device |
