# Phase 13: Kubernetes Deployment — Research

**Researched:** 2026-05-04
**Domain:** Kubernetes manifests for RL training (Jobs, KubeRay, sidecars, ConfigMap/Secrets, PVC)
**Confidence:** HIGH

## Summary

Phase 13 delivers K8s manifests that deploy surg-rl RL training as production workloads. The stack is vanilla Kubernetes API resources (`batch/v1` Job, `v1` ConfigMap/Secret/PVC) plus KubeRay CRDs (`RayCluster`, `RayJob`) for RLlib distributed training. Kustomize overlays provide environment-specific configuration (CPU vs. GPU, dev vs. prod) without Helm.

The current codebase has a critical blocking gap: `train_rllib()` in `src/surg_rl/rl/rllib/train.py` calls `ray.init()` hardcoded (line 59-69) without reading the `RAY_ADDRESS` environment variable that KubeRay injects into worker pods. Without this fix, RLlib training inside a RayCluster will initialize a new local cluster instead of joining the existing one. This is a Phase 13 code change, not a manifest-only task.

The ROS2 bridge currently runs as `multiprocessing.Process` inside the training process. In K8s, this becomes a native sidecar container sharing the pod's network namespace. The bridge publishes to ROS2 topics on `localhost` within the pod — DDS multicast across pods is explicitly out of scope (REQUIREMENTS.md Out of Scope).

Docker images are already built (Phase 11) and pushed to GHCR: `ghcr.io/surg-rl/surg-rl:v0.3.0` (CPU, multi-arch) and `ghcr.io/surg-rl/surg-rl/cuda:v0.3.0` (CUDA, amd64). Manifests reference these images plus a ROS2-enabled bridge image (needs Dockerfile extension or separate image).

**Primary recommendation:** Use KubeRay `RayJob` for RLlib training (auto-creates cluster, submits job, cleans up on completion). Use native K8s `Job` for SB3 training (single-pod, no Ray dependency). Mount scene JSON from ConfigMap at `/etc/surg-rl/scene.json`, inject secrets as env vars from Secret. Checkpoints and TensorBoard logs share a `ReadWriteOnce` PVC at `/app/checkpoints`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| RL training (SB3) | K8s Pod (Job) | — | Single-container batch workload; Job manages completion/retry |
| RL training (RLlib) | KubeRay RayCluster | K8s Pod | Ray owns cluster lifecycle; K8s provides node placement |
| GPU scheduling | K8s Node | Device Plugin | `nvidia.com/gpu` resource + nodeSelector/tolerations |
| ROS2 bridge pub/sub | Sidecar Container | Pod network namespace | Shares localhost with training container; no cross-pod DDS |
| Scene JSON injection | ConfigMap → File mount | — | Immutable at runtime; mounted read-only |
| API keys / tokens | Secret → Env vars | — | Never in pod spec; referenced via `secretKeyRef` |
| Checkpoint persistence | PVC (ReadWriteOnce) | — | Survives pod/job deletion; reused by subsequent Jobs |
| Ray cluster discovery | Env var `RAY_ADDRESS` | KubeRay head Service | Auto-injected by KubeRay; consumed by `ray.init(address=env)` |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Kubernetes API | `batch/v1`, `v1` | Job, ConfigMap, Secret, PVC, Service | Built-in; no additional operator needed for SB3 training |
| KubeRay CRDs | v1.6.0 | RayCluster, RayJob | Official Ray-on-K8s operator; managed by Ray project |
| Kustomize | built-in (`kubectl apply -k`) | Overlay management | Project constraint: Helm explicitly out of scope |
| NVIDIA Device Plugin | latest | GPU exposure to pods | Required for `nvidia.com/gpu` resource on GPU nodes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `kind` | v0.20+ | Local K8s cluster for CI testing | Integration tests in plan 13-05 |
| `kubectl` | ≥1.28 | Manifest application | All interaction with the cluster |
| `ghcr.io` | — | Container registry | Images already pushed by Phase 11 release workflow |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| KubeRay RayJob | Helm Ray chart | Helm out of scope per project decision |
| Kustomize overlays | Helm | Kustomize is kubectl-native; no Tiller/Helm install needed |
| Sidecar container (K8s native) | `multiprocessing.Process` (current) | Sidecar is K8s-idiomatic; Process model doesn't survive pod restarts cleanly |

**Version verification:**
KubeRay stable release as of 2026-05: v1.6.0
[VERIFIED: docs.ray.io/en/latest/cluster/kubernetes/getting-started/kuberay-operator-installation.html]

