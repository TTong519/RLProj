<!-- generated-by: gsd-doc-writer -->

# DEPLOYMENT.md

## Deployment targets

surg-rl supports multiple deployment strategies for different environments and compute backends,
including CPU, GPU (CUDA/ROCm), Jetson edge devices, ROS2-enabled robotics stacks, and
Kubernetes orchestration.

### Docker (CPU / headless)

The CPU `Dockerfile` supports **multi-architecture builds** (linux/amd64 + linux/arm64) via `docker buildx`.
Base image: `python:3.11-slim`.

**Build:**
```bash
# Multi-arch build (requires QEMU)
docker buildx build --platform linux/amd64,linux/arm64 -t surge-rl:latest .
```

**Run:**
```bash
docker run surge-rl:latest version
docker run -v $(pwd)/scenes:/app/scenes surge-rl:latest train --scene /app/scenes/simple_suturing.json
```

The image sets `PYTHONPATH=/app/src` and `PYTHONUNBUFFERED=1` by default. Entrypoint is
`python -m surg_rl.cli`.

### GPU Docker variants

Dedicated GPU Dockerfiles are provided for NVIDIA CUDA, AMD ROCm, and NVIDIA Jetson edge devices.
All install Python 3.11 into the respective base image, then install `surg-rl` with `[dev,tracking]`
extras (Jetson omits `dev` extras to reduce image size).

#### CUDA (NVIDIA)

```bash
# Build (amd64 only — no arm64 CUDA base image)
docker buildx build --platform linux/amd64 -f Dockerfile.cuda -t surge-rl:cuda .

# Run (requires NVIDIA Container Toolkit)
docker run --gpus all surge-rl:cuda version --verbose
```

Base image: `nvidia/cuda:12.2.0-runtime-ubuntu22.04`

#### ROCm (AMD)

```bash
# Build
docker buildx build --platform linux/amd64 -f Dockerfile.rocm -t surge-rl:rocm .

# Run (requires ROCm kernel driver)
docker run --device /dev/kfd --device /dev/dri surge-rl:rocm version --verbose
```

Base image: `rocm/dev-ubuntu-22.04`

#### Jetson (NVIDIA edge AI)

For NVIDIA Jetson devices running JetPack 6.0 L4T (Ubuntu 22.04, CUDA 12.4, cuDNN 9.x, TensorRT 10.x):

```bash
# Build (arm64 only — cross-compile from x86 host with QEMU)
docker buildx build --platform linux/arm64 -f Dockerfile.jetson -t surge-rl:jetson .

# Run on the Jetson device
docker run --runtime=nvidia surge-rl:jetson version --verbose
```

Base image: `nvcr.io/nvidia/l4t-pytorch:r36.4.0-pth2.5.0`. This image includes
PyTorch 2.5.0 pre-built for arm64+L4T, so `[tracking]` extras are installed (no `[dev]`).

### ROS2 bridge

A ROS2-enabled image provides the `ros2-bridge` command for integrating surg-rl with
ROS2-based robotic systems. The bridge runs as a ROS2 node using `rclpy` (ROS2 Humble).

```bash
# Build
docker buildx build --platform linux/amd64 -f Dockerfile.ros2 -t surge-rl:ros2 .

# Run the bridge
docker run surge-rl:ros2 ros2-bridge --scene /app/scenes/minimal_scene.json
```

Base image: `ros:humble-ros-base`. Installs `surg-rl` with `[ros2]` extras (PyYAML, launch,
launch_ros). The `Dockerfile.ros2` CMD is `ros2-bridge --help`.

ROS2-related project scripts (entrypoints in `pyproject.toml`):
- `bridge_node` — `surg_rl.ros2.bridge_node:main`
- `replay_node` — `surg_rl.ros2.replay_node:main`

ROS2 launch files are shipped under `share/surg_rl/launch/`:
- `bridge.launch.py` — controller_manager + bridge node + robot_state_publisher
- `replay.launch.py` — controller_manager + trajectory replay node

### Kubernetes

The `k8s/` directory provides Kustomize-based Kubernetes manifests with GPU and CPU overlays.

