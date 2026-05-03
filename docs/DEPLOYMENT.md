<!-- generated-by: gsd-doc-writer -->

# DEPLOYMENT.md

## Deployment targets

surg-rl supports three deployment strategies for different environments and compute backends.

### Docker (CPU / headless)

The project includes a multi-stage `Dockerfile` optimized for CPU-only deployment and CI use:

| Stage   | Purpose                                                 |
|---------|---------------------------------------------------------|
| `base`  | `python:3.11-slim` with system libs (OpenGL, GLEW, GLU) |
| `build` | Copies source and installs `surg-rl` with `[dev,tracking]` extras |
| `runtime` | Copies site-packages and source from build; minimal final image |

**Build:**

```bash
docker build -t surg-rl:latest .
```

**Run:**

```bash
# Show version
docker run surg-rl:latest version

# Train a suturing scene (mount data volumes as needed)
docker run -v $(pwd)/scenes:/app/scenes -v $(pwd)/models:/app/models \
  surg-rl:latest train --scene scenes/simple_suturing.json --algorithm PPO --timesteps 100000

# Evaluate a trained model
docker run -v $(pwd)/models:/app/models \
  surg-rl:latest evaluate --model models/ppo_model.zip
```

The default entrypoint is `python -m surg_rl.cli` and overrides are passed as arguments after the image name.

### GPU Docker variants

Dedicated GPU Dockerfiles are provided for NVIDIA CUDA and AMD ROCm environments. Both install Python 3.11 into the respective base image, then install `surg-rl` with `[dev,tracking]` extras.

#### CUDA (NVIDIA)

```bash
# Build
docker build -f Dockerfile.cuda -t surg-rl:cuda .

# Run (requires nvidia-container-toolkit)
docker run --gpus all surg-rl:cuda version --verbose

# Training with GPU acceleration
docker run --gpus all -v $(pwd)/scenes:/app/scenes -v $(pwd)/models:/app/models \
  surg-rl:cuda train --scene scenes/simple_suturing.json --algorithm PPO --timesteps 100000
```

Base image: `nvidia/cuda:12.2.0-runtime-ubuntu22.04`

#### ROCm (AMD)

```bash
# Build
docker build -f Dockerfile.rocm -t surg-rl:rocm .

# Run (requires ROCm kernel driver)
docker run --device /dev/kfd --device /dev/dri surg-rl:rocm version --verbose
```

Base image: `rocm/dev-ubuntu-22.04`

### PyPI (Python package)

The package is published to PyPI for users who want to install directly rather than use Docker. <!-- VERIFY: confirm package is published at https://pypi.org/project/surg-rl/ -->

```bash
pip install surg-rl
```

Alternatively, install from source (editable):

```bash
git clone https://github.com/surg-rl/surg-rl
cd surg-rl
pip install -e ".[dev,tracking]"
```

---

## Build pipeline

### CI workflow (`ci.yml`)

Triggered on **push to `main`** and **pull requests targeting `main`**. Runs on `ubuntu-latest` across a Python version matrix (`3.10`, `3.11`, `3.12`).

| Step         | Command / tool                              |
|------------- |---------------------------------------------|
| Lint         | `ruff check src/ tests/`                    |
| Format check | `black --check src/ tests/`                 |
| Type check   | `mypy src/surg_rl`                          |
| Unit tests   | `pytest tests/ -m "not integration" -v`     |

Dependencies are cached using `actions/cache@v4` keyed on `pyproject.toml`.

### Release workflow (`release.yml`)

Triggered on **tag push matching `v*`** (e.g., `v0.1.0`, `v1.0.0`). Runs on `ubuntu-latest` with Python 3.11.

1. Checkout code at the tag.
2. Install build tools: `build` and `twine`.
3. Run `python -m build` to produce `dist/*.whl` and `dist/*.tar.gz`.
4. Publish to PyPI via `pypa/gh-action-pypi-publish@release/v1`, authenticating with the `PYPI_API_TOKEN` secret.

**Release steps summary:**

