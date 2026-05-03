"""Tests for the ROS2 bridge core — config, import guard, and bridge node.

Tests use mocked rclpy imports to work on macOS without actual ROS2 apt deps.
"""

import queue
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml

# ── Task 0: Ros2BridgeConfig tests ──────────────────────────────────────


class TestRos2BridgeConfig:
    """Tests for Ros2BridgeConfig Pydantic v2 dataclass."""

    def test_import_config_class(self):
        """Test 1: Ros2BridgeConfig imports without error."""
        from surg_rl.ros2.config import Ros2BridgeConfig

        assert Ros2BridgeConfig is not None

    def test_default_config_creation(self):
        """Test 2: Create config with only required fields, verify defaults."""
        from surg_rl.ros2.config import Ros2BridgeConfig

        c = Ros2BridgeConfig(
            state_topic="/surg_rl/joint_states",
            command_topic="/surg_rl/commands",
        )
        assert c.state_topic == "/surg_rl/joint_states"
        assert c.command_topic == "/surg_rl/commands"
        assert c.frame_id == "world"
        assert c.batch_size == 1
        assert c.qos_profile == "sensor_data"
        assert c.on_missing_topic == "error"
        assert c.on_nan_inf == "raise"
        assert c.on_dimension_mismatch == "zero"

    def test_validate_from_yaml_dict(self):
        """Test 3: Parsing from YAML dict works correctly."""
        from surg_rl.ros2.config import Ros2BridgeConfig

        yaml_data = {
            "state_topic": "/custom/joint_states",
            "command_topic": "/custom/commands",
            "frame_id": "base_link",
            "batch_size": 4,
            "qos_profile": "default",
            "on_missing_topic": "warn",
            "on_nan_inf": "sanitize",
            "on_dimension_mismatch": "zero",
        }
        c = Ros2BridgeConfig(**yaml_data)
        assert c.state_topic == "/custom/joint_states"
        assert c.command_topic == "/custom/commands"
        assert c.frame_id == "base_link"
        assert c.batch_size == 4
        assert c.qos_profile == "default"
        assert c.on_missing_topic == "warn"
        assert c.on_nan_inf == "sanitize"
        assert c.on_dimension_mismatch == "zero"

    def test_missing_required_fields_raise_error(self):
        """Test 4: Missing state_topic or command_topic raises ValidationError."""
        from pydantic import ValidationError

        from surg_rl.ros2.config import Ros2BridgeConfig

        # Missing command_topic
        with pytest.raises(ValidationError):
            Ros2BridgeConfig(state_topic="/test")

        # Missing state_topic
        with pytest.raises(ValidationError):
            Ros2BridgeConfig(command_topic="/test")

        # Empty constructor
        with pytest.raises(ValidationError):
            Ros2BridgeConfig()  # type: ignore[call-arg]

    def test_from_yaml_classmethod(self, tmp_path):
        """Test from_yaml() classmethod loads YAML file correctly."""
        from surg_rl.ros2.config import Ros2BridgeConfig

        yaml_path = tmp_path / "ros2_bridge.yaml"
        yaml_path.write_text(
            yaml.dump({
                "state_topic": "/yaml/joint_states",
                "command_topic": "/yaml/commands",
                "frame_id": "odom",
                "batch_size": 8,
            })
        )
        c = Ros2BridgeConfig.from_yaml(str(yaml_path))
        assert c.state_topic == "/yaml/joint_states"
        assert c.command_topic == "/yaml/commands"
        assert c.frame_id == "odom"
        assert c.batch_size == 8

    def test_from_yaml_missing_file_warns(self, tmp_path):
        """Test from_yaml with missing file returns default config."""
        from surg_rl.ros2.config import Ros2BridgeConfig

        missing_path = tmp_path / "nonexistent.yaml"
        with pytest.warns(UserWarning):
            with pytest.raises(FileNotFoundError):
                Ros2BridgeConfig.from_yaml(str(missing_path))


# ── Task 1: Ros2BridgeNode tests ────────────────────────────────────────