```
k8s/
├── base/
│   ├── kustomization.yaml      # aggregates all base resources
│   ├── training-job.yaml       # Job with ROS2 bridge sidecar
│   ├── raycluster.yaml         # RayCluster for distributed RL
│   ├── rayjob.yaml             # RayJob for batch distributed training
│   ├── configmap.yaml          # scene config (placeholder JSON)
│   ├── secret.yaml             # LLM API key + model registry token
│   ├── pvc.yaml                # 50Gi persistent volume for checkpoints
│   └── rbac.yaml               # ServiceAccount + Role + RoleBinding
└── overlays/
    ├── gpu/
    │   └── kustomization.yaml  # references base (GPU nodeSelector retained)
    └── cpu/
        └── kustomization.yaml  # patches: removes GPU nodeSelector,
                                # tolerations, resource requests; uses CPU image
```

**Deploy GPU variant:**
```bash
kubectl apply -k k8s/overlays/gpu
```

**Deploy CPU variant:**
```bash
kubectl apply -k k8s/overlays/cpu
```

#### ROS2 bridge as a Kubernetes sidecar

The `training-job.yaml` deploys the ROS2 bridge as a **sidecar container** alongside the
trainer. Pattern:

1. **Init container** (`ghcr.io/surg-rl/surg-rl/ros2:v0.3.0`) waits for ROS2 topics
   (`ros2 topic list | grep surg_rl`) to confirm the bridge is ready.
2. **Trainer container** (`ghcr.io/surg-rl/surg-rl/cuda:v0.3.0`) runs
   `surg-rl train` with `SURGRL_BRIDGE_SIDECAR=true`.
3. **Bridge container** (`ghcr.io/surg-rl/surg-rl/ros2:v0.3.0`) runs
   `surg-rl ros2-bridge` on port 9090.

Both the trainer and bridge mount a scene ConfigMap (`surg-rl-scene`) and a checkpoint PVC
(`surg-rl-checkpoints`, 50Gi, ReadWriteOnce).

#### Distributed training (Ray)

Two Ray resources are available:

| Resource    | Kind        | Use case                                    |
|-------------|-------------|---------------------------------------------|
| RayCluster  | RayCluster  | Long-running cluster for iterative training |
| RayJob      | RayJob      | One-shot batch training with auto-shutdown  |

Both use `rayVersion: "2.55.0"`. The `RayJob` entrypoint is:
```
python -m surg_rl.cli train-rllib --scene /etc/surg-rl/scene.json --timesteps 1000000
```

Worker group: `gpu-workers` with 1–4 replicas, each requesting 1 GPU, 4 CPU, 8Gi memory.

### PyPI (Python package)

The package is published to PyPI for users who want to install directly rather than use Docker.
<!-- VERIFY: confirm package is published at https://pypi.org/project/surg-rl/ -->

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

Triggered on **push to `main`** and **pull requests targeting `main`**. Runs across a matrix
of `ubuntu-latest` (Python 3.10, 3.11, 3.12) and `macos-latest` (Python 3.11).

| Step         | Platform | Command / tool                              |
|------------- |----------|---------------------------------------------|
| Lint         | Linux    | `ruff check src/ tests/`                    |
| Format check | Linux    | `black --check src/ tests/`                 |
| Type check   | Linux    | `mypy src/surg_rl`                          |
| Unit tests   | Linux    | `pytest tests/ -m "not integration" -v`     |
| Unit tests   | macOS    | `mjpython -m pytest tests/ -m "not integration" -v` (skips ROS2 tests) |

