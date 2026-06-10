"""K8S-01..05: Validate Kubernetes manifest structure."""

from __future__ import annotations

from pathlib import Path

import yaml

K8S_BASE = Path(__file__).resolve().parents[1] / "k8s" / "base"


def _load(name: str) -> dict:
    return yaml.safe_load((K8S_BASE / name).read_text())


class TestJobStructure:
    """K8S-01: Training Job structure checks."""

    def test_has_gpu_node_selector(self):
        job = _load("training-job.yaml")
        sel = job["spec"]["template"]["spec"]["nodeSelector"]
        assert "nvidia.com/gpu.present" in sel

    def test_has_resource_limits(self):
        job = _load("training-job.yaml")
        limits = job["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]
        assert "cpu" in limits
        assert "memory" in limits

    def test_gpu_resource_request(self):
        job = _load("training-job.yaml")
        requests = job["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]
        assert "nvidia.com/gpu" in requests

    def test_has_pvc_volume(self):
        job = _load("training-job.yaml")
        volumes = {v["name"]: v for v in job["spec"]["template"]["spec"]["volumes"]}
        assert "checkpoints" in volumes
        assert "persistentVolumeClaim" in volumes["checkpoints"]

    def test_has_bridge_sidecar(self):
        job = _load("training-job.yaml")
        containers = job["spec"]["template"]["spec"]["containers"]
        names = [c["name"] for c in containers]
        assert "bridge" in names

    def test_share_process_namespace(self):
        job = _load("training-job.yaml")
        assert job["spec"]["template"]["spec"].get("shareProcessNamespace") is True

    def test_trainer_has_sidecar_env(self):
        job = _load("training-job.yaml")
        for c in job["spec"]["template"]["spec"]["containers"]:
            if c["name"] == "trainer":
                env_vars = {e["name"]: e.get("value", "") for e in c.get("env", [])}
                assert "SURGRL_BRIDGE_SIDECAR" in env_vars
                assert env_vars["SURGRL_BRIDGE_SIDECAR"] == "true"

    def test_init_container_wait_for_bridge(self):
        job = _load("training-job.yaml")
        init = job["spec"]["template"]["spec"]["initContainers"][0]
        assert init["name"] == "wait-for-bridge"

    def test_trainer_cuda_image(self):
        job = _load("training-job.yaml")
        for c in job["spec"]["template"]["spec"]["containers"]:
            if c["name"] == "trainer":
                assert "cuda" in c["image"]
                assert "ghcr.io/surg-rl" in c["image"]

    def test_init_container_ros2_topic_probe(self):
        job = _load("training-job.yaml")
        init = job["spec"]["template"]["spec"]["initContainers"][0]
        cmd = " ".join(init["command"])
        assert "ros2 topic list" in cmd
        assert "grep" in cmd
        assert "nc" not in cmd


class TestRayManifests:
    """K8S-02: RayCluster and RayJob structure checks."""

    def test_raycluster_has_head_and_workers(self):
        rc = _load("raycluster.yaml")
        assert "headGroupSpec" in rc["spec"]
        assert len(rc["spec"]["workerGroupSpecs"]) >= 1

    def test_rayjob_shutdown_after_finishes(self):
        rj = _load("rayjob.yaml")
        assert rj["spec"]["shutdownAfterJobFinishes"] is True

    def test_raycluster_image_references(self):
        rc = _load("raycluster.yaml")
        for container in rc["spec"]["headGroupSpec"]["template"]["spec"]["containers"]:
            assert "ghcr.io/surg-rl" in container["image"]

    def test_raycluster_has_pvc(self):
        rc = _load("raycluster.yaml")
        wgs = rc["spec"]["workerGroupSpecs"]
        worker_volumes = wgs[0]["template"]["spec"].get("volumes", [])
        vol_names = [v["name"] for v in worker_volumes]
        assert "checkpoints" in vol_names


class TestInfrastructureManifests:
    """K8S-04, K8S-05: ConfigMap, Secret, PVC, RBAC."""

    def test_configmap_has_scene(self):
        cm = _load("configmap.yaml")
        assert "scene.json" in cm["data"]

    def test_secret_is_opaque(self):
        secret = _load("secret.yaml")
        assert secret["type"] == "Opaque"

    def test_pvc_read_write_once(self):
        pvc = _load("pvc.yaml")
        assert "ReadWriteOnce" in pvc["spec"]["accessModes"]

    def test_pvc_has_storage_request(self):
        pvc = _load("pvc.yaml")
        assert int(pvc["spec"]["resources"]["requests"]["storage"].replace("Gi", "")) > 0

    def test_rbac_has_service_account(self):
        docs = list(yaml.safe_load_all((K8S_BASE / "rbac.yaml").read_text()))
        kinds = [d["kind"] for d in docs]
        assert "ServiceAccount" in kinds
        assert "Role" in kinds
        assert "RoleBinding" in kinds

    def test_rbac_namespace_scoped(self):
        docs = list(yaml.safe_load_all((K8S_BASE / "rbac.yaml").read_text()))
        for doc in docs:
            if doc["kind"] == "Role":
                assert doc["metadata"]["name"] == "surg-rl"
                # verify no cluster-scoped resources
                for rule in doc["rules"]:
                    for resource in rule["resources"]:
                        assert resource in ("pods", "pods/log", "jobs")


class TestKustomizeOverlays:
    """K8S-02: Kustomize overlay structure checks."""

    def test_cpu_overlay_exists(self):
        p = K8S_BASE.parent / "overlays" / "cpu" / "kustomization.yaml"
        assert p.exists()
        overlay = yaml.safe_load(p.read_text())
        assert len(overlay.get("patches", [])) >= 5

    def test_cpu_overlay_replaces_image(self):
        p = K8S_BASE.parent / "overlays" / "cpu" / "kustomization.yaml"
        overlay = yaml.safe_load(p.read_text())
        image_patches = [patch for patch in overlay["patches"] if "image" in patch.get("patch", "")]
        assert len(image_patches) >= 1
        for patch in image_patches:
            assert "cuda" not in patch["patch"]

    def test_gpu_overlay_exists(self):
        p = K8S_BASE.parent / "overlays" / "gpu" / "kustomization.yaml"
        assert p.exists()
        overlay = yaml.safe_load(p.read_text())
        assert overlay["kind"] == "Kustomization"