class TestHASROS2Flag:
    """Tests for the HAS_ROS2 flag and import guard."""

    def test_has_ros2_flag_exists(self):
        """Test 1: HAS_ROS2 is a boolean at module level."""
        from surg_rl.ros2 import HAS_ROS2

        assert isinstance(HAS_ROS2, bool)

    def test_ros2bridge_importable_without_rclpy(self):
        """Test 2: Ros2BridgeNode importable even when HAS_ROS2 is False."""
        # On macOS, HAS_ROS2 is False and bridge_node still imports
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        assert Ros2BridgeNode is not None


class TestRos2BridgeNodeDummy:
    """Tests for the dummy Ros2BridgeNode (when HAS_ROS2 is False)."""

    def test_dummy_node_creation(self):
        """Dummy node creates without rclpy."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(
            joint_names=["joint1", "joint2"],
            publisher_topic="/surg_rl/joint_states",
            command_topic="/surg_rl/commands",
        )
        assert node is not None

    def test_dummy_publish_state_noop(self):
        """Dummy node publish_state is no-op."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(
            joint_names=["joint1", "joint2"],
        )
        # Should not raise on dummy node
        node.publish_state(
            np.array([0.0, 0.0]), np.array([0.0, 0.0])
        )

    def test_dummy_get_latest_command_returns_none(self):
        """Dummy node get_latest_command returns None."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(joint_names=["joint1"])
        result = node.get_latest_command()
        assert result is None

    def test_dummy_setup_joint_names_noop(self):
        """Dummy node setup_joint_names is no-op."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(joint_names=["joint1"])
        node.setup_joint_names(["joint2", "joint3"])
        # No error means success for dummy


class TestRos2BridgeNodeMocked:
    """Tests for the real Ros2BridgeNode (mocked rclpy)."""

    @pytest.fixture
    def mock_rclpy(self):
        """Mock rclpy, Node, sensor_msgs, std_msgs for testing on any platform."""
        with patch("rclpy.node.Node") as mock_node, \
             patch("sensor_msgs.msg.JointState") as mock_js, \
             patch("std_msgs.msg.Float64MultiArray") as mock_fma:
            yield {
                "Node": mock_node,
                "JointState": mock_js,
                "Float64MultiArray": mock_fma,
            }

    def test_bridge_node_publisher_creation(self, mock_rclpy):
        """Test 3: Node creates publisher for JointState."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(
            joint_names=["joint1", "joint2"],
            publisher_topic="/test/joint_states",
            command_topic="/test/commands",
        )
        mock_node = mock_rclpy["Node"]
        mock_node.assert_called_once_with("surg_rl_bridge")

    def test_bridge_node_subscriber_creation(self, mock_rclpy):
        """Test 4: Node creates subscriber for Float64MultiArray."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(
            joint_names=["joint1", "joint2"],
            publisher_topic="/test/joint_states",
            command_topic="/test/commands",
        )
        assert node._command_queue.maxsize == 1

    def test_get_latest_command_empty_queue(self):
        """Test 5: get_latest_command returns None when queue is empty."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(
            joint_names=["joint1"],
            publisher_topic="/test/joint_states",
            command_topic="/test/commands",
        )
        result = node.get_latest_command()
        assert result is None

    def test_get_latest_command_with_data(self):
        """Test get_latest_command returns data when queue has content."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(
            joint_names=["joint1", "joint2"],
            publisher_topic="/test/joint_states",
            command_topic="/test/commands",
        )
        test_cmd = np.array([0.5, -0.3], dtype=np.float64)
        node._command_queue.put_nowait(test_cmd)
        result = node.get_latest_command()
        np.testing.assert_array_equal(result, test_cmd)

    def test_repr_shows_topic_names(self):
        """Test __repr__ shows topic names."""
        from surg_rl.ros2.bridge_node import Ros2BridgeNode

        node = Ros2BridgeNode(
            joint_names=["joint1"],
            publisher_topic="/pub/topic",
            command_topic="/sub/topic",
        )
        repr_str = repr(node)
        assert "/pub/topic" in repr_str
        assert "/sub/topic" in repr_str