**Installation:**
```bash
# KubeRay operator (once per cluster)
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm install kuberay-operator kuberay/kuberay-operator --version 1.6.0

# Apply surg-rl manifests
kubectl apply -k k8s/overlays/production/
```

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────────────────┐
                    │              K8s Cluster                 │
                    │                                          │
  ┌─────────────────┤  Namespace: surg-rl                     │
  │                 │                                          │
  │   ┌──────────────────────────────────────────────────┐    │
  │   │  Job: surg-rl-train (SB3)                        │    │
  │   │  ┌──────────────────┐  ┌──────────────────────┐  │    │
  │   │  │ trainer container│  │ ros2-bridge sidecar  │  │    │
  │   │  │  surg-rl:cuda    │  │  (shared net ns)     │  │    │
  │   │  │                  │  │                      │  │    │
  │   │  │  /app/scene.json │  │  pub: JointState     │  │    │
  │   │  │  ← ConfigMap     │  │  sub: Float64Multi.. │  │    │
  │   │  │  /app/checkpoints│  │  → localhost topics  │  │    │
  │   │  │  ← PVC           │  │                      │  │    │
  │   │  └──────────────────┘  └──────────────────────┘  │    │
  │   └──────────────────────────────────────────────────┘    │
  │                 │                                          │
  │   ┌─────────────▼────────────────────────────────────┐    │
  │   │  RayJob: surg-rl-ray-train (RLlib)               │    │
  │   │  ┌───────────────────────────────────────────┐   │    │
  │   │  │  RayCluster (auto-created by RayJob)      │   │    │
  │   │  │  ┌──────────┐  ┌──────────┐  ┌─────────┐ │   │    │
  │   │  │  │Head Pod  │  │Worker 1  │  │Worker N │ │   │    │
  │   │  │  │          │  │          │  │         │ │   │    │
  │   │  │  │RAY_ADDR..│  │RAY_ADDR..│  │RAY_ADDR.│ │   │    │
  │   │  │  │=auto:6379│  │=auto:6379│  │=auto:...│ │   │    │
  │   │  │  └──────────┘  └──────────┘  └─────────┘ │   │    │
  │   │  └───────────────────────────────────────────┘   │    │
  │   └──────────────────────────────────────────────────┘    │
  │                 │                                          │
  │   ┌─────────────▼──────────────┐                           │
  │   │  Storage                   │                           │
  │   │  ┌──────────────────────┐  │                           │
  │   │  │ PVC: checkpoints     │  │                           │
  │   │  │  /app/checkpoints/   │  │                           │
  │   │  │  /app/tensorboard/   │  │                           │
  │   │  └──────────────────────┘  │                           │
  │   └────────────────────────────┘                           │
  └────────────────────────────────────────────────────────────┘

  External dependencies:
  ┌──────────────┐     ┌─────────────┐
  │ GHCR         │     │ ConfigMap   │
  │ surg-rl:cuda │     │ scene.json  │
  │ surg-rl:ray  │     │ (from file) │
  └──────────────┘     └─────────────┘
```

### Recommended Project Structure
```
k8s/
├── base/
│   ├── kustomization.yaml       # Common labels, namespace
│   ├── training-job.yaml        # K8s Job for SB3 training
│   ├── ray-cluster.yaml         # KubeRay RayCluster (standalone)
│   ├── ray-job.yaml             # KubeRay RayJob (cluster + submit)
│   ├── configmap.yaml           # Scene JSON injection
│   ├── secret.yaml              # API keys, model registry tokens
│   ├── pvc.yaml                 # Checkpoint/TensorBoard volume
│   └── rbac.yaml                # ServiceAccount + RBAC for Job pods
├── overlays/
│   ├── cpu/
│   │   └── kustomization.yaml   # CPU image, no GPU selectors
│   ├── gpu/
│   │   └── kustomization.yaml   # CUDA image, GPU nodeSelector, nvidia.com/gpu
│   └── production/
│       └── kustomization.yaml   # Combines gpu + GHCR image tags + secrets
└── scripts/
    └── create-configmap.sh      # Helper: kubectl create configmap from scene file
```

### Pattern 1: K8s Job for SB3 Training

**What:** A `batch/v1` Job runs `surg-rl train` to completion. Uses `restartPolicy: OnFailure` with `backoffLimit: 3`. Sidecar container for ROS2 bridge shares process or network namespace.

**When to use:** Single-node SB3 training (PPO, SAC, TD3) — no Ray dependency.

**Example:**
```yaml
# Source: kubernetes.io/docs/concepts/workloads/controllers/job/
apiVersion: batch/v1
kind: Job
metadata:
  name: surg-rl-train
