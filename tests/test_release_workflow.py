"""GAP-01: Verify release workflow includes ROS2 bridge image build."""

from pathlib import Path

import yaml

_WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"


class TestReleaseWorkflow:
    def test_release_has_ros2_build(self):
        workflow = yaml.safe_load(_WORKFLOW_PATH.read_text())
        steps = workflow["jobs"]["docker-release"]["steps"]
        step_names = [s.get("name", s.get("uses", "")) for s in steps]
        has_meta = any("ROS2" in str(n) for n in step_names)
        has_push = any("push" in str(n).lower() and "ROS2" in str(n) for n in step_names)
        assert has_meta, "Missing Docker meta (ROS2) step"
        assert has_push, "Missing Build and push ROS2 step"

    def test_release_ros2_uses_dockerfile_ros2(self):
        workflow = yaml.safe_load(_WORKFLOW_PATH.read_text())
        steps = workflow["jobs"]["docker-release"]["steps"]
        for step in steps:
            if "ROS2" in str(step.get("name", "")) and "push" in str(step.get("name", "")).lower():
                assert step.get("with", {}).get("file") == "./Dockerfile.ros2"
                return
        raise AssertionError("ROS2 build step not found")
