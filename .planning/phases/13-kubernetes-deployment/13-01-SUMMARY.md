# 13-01 Summary: Training Job Manifest

**Plan:** 13-01-PLAN.md
**Status:** Complete
**Commits:** 1

## Accomplishments

- Created `k8s/base/training-job.yaml`: batch/v1 Job for SB3 RL training
- GPU nodeSelector (`nvidia.com/gpu.present: "true"`) + tolerations
- Resource requests/limits: 4 CPU, 8Gi memory, 1 GPU per container
- Scene ConfigMap volume mount at `/etc/surg-rl`
- Checkpoints PVC volume mount at `/app/checkpoints`
- `restartPolicy: Never`, `backoffLimit: 3`, TTL 86400s
- References `ghcr.io/surg-rl/surg-rl:v0.3.0` multi-arch image

## Self-Check: PASSED

- YAML structure valid, all required fields present
- GPU scheduling configured correctly
- Volume mounts reference existing ConfigMap/PVC names