spec:
  backoffLimit: 3
  template:
    spec:
      restartPolicy: OnFailure
      nodeSelector:
        accelerator: nvidia-tesla-v100
      containers:
      - name: trainer
        image: ghcr.io/surg-rl/surg-rl/cuda:v0.3.0
        command: ["python", "-m", "surg_rl.cli", "train"]
        args:
          - "--scene"
          - "/etc/surg-rl/scene.json"
          - "--algorithm"
          - "PPO"
          - "--timesteps"
          - "1000000"
          - "--log-dir"
          - "/app/checkpoints"
        env:
        - name: WANDB_API_KEY
          valueFrom:
            secretKeyRef:
              name: surg-rl-secrets
              key: wandb_api_key
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "16Gi"
            cpu: "4"
          limits:
            nvidia.com/gpu: 1
            memory: "32Gi"
            cpu: "8"
        volumeMounts:
        - name: scene-config
          mountPath: /etc/surg-rl
          readOnly: true
        - name: checkpoints
          mountPath: /app/checkpoints
      - name: ros2-bridge
        image: ghcr.io/surg-rl/surg-rl/ros2:v0.3.0
        command: ["python", "-m", "surg_rl.cli", "ros2-bridge"]
        args:
          - "--state-topic"
          - "/surg_rl/joint_states"
          - "--command-topic"
          - "/surg_rl/commands"
        env:
        - name: ROS_DOMAIN_ID
          value: "42"
      volumes:
      - name: scene-config
        configMap:
          name: surg-rl-scene
      - name: checkpoints
        persistentVolumeClaim:
          claimName: surg-rl-checkpoints
```

### Pattern 2: KubeRay RayJob for RLlib Training

**What:** A `RayJob` CR creates a RayCluster and submits the training script via `ray job submit`. The training code calls `ray.init(address="auto")` (reading `RAY_ADDRESS` env var) to join the existing cluster.

**When to use:** RLlib distributed training across multiple worker pods.

**Key mechanism:** KubeRay sets `RAY_ADDRESS` env var on all worker pods pointing to the head service. The training code must NOT call `ray.init()` without arguments — it must use `ray.init(address=os.environ.get("RAY_ADDRESS", "auto"))` or equivalent.

**Example:**
```yaml
# Source: docs.ray.io/en/latest/cluster/kubernetes/getting-started/rayjob-quick-start.html
apiVersion: ray.io/v1
kind: RayJob
metadata:
  name: surg-rl-ray-train
spec:
  entrypoint: >
    python -m surg_rl.cli ray-train
    --scene /etc/surg-rl/scene.json
    --algorithm PPO
    --timesteps 1000000
    --checkpoint-dir /app/checkpoints
  shutdownAfterJobFinishes: true
  ttlSecondsAfterFinished: 300
  rayClusterSpec:
    rayVersion: "2.10.0"
    headGroupSpec:
      rayStartParams:
        dashboard-host: "0.0.0.0"
      template:
        spec:
          containers:
          - name: ray-head
            image: ghcr.io/surg-rl/surg-rl/ray:v0.3.0
            ports:
            - containerPort: 6379   # GCS
            - containerPort: 8265   # Dashboard
            - containerPort: 10001  # Ray client
            resources:
              requests:
                cpu: "2"
                memory: "8Gi"
              limits:
                cpu: "4"
                memory: "16Gi"
            volumeMounts:
            - name: scene-config
              mountPath: /etc/surg-rl
              readOnly: true
            - name: checkpoints
              mountPath: /app/checkpoints
    workerGroupSpecs:
    - groupName: gpu-workers
      replicas: 2
      minReplicas: 1
      maxReplicas: 4
      rayStartParams: {}
      template:
        spec:
          nodeSelector:
            accelerator: nvidia-tesla-v100
          containers:
          - name: ray-worker
            image: ghcr.io/surg-rl/surg-rl/cuda:v0.3.0
            resources:
              requests:
                nvidia.com/gpu: 1
                cpu: "4"
                memory: "16Gi"
              limits:
                nvidia.com/gpu: 1
                cpu: "8"
                memory: "32Gi"
            volumeMounts:
            - name: scene-config
              mountPath: /etc/surg-rl
              readOnly: true
            - name: checkpoints
              mountPath: /app/checkpoints
      volumes:
      - name: scene-config
        configMap:
          name: surg-rl-scene
      - name: checkpoints
        persistentVolumeClaim:
          claimName: surg-rl-checkpoints