macOS uses **mjpython** (MuJoCo's bundled Python binary) for test execution, which provides
the required MuJoCo runtime libraries. ROS2 tests (`test_ros2_bridge.py`, `test_ros2_cli.py`,
`test_ros2_controller.py`, `test_ros2_replay.py`) are ignored on macOS.

Dependencies are cached using `actions/cache@v4` keyed on `pyproject.toml`.

#### Docker CI builds (`docker-ci` job)

The `docker-ci` job builds all Docker variants on every CI run (push=false, no registry push):

| Variant | Dockerfile        | Platforms          |
|---------|-------------------|--------------------|
| CPU     | `Dockerfile`      | linux/amd64, linux/arm64 |
| CUDA    | `Dockerfile.cuda` | linux/amd64        |
| ROCm    | `Dockerfile.rocm` | linux/amd64        |
| Jetson  | `Dockerfile.jetson` | linux/arm64      |

All builds use GitHub Actions cache for layer caching (`type=gha`).

### Release workflow (`release.yml`)

Triggered on **tag push matching `v*`** (e.g., `v0.1.0`, `v1.0.0`).

#### PyPI release (`build-and-publish` job)

Runs on `ubuntu-latest` with Python 3.11.

1. Checkout code at the tag.
2. Install build tools: `build` and `twine`.
3. Run `python -m build` to produce `dist/*.whl` and `dist/*.tar.gz`.
4. Publish to PyPI via `pypa/gh-action-pypi-publish@release/v1`, authenticating with the
   `PYPI_API_TOKEN` secret.

#### GHCR container release (`docker-release` job)

Pushes multi-arch Docker images to GitHub Container Registry. Requires
`packages: write` permission.

| Image                          | Dockerfile        | Platforms          | Tags (semver)                           |
|------------------------------- |-------------------|--------------------|------------------------------------------|
| `ghcr.io/surg-rl/surg-rl`      | `Dockerfile`      | linux/amd64, linux/arm64 | version, major.minor, sha           |
| `ghcr.io/surg-rl/surg-rl/cuda` | `Dockerfile.cuda` | linux/amd64        | version, major.minor                     |
| `ghcr.io/surg-rl/surg-rl/ros2` | `Dockerfile.ros2` | linux/amd64        | version, major.minor                     |

Tags follow `docker/metadata-action@v5` semver patterns:
- `type=semver,pattern={{version}}` — exact version (e.g., `v0.1.0`)
- `type=semver,pattern={{major}}.{{minor}}` — floating minor (e.g., `v0.1`)
- `type=sha,prefix=` — commit SHA (CPU image only)

**Release steps summary:**

```bash
# From a local checkout:
git tag v0.2.0
git push origin v0.2.0
# CI automatically builds and publishes to PyPI, then pushes Docker images to GHCR
```

---

## Environment setup

### Required environment variables for production

When running in production (deployed Docker container, cloud instance, or Kubernetes), refer
to CONFIGURATION.md for the full variable listing. Key production variables from `.env.example`:

| Variable              | Required | Default       | Description                                |
|---------------------- |----------|---------------|--------------------------------------------|
| `LLM_PROVIDER`        | Yes      | `openai`      | LLM backend: `openai`, `anthropic`, or `ollama` |
| `LLM_API_KEY`         | Yes      | —             | API key for the chosen provider            |
| `LLM_MODEL`           | No       | `gpt-4-turbo-preview` | Model name for scene generation      |
| `VLM_MODEL`           | No       | `gpt-4-vision-preview` | Vision model for visual scene parsing |
| `DEFAULT_SIMULATOR`   | No       | `mujoco`      | `mujoco` or `pybullet`                     |
| `RL_DEVICE`           | No       | `auto`        | Torch device: `auto`, `cuda`, `cpu`, `mps` |
| `RANDOMIZATION_ENABLED` | No     | `false`       | Toggle domain randomization                |
| `LOG_LEVEL`           | No       | `INFO`        | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FILE`            | No       | —             | Optional log file path                     |
| `WANDB_API_KEY`       | No       | —             | Weights & Biases tracking (requires `[tracking]` extras) |

### Docker environment injection

```bash
# With an .env file
docker run --env-file .env surge-rl:latest train --scene /app/scenes/simple_suturing.json

# With individual variables
docker run -e LLM_PROVIDER=openai -e LLM_API_KEY=sk-... surge-rl:latest ...
```

The image already sets `PYTHONPATH=/app/src` and `PYTHONUNBUFFERED=1`.

### Kubernetes environment injection

In Kubernetes, sensitive values are stored in a Secret (`surg-rl-secrets`) with keys:

| Secret key            | Purpose              |
|-----------------------|----------------------|
| `llm-api-key`         | Provider API key     |
| `model-registry-token` | Model checkpoint registry auth |

The scene definition is stored in a ConfigMap (`surg-rl-scene`) as `scene.json`.

<!-- VERIFY: llm-api-key and model-registry-token values in the K8s secret template are placeholders — actual secrets must be provisioned per cluster -->

### Secrets management

| Secret            | Where it is used    | How to set                                               |
|-------------------|---------------------|----------------------------------------------------------|
| `PYPI_API_TOKEN`  | GitHub Actions      | Repository Settings → Secrets and variables → Actions    |
| `LLM_API_KEY`     | Runtime environment | `.env` file or platform secret manager (Kubernetes Secrets, Docker secrets) |
| `GITHUB_TOKEN`    | GitHub Actions      | Auto-provided by Actions; used for GHCR login            |

---

## Rollback procedure

### Docker deployment

Redeploy with the previous stable image tag:

```bash
# Pull the last known-good tag
docker pull ghcr.io/surg-rl/surg-rl:v0.1.0

# Restart the container
docker stop surge-rl-instance
docker rm surge-rl-instance
docker run -d --name surge-rl-instance ghcr.io/surg-rl/surg-rl:v0.1.0
```

<!-- VERIFY: ghcr.io image availability depends on successful prior release workflow runs -->

### Kubernetes deployment

Redeploy the previous Kustomize configuration or use `kubectl rollout undo`:

```bash
# Roll back the training Job by re-applying a known-good Kustomize overlay
kubectl apply -k k8s/overlays/gpu

# Or use rollout undo for Deployments (not applicable to Jobs)
kubectl delete job surg-rl-training
kubectl apply -f - <<EOF
...
EOF
```

For Ray-based deployments, delete the existing RayJob/RayCluster and re-create:

```bash
kubectl delete rayjob surg-rl-rayjob
kubectl apply -k k8s/overlays/gpu
```

### PyPI rollback

If a published release is broken, revert by installing the previous version:

```bash
pip install surg-rl==0.1.0
```

To prevent further installs of the bad version, yank it on PyPI via the web UI or using `twine`.
<!-- VERIFY: yanking requires project owner credentials on PyPI -->

### Training checkpoint rollback

If a training run diverges, revert to the last checkpoint:

```bash
# SB3 models are zip archives containing periodic snapshots
cp models/ppo_model_backup.zip models/ppo_model.zip
surg-rl evaluate --model models/ppo_model.zip
```

In Kubernetes, checkpoints persist on the `surg-rl-checkpoints` PVC and survive Job deletion.

---

## Monitoring

### Experiment tracking

surg-rl supports two experiment tracking backends via the `[tracking]` optional dependency group:

| Tool            | Package    | Environment setup           |
|-----------------|------------|-----------------------------|
| Weights & Biases | `wandb`    | Set `WANDB_API_KEY`         |
| MLflow          | `mlflow`   | No additional config needed |

To enable during training, ensure the `[tracking]` extras are installed (included by default
in all Docker images).

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

This is not included in the default Dockerfiles to keep the images minimal — add it when
deploying to orchestrated environments (Kubernetes, Docker Swarm).

### Infrastructure monitoring

For full production observability, consider integrating:

- **GPU metrics**: `nvidia-smi` (CUDA), `rocm-smi` (ROCm), or `tegrastats` (Jetson) exposed
  via Prometheus exporters.
- **Container metrics**: cAdvisor or Docker's built-in `docker stats`.
- **Application monitoring**: <!-- VERIFY: Sentry DSN and other APM endpoints are not configured in this repository — set up externally if needed -->
- **Ray dashboard**: Available on port 8265 when using RayCluster/RayJob (exposed in K8s manifests).

<!-- VERIFY: all external monitoring dashboard URLs, alert webhook endpoints, and team-specific APM project keys are deployment-specific and not tracked in this repository -->