```bash
# From a local checkout:
git tag v0.2.0
git push origin v0.2.0
# CI automatically builds and publishes to PyPI
```

---

## Environment setup

### Required environment variables for production

When running in production (deployed Docker container or cloud instance), configure these variables by copying `.env.example` to `.env` and filling in values:

| Variable              | Required | Description                                |
|---------------------- |----------|--------------------------------------------|
| `LLM_PROVIDER`        | Yes      | LLM backend: `openai`, `anthropic`, or `ollama` |
| `LLM_API_KEY`         | Yes      | API key for the chosen provider            |
| `DEFAULT_SIMULATOR`   | No       | `mujoco` (default) or `pybullet`           |
| `RANDOMIZATION_ENABLED` | No     | Toggle domain randomization (`false`)      |
| `RL_DEVICE`           | No       | Torch device: `auto`, `cuda`, or `cpu`     |
| `LOG_LEVEL`           | No       | Logging verbosity (default: `INFO`)        |
| `WANDB_API_KEY`       | No       | Weights & Biases tracking (if using `[tracking]` extras) |

### Docker environment injection

```bash
# With an .env file
docker run --env-file .env surg-rl:latest train --scene scenes/simple_suturing.json

# With individual variables
docker run -e LLM_PROVIDER=openai -e LLM_API_KEY=sk-... surg-rl:latest ...
```

The image already sets `PYTHONPATH=/app/src` and `PYTHONUNBUFFERED=1`.

### Secrets management

| Secret            | Where it is used    | How to set                                               |
|-------------------|---------------------|----------------------------------------------------------|
| `PYPI_API_TOKEN`  | GitHub Actions      | Repository Settings → Secrets and variables → Actions    |
| `LLM_API_KEY`     | Runtime environment | `.env` file or platform secret manager (e.g., Docker secrets, Kubernetes secrets) |

---

## Rollback procedure

### Docker deployment

Redeploy with the previous stable image tag:

```bash
# Pull the last known-good tag
docker pull surg-rl:v0.1.0

# Restart the container
docker stop surg-rl-instance
docker rm surg-rl-instance
docker run -d --name surg-rl-instance surg-rl:v0.1.0
```

### PyPI rollback

If a published release is broken, revert by installing the previous version:

```bash
pip install surg-rl==0.1.0
```

To prevent further installs of the bad version, yank it on PyPI via the web UI or using `twine`. <!-- VERIFY: yanking requires project owner credentials on PyPI -->

### Training checkpoint rollback

If a training run diverges, revert to the last checkpoint:

```bash
# SB3 models are zip archives containing periodic snapshots
cp models/ppo_model_backup.zip models/ppo_model.zip
surg-rl evaluate --model models/ppo_model.zip
```

---

## Monitoring

### Experiment tracking

surg-rl supports two experiment tracking backends via the `[tracking]` optional dependency group:

| Tool            | Package    | Environment setup           |
|-----------------|------------|-----------------------------|
| Weights & Biases | `wandb`    | Set `WANDB_API_KEY`         |
| MLflow          | `mlflow`   | No additional config needed |

To enable during training, ensure the `[tracking]` extras are installed (included by default in all Docker images).

### Logging

The application uses Rich structured logging. Configure via:

- `LOG_LEVEL` environment variable (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- `LOG_FILE` to write logs to a file.

### Health check

A lightweight container health check can be added with:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -m surg_rl.cli version || exit 1
```

This is not included in the default Dockerfiles to keep the images minimal — add it when deploying to orchestrated environments (Kubernetes, Docker Swarm).

### Infrastructure monitoring

For full production observability, consider integrating:

- **GPU metrics**: `nvidia-smi` (CUDA) or `rocm-smi` (ROCm) exposed via Prometheus exporters.
- **Container metrics**: cAdvisor or Docker's built-in `docker stats`.
- **Application monitoring**: <!-- VERIFY: Sentry DSN and other APM endpoints are not configured in this repository — set up externally if needed -->

<!-- VERIFY: all external monitoring dashboard URLs, alert webhook endpoints, and team-specific APM project keys are deployment-specific and not tracked in this repository -->