```

### Pattern 3: Native Sidecar Container (ROS2 Bridge)

**What:** Since K8s 1.28, init containers with `restartPolicy: Always` are native sidecar containers. They start before the main container and run for the pod's lifetime. This replaces the current `multiprocessing.Process` approach.

**When to use:** Any pod needing a companion process that shares lifecycle with the main container.

**Example:**
```yaml
# Source: kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/
spec:
  initContainers:
  - name: ros2-bridge
    image: ghcr.io/surg-rl/surg-rl/ros2:v0.3.0
    restartPolicy: Always           # ← Makes it a sidecar, not init
    command:
      - python
      - -m
      - surg_rl.cli
      - ros2-bridge
      - --state-topic
      - /surg_rl/joint_states
      - --command-topic
      - /surg_rl/commands
    env:
    - name: ROS_DOMAIN_ID
      value: "42"
  containers:
  - name: trainer
    # ... main container
```

> **Important:** The current ROS2 bridge in `src/surg_rl/rl/environment.py` spawns inside `SurgicalEnv.__init__()` via `_setup_bridge()`. For K8s sidecar mode, the training container should NOT self-spawn the bridge — it should detect the bridge is running as a sidecar and skip spawn. This requires code change in the environment lifecycle. See "Code Changes Required" below.

### Pattern 4: ConfigMap + Secret Injection

**What:** ConfigMap holds non-sensitive configuration (scene JSON). Secret holds credentials (API keys, tokens). ConfigMap mounts as files; Secrets expose as environment variables.

**When to use:** All K8s deployments. Never hardcode configuration in pod specs.

**Example:**
```yaml
# ConfigMap: scene JSON
apiVersion: v1
kind: ConfigMap
metadata:
  name: surg-rl-scene
data:
  scene.json: |
    {
      "name": "laparoscopic_dissection",
      "robots": [...]
    }

---
# Secret: API keys (NEVER commit plaintext; use SOPS/sealed-secrets in production)
apiVersion: v1
kind: Secret
metadata:
  name: surg-rl-secrets
type: Opaque
stringData:
  wandb_api_key: "PLACEHOLDER"
  mlflow_tracking_uri: "http://mlflow-server:5000"
  model_registry_token: "PLACEHOLDER"
```

### Pattern 5: PVC for Checkpoint + TensorBoard Persistence

**What:** A `ReadWriteOnce` PVC shared by training Jobs. Survives pod deletion. Subsequent Jobs mount the same PVC and resume from latest checkpoint.

**When to use:** Long-running training that must survive interruptions.

**Example:**
```yaml
# Source: kubernetes.io/docs/concepts/storage/persistent-volumes/
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: surg-rl-checkpoints
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: standard  # cloud-provider specific; use local-path for kind
```

### Anti-Patterns to Avoid

- **Hardcoding `ray.init()` without `RAY_ADDRESS`:** The current code does this. Ray will create a NEW local cluster instead of joining the existing KubeRay cluster. Must be fixed before manifests work.
- **Committing plaintext secrets to git:** Secrets should be placeholders in base manifests; actual values injected via Kustomize `secretGenerator` or external secret management.
- **Using `LoadBalancer` Service for internal Ray communication:** Ray head uses `ClusterIP` (via KubeRay's head Service); only Dashboard needs external access (via `kubectl port-forward`).
- **Mounting PVC as `ReadWriteMany` for single-pod workloads:** Unnecessary complexity. `ReadWriteOnce` is correct for Job pods (one pod at a time).
- **Sidecar as regular container (before K8s 1.28):** Without `restartPolicy: Always` on init containers, the sidecar lifecycle doesn't properly tie to the pod. Target K8s ≥1.28 for native sidecar support.

## Code Changes Required (Not Just Manifests)

These are codebase modifications the phase must make to enable the K8s manifests:

1. **`src/surg_rl/rl/rllib/train.py` line 59-63:** Replace hardcoded `ray.init()` with:
   ```python
   ray.init(address=os.environ.get("RAY_ADDRESS", "auto"), ...)
   ```
   This is the single breaking gap — without it, RLlib training inside a KubeRay cluster will silently run locally.

2. **`src/surg_rl/rl/environment.py` `_setup_bridge()` (line 371-426):** Add logic to detect when ROS2 bridge is running as a sidecar (e.g., check for env var `SURGRL_BRIDGE_SIDECAR=true` or probe `localhost` ROS2 topics). If sidecar detected, skip `multiprocessing.Process` spawn. The environment should still forward joint states — but via ROS2 publish to localhost rather than in-process queue.

3. **`src/surg_rl/cli.py`:** Verify `ros2-bridge` command works as standalone entrypoint (it currently relies on `SurgicalEnv` lifecycle). For sidecar mode, the bridge needs to run independently as a long-lived service.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ray cluster lifecycle | Custom Job that starts Ray manually | KubeRay `RayJob` CRD | Handles head election, worker scaling, address injection, cleanup |
| GPU detection in K8s | Custom node discovery | `nvidia.com/gpu` + NVIDIA Device Plugin | Standard K8s resource; scheduler natively understands it |
| Secret management | Custom vault integration | K8s `Secret` + Kustomize `secretGenerator` | Native; works with external-secrets-operator if needed later |
| Config injection | Custom sidecar for config serving | K8s `ConfigMap` volume mount | Automatic hot-reload on ConfigMap update; zero code |
| Checkpoint resume logic | Custom checkpoint scanning | Mount same PVC; surg-rl resumes from latest | Application already handles `--checkpoint-dir` |
| ROS2 DDS cross-pod | Custom DDS router/relay | Document localhost-only limitation; out of scope | Platform-level issue with multicast in CNI; not solving in v0.3.0 |

**Key insight:** KubeRay and the NVIDIA device plugin handle the two hardest distributed-compute problems (Ray cluster formation and GPU device assignment). The phase should lean on these operators, not rebuild them.

## Runtime State Inventory

> Phase 13 adds new files only (no rename/refactor/migration). This section is not applicable — skipped per research protocol.

## Common Pitfalls

### Pitfall 1: `ray.init()` Creates Local Cluster Instead of Joining Existing

**What goes wrong:** Training pod calls `ray.init()` without `address` kwarg. Ray creates a new single-node cluster inside the pod. The KubeRay RayCluster sits unused. Training runs but without parallel workers — no speedup and wasted GPU resources.

**Why it happens:** The current `train_rllib()` code hardcodes `ray.init(local_mode=..., ignore_reinit_error=True)` without reading `RAY_ADDRESS`. KubeRay sets `RAY_ADDRESS` on all pods, but our code ignores it.

**How to avoid:** Fix `train_rllib()` to use `ray.init(address=os.environ.get("RAY_ADDRESS", "auto"))`. Add an integration test that mocks `RAY_ADDRESS` and asserts `ray.init` is called with the correct address.

**Warning signs:** Log shows "Ray initialised — CPUs=X GPUs=Y" with resources matching the pod's own allocation (not the full cluster). No worker pods appear in `ray.cluster_resources()`.

### Pitfall 2: Sidecar Container Doesn't Replace In-Process Bridge

**What goes wrong:** K8s manifest has a sidecar container running `ros2-bridge`, but the trainer container also spawns its own bridge via `multiprocessing.Process`. Two bridges conflict (duplicate publishers, port conflicts).

**Why it happens:** `SurgicalEnv.__init__()` unconditionally spawns a bridge if `ros2_bridge_config` is set. The sidecar is unaware of the in-process bridge.

**How to avoid:** Add env var `SURGRL_BRIDGE_SIDECAR=true` to the trainer container. Modify `_setup_bridge()` to check this env var and skip spawn if set. The environment should still call `publish_joint_state()` — but route to the sidecar's ROS2 topics on `localhost`.

**Warning signs:** Duplicate JointState messages on the topic. ROS2 warnings about multiple publishers.

### Pitfall 3: PVC Access Mode Mismatch

**What goes wrong:** PVC is created as `ReadWriteOnce` but two pods from the same Job try to mount it simultaneously (e.g., during Job retry or parallel workers). One pod gets stuck in `ContainerCreating` with `Multi-Attach error`.

**Why it happens:** `ReadWriteOnce` allows exactly one pod to mount the volume. During Job retries, the old pod may still be terminating while the new one tries to mount.

**How to avoid:** Set `spec.backoffLimit` to a reasonable value (3 is standard). Ensure `restartPolicy: OnFailure` not `Always`. Consider using `ReadWriteOncePod` (K8s 1.29+) if available, which restricts to a single pod even within the same node. For RLlib distributed training, only the head pod should mount the checkpoint PVC — workers don't need it.

**Warning signs:** Pod stuck in `Pending`/`ContainerCreating` with event: `Multi-Attach error for volume "checkpoints"`.

### Pitfall 4: Ray Worker Crashes Leave Orphaned Resources

**What goes wrong:** A Ray worker pod crashes (OOMKilled, GPU driver issue). The RayJob's `backoffLimit` controls retries, but the default is 0 — no retries, Job marked failed immediately.

**Why it happens:** Default `backoffLimit` on RayJob is 0. A single pod failure kills the entire training run.

**How to avoid:** Set `spec.backoffLimit: 2` on the RayJob. The RayCluster handles worker pod recovery internally; `backoffLimit` covers cases where the entire cluster is unhealthy. Use `activeDeadlineSeconds` to prevent infinite retry loops.

**Warning signs:** RayJob status `FAILED` with reason `DeadlineExceeded`. Head pod logs show worker disconnection.

### Pitfall 5: Image Pull Failure from GHCR Without Credentials

**What goes wrong:** K8s cluster can't pull from `ghcr.io/surg-rl/surg-rl` because GHCR requires authentication for private packages. Pod stays in `ImagePullBackOff`.

**Why it happens:** GHCR packages are private by default. K8s needs an `imagePullSecret` referencing a GitHub token.

**How to avoid:** Create a `docker-registry` Secret and reference it in `spec.template.spec.imagePullSecrets`. Document in README. For public repos, GHCR can be configured to allow anonymous pulls — verify this setting.

**Warning signs:** `kubectl describe pod` shows `Failed to pull image ... unauthorized: authentication required`.

## Code Examples

### RAY_ADDRESS-Aware ray.init()

```python
# Source: docs.ray.io/en/latest/cluster/kubernetes/getting-started/raycluster-quick-start.html
# Method 1: exec into head pod — RAY_ADDRESS is set automatically
import os
import ray

def train_rllib(config, *, local_mode=False, log_dir=None, checkpoint_dir=None):
    ray_address = os.environ.get("RAY_ADDRESS")
    if ray_address:
        # Running inside KubeRay cluster — join existing cluster
        ray.init(address=ray_address, ignore_reinit_error=True)
    elif not ray.is_initialized():
        # Running standalone — create local cluster
        ray.init(local_mode=local_mode, ignore_reinit_error=True)
    # ... rest of training loop
```

### ConfigMap from Scene File

```bash
# Source: kubernetes.io/docs/concepts/configuration/configmap/
# Create ConfigMap from an existing scene JSON file
kubectl create configmap surg-rl-scene \
  --from-file=scene.json=scenes/laparoscopic_dissection.yaml \
  --namespace surg-rl \
  --dry-run=client -o yaml > k8s/base/configmap.yaml
```

### Kustomize Overlay for GPU

```yaml
# k8s/overlays/gpu/kustomization.yaml
# Source: kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

images:
  - name: ghcr.io/surg-rl/surg-rl
    newTag: cuda-v0.3.0

patches:
  - target:
      kind: Job
      name: surg-rl-train
    patch: |
      - op: add
        path: /spec/template/spec/nodeSelector
        value:
          accelerator: nvidia-tesla-v100
      - op: add
        path: /spec/template/spec/containers/0/resources/limits/nvidia.com~1gpu
        value: "1"
```

### RBAC for Job Pods

```yaml
# Source: kubernetes.io/docs/reference/access-authn-authz/rbac/
apiVersion: v1
kind: ServiceAccount
metadata:
  name: surg-rl-trainer
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: surg-rl-trainer
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: surg-rl-trainer
subjects:
  - kind: ServiceAccount
    name: surg-rl-trainer
roleRef:
  kind: Role
  name: surg-rl-trainer
  apiGroup: rbac.authorization.k8s.io
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom Ray launcher scripts | KubeRay CRDs (RayCluster, RayJob) | Ray 2.0+ / KubeRay 0.6+ | Lifecycle managed by operator; no custom scripts |
| `multiprocessing.Process` for bridge | K8s native sidecar containers | K8s 1.28 (2023) | Cleaner lifecycle; survives pod restarts; matches K8s idioms |
| `restartPolicy: Always` on main container | `restartPolicy: OnFailure` for Jobs | Always standard | OnFailure is correct for batch workloads |
| Helm charts for K8s deployment | Kustomize overlays | Project decision (v0.3.0) | kubectl-native; no Helm dependency; simpler for 5 manifests |

**Deprecated/outdated:**
- **`PodSecurityPolicy`:** Removed in K8s 1.25. Use `Pod Security Admission` (namespace labels) instead.
- **`extensions/v1beta1` API:** Removed. Use `apps/v1` for Deployments, `batch/v1` for Jobs.
- **Helm operator:** Explicitly out of scope for this milestone.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | K8s cluster will have KubeRay operator v1.6.0 pre-installed | Standard Stack | Manifests reference RayCluster/RayJob CRDs; without operator, `kubectl apply` will fail with unknown resource type |
| A2 | GPU nodes have `nvidia.com/gpu` resource exposed via NVIDIA Device Plugin | GPU Scheduling | Pods will stay in Pending state waiting for GPU resources that don't exist |
| A3 | GHCR images are private and require `imagePullSecret` | Common Pitfalls | If GHCR repos are public, extra Secret setup is unnecessary (but harmless) |
| A4 | K8s version ≥1.28 for native sidecar container support | Sidecar Pattern | Fall back to regular container pattern if cluster runs older K8s; sidecar lifecycle won't be as tightly coupled |
| A5 | ROS2 bridge as sidecar communicates on localhost only | DDS Networking | If ROS2 needs to communicate across pods, this approach won't work — but cross-pod DDS is explicitly out of scope |
| A6 | Single training pod per PVC (ReadWriteOnce) | PVC Pattern | If RLlib needs multiple pods writing checkpoints, ReadWriteMany or a shared filesystem (NFS) is needed |

## Open Questions

1. **ROS2-enabled Docker image:**
   - What we know: Current Docker images install `[dev,tracking]` extras only. No ROS2 dependency (rclpy, sensor_msgs) in images.
   - What's unclear: Whether to build a separate `Dockerfile.ros2` or add ROS2 to the CPU image with an optional layer.
   - Recommendation: Add `Dockerfile.ros2` extending the CPU image with `ros:humble-ros-base` + `[ros2]` extras. This is a Phase 13 deliverable (bridges the gap from Phase 11 images).

2. **Bridge sidecar detection mechanism:**
   - What we know: `SurgicalEnv._setup_bridge()` currently spawns a bridge if `ros2_bridge_config` is set. In sidecar mode, the bridge already runs — the env shouldn't double-spawn.
   - What's unclear: Best detection mechanism — env var vs. topic probe vs. explicit config field.
   - Recommendation: Add `SURGRL_BRIDGE_SIDECAR` env var. Trainer container sets `value: "true"` in pod spec. `_setup_bridge()` checks `os.environ.get("SURGRL_BRIDGE_SIDECAR")` and skips spawn if true. Falls into the `Ros2BridgeConfig` config model or as a top-level env.

3. **RayCluster vs. RayJob for interactive development:**
   - What we know: RayJob auto-deletes cluster after job completion. For development workflows where you want `kubectl exec` into the cluster, a persistent RayCluster is better.
   - What's unclear: Whether to ship both patterns (RayCluster standalone + RayJob wrapper) or just RayJob.
   - Recommendation: Ship both. RayJob for production (CI/CD, scheduled runs). RayCluster for manual debugging. Document the tradeoff in README.

4. **Kind integration test scope:**
   - What we know: CI needs to validate manifests are syntactically correct and schedulable. Full GPU integration testing requires real hardware.
   - What's unclear: Whether to run `kubectl apply --dry-run=client` in CI or spin up a real kind cluster.
   - Recommendation: `dry-run=client` for syntax validation in primary CI. Kind cluster with KubeRay + `kubectl apply` for plan 13-05 integration tests (CPU-only, no GPU assertion). GPU validation is manual-only for v0.3.0.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `kubectl` | All manifest application | ✓ | — (varies) | — |
| KubeRay operator | K8S-02 (RayCluster/RayJob) | ✗ | — | Must be installed on target cluster; documented in README |
| NVIDIA Device Plugin | K8S-01 (GPU scheduling) | ✗ | — | Must be installed on GPU nodes; skip for CPU overlays |
| `kind` | CI integration tests | ✗ | — | Install in CI via `setup-kind` GitHub Action |
| GHCR access | Image pulls | ✓ (Phase 11) | — | `imagePullSecret` for private repos if needed |

**Missing dependencies with no fallback:**
- **KubeRay operator:** Blocks all RLlib manifests. Cannot be bypassed — RayCluster/RayJob CRDs are required.
- **NVIDIA Device Plugin:** Blocks GPU manifests. CPU overlays work without it.

**Missing dependencies with fallback:**
- **`kind`:** Only needed for CI; local development can use any K8s cluster.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) + `kubectl --dry-run=client` + kind cluster shell tests |
| Config file | pytest.ini (existing) |
| Quick run command | `kubectl apply -k k8s/overlays/cpu/ --dry-run=client` |
| Full suite command | `PYTHONPATH=src pytest tests/test_kubernetes_manifests.py -v` (Wave 0) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| K8S-01 | Job manifest with GPU node selectors and resource limits | unit | `kubectl apply -f k8s/base/training-job.yaml --dry-run=client` | ❌ Wave 0 |
| K8S-02 | RLlib training with ray.init(address="auto") | integration | `PYTHONPATH=src python -c "import os; os.environ['RAY_ADDRESS']='test'; ..."` (code test) | ❌ Wave 0 |
| K8S-03 | ROS2 bridge sidecar in training pod | unit | `kubectl apply -f k8s/base/training-job.yaml --dry-run=client && yq eval '.spec.template.spec.initContainers[0].name'` | ❌ Wave 0 |
| K8S-04 | ConfigMap injects scene JSON; Secrets as env vars | unit | `kubectl apply -f k8s/base/configmap.yaml --dry-run=client && kubectl apply -f k8s/base/secret.yaml --dry-run=client` | ❌ Wave 0 |
| K8S-05 | PVC survives pod restarts; checkpoints + TensorBoard persist | manual-only | Manual: delete pod, verify PVC exists, re-apply Job, check log for "resuming from checkpoint" | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `kubectl apply -k k8s/overlays/cpu/ --dry-run=client` (manifest validity)
- **Per wave merge:** `PYTHONPATH=src pytest tests/test_kubernetes_manifests.py tests/test_ray_address.py -v`
- **Phase gate:** All manifests `--dry-run=client` pass + RLlib code test passes + kind integration test (CPU overlay only)

### Wave 0 Gaps
- [ ] `tests/test_kubernetes_manifests.py` — validates all 5 manifests via `kubectl --dry-run=client`; checks required fields populated
- [ ] `tests/test_ray_address.py` — validates `train_rllib()` reads `RAY_ADDRESS` env var; mocks `ray.init()` and asserts `address` kwarg
- [ ] `tests/conftest.py` — existing; may need `kubectl` availability fixture
- [ ] kind setup in CI — plan 13-05 handles this

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | `imagePullSecret` for GHCR; `ServiceAccount` with minimal RBAC |
| V3 Session Management | No | Not applicable to batch workloads |
| V4 Access Control | Yes | RBAC: Role/ServiceAccount scoped to `surg-rl` namespace; List/Get pods only |
| V5 Input Validation | Yes | K8s API validates manifest structure; `kubectl --dry-run=client` catches schema errors |
| V6 Cryptography | Yes | Secrets at rest encrypted via K8s Secret (base64); production should use `SealedSecrets` or SOPS |
| V7 Error Handling | No | Not applicable to manifests |
| V8 Data Protection | Yes | Sensitive data (API keys, tokens) in Secrets never in pod spec or ConfigMap |

### Known Threat Patterns for K8s Manifests

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secrets exposed in pod spec (hardcoded `env.value`) | Information Disclosure | Use `secretKeyRef` referencing K8s Secret objects |
| Overly permissive RBAC (cluster-admin for training pods) | Elevation of Privilege | Namespace-scoped Role with minimal verbs (get, list pods only) |
| Committed plaintext secrets in git | Information Disclosure | Placeholder values in base; Kustomize `secretGenerator` or SOPS in overlays |
| Missing `securityContext` (root user in container) | Elevation of Privilege | Add `runAsNonRoot: true`, `runAsUser: 1000`, `allowPrivilegeEscalation: false` |
| Unbounded resource consumption (no limits) | Denial of Service | `resources.limits` on all containers for CPU, memory, GPU |

## Sources

### Primary (HIGH confidence)
- KubeRay docs (`ray-project/kuberay`): RayJob CRD, RayCluster CRD, operator installation — [VERIFIED: docs.ray.io/en/latest/cluster/kubernetes/getting-started/]
- Kubernetes docs: Job controller, sidecar containers, ConfigMap, Secrets, GPU scheduling — [VERIFIED: kubernetes.io/docs/]
- NVIDIA Device Plugin: GPU resource exposure — [VERIFIED: kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/]
- Project codebase: `train_rllib()`, `SurgicalEnv._setup_bridge()`, `Dockerfile`, CI workflows — [VERIFIED: codebase grep/read]

### Secondary (MEDIUM confidence)
- KubeRay GitHub samples: `ray-job.sample.yaml`, `ray-job.shutdown.yaml` — [CITED: github.com/ray-project/kuberay]

### Tertiary (LOW confidence)
- None — all claims verified against primary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — KubeRay v1.6.0 confirmed via official docs; Kustomize is project decision
- Architecture: HIGH — K8s Job, sidecar, ConfigMap/Secret patterns verified against official docs
- Pitfalls: HIGH — All pitfalls verified with official docs or codebase analysis
- Code changes: HIGH — `ray.init()` gap confirmed by reading `train.py` directly; bridge double-spawn confirmed in `environment.py`

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (30 days — K8s API is stable; KubeRay may have minor version bumps)
