"""Tests for multi-agent RL schema: ArmRole, ArmConfig, MultiAgentConfig.

Phase 22 Plan 01 — Schema extension for dual-arm scenes.
"""

import json

import pytest
from pydantic import ValidationError

from surg_rl.scene_definition.schema import (
    ArmConfig,
    ArmRole,
    MultiAgentConfig,
    RobotConfig,
    SceneDefinition,
)


class TestArmRole:
    """ArmRole enum tests."""

    def test_armrole_surgeon_construction(self):
        """ArmRole("surgeon") succeeds and equals ArmRole.SURGEON."""
        role = ArmRole("surgeon")
        assert role == ArmRole.SURGEON
        assert role.value == "surgeon"

    def test_armrole_assistant_construction(self):
        """ArmRole("assistant") succeeds and equals ArmRole.ASSISTANT."""
        role = ArmRole("assistant")
        assert role == ArmRole.ASSISTANT
        assert role.value == "assistant"

    def test_armrole_is_str_enum(self):
        """ArmRole is a str Enum."""
        assert issubclass(ArmRole, str)
        assert isinstance(ArmRole.SURGEON, str)


class TestArmConfig:
    """ArmConfig model tests."""

    def test_armconfig_valid_surgeon(self):
        """ArmConfig(role="surgeon", robot_ref="robot_1") validates."""
        config = ArmConfig(role="surgeon", robot_ref="robot_1")
        assert config.role == ArmRole.SURGEON
        assert config.robot_ref == "robot_1"
        assert config.observation_keys is None

    def test_armconfig_invalid_role_raises(self):
        """ArmConfig(role="invalid", robot_ref="r1") raises ValidationError."""
        with pytest.raises(ValidationError):
            ArmConfig(role="invalid", robot_ref="r1")

    def test_armconfig_model_validate_assistant(self):
        """ArmConfig.model_validate with assistant role produces correct values."""
        config = ArmConfig.model_validate({"role": "assistant", "robot_ref": "davinci_right"})
        assert config.role == ArmRole.ASSISTANT
        assert config.robot_ref == "davinci_right"

    def test_armconfig_empty_robot_ref_raises(self):
        """ArmConfig with empty robot_ref raises ValidationError."""
        with pytest.raises(ValidationError):
            ArmConfig(role="surgeon", robot_ref="")

    def test_armconfig_with_observation_keys(self):
        """ArmConfig with observation_keys list validates."""
        config = ArmConfig(
            role="surgeon",
            robot_ref="robot_1",
            observation_keys=["joint_positions", "ee_pose"],
        )
        assert config.observation_keys == ["joint_positions", "ee_pose"]


class TestMultiAgentConfig:
    """MultiAgentConfig model tests."""

    def test_valid_two_arms(self):
        """MultiAgentConfig with 2 arm_configs validates."""
        config = MultiAgentConfig(
            arm_configs=[
                {"role": "surgeon", "robot_ref": "r1"},
                {"role": "assistant", "robot_ref": "r2"},
            ]
        )
        assert len(config.arm_configs) == 2
        assert config.num_agents == 2

    def test_existing_fields_preserved(self):
        """shared_policy defaults to True; cooperative, observation_sharing work."""
        config = MultiAgentConfig(
            arm_configs=[
                {"role": "surgeon", "robot_ref": "r1"},
                {"role": "assistant", "robot_ref": "r2"},
            ]
        )
        assert config.shared_policy is True
        assert config.cooperative is True
        assert config.observation_sharing is False

    def test_duplicate_roles_raises(self):
        """Duplicate roles in arm_configs raises ValidationError."""
        with pytest.raises(ValidationError, match="Duplicate roles"):
            MultiAgentConfig(
                arm_configs=[
                    {"role": "surgeon", "robot_ref": "r1"},
                    {"role": "surgeon", "robot_ref": "r2"},
                ]
            )

    def test_single_arm_raises(self):
        """arm_configs with fewer than 2 entries raises ValidationError."""
        with pytest.raises(ValidationError):
            MultiAgentConfig(arm_configs=[{"role": "surgeon", "robot_ref": "r1"}])

    def test_empty_arm_configs_raises(self):
        """arm_configs=[] raises ValidationError (min_length=2)."""
        with pytest.raises(ValidationError):
            MultiAgentConfig(arm_configs=[])

    def test_no_agent_roles_field(self):
        """MultiAgentConfig does not have agent_roles field (replaced by arm_configs)."""
        config = MultiAgentConfig(
            arm_configs=[
                {"role": "surgeon", "robot_ref": "r1"},
                {"role": "assistant", "robot_ref": "r2"},
            ]
        )
        assert not hasattr(config, "agent_roles")

    def test_num_agents_is_property_not_field(self):
        """num_agents is a computed property, not a Field."""
        config = MultiAgentConfig(
            arm_configs=[
                {"role": "surgeon", "robot_ref": "r1"},
                {"role": "assistant", "robot_ref": "r2"},
            ]
        )
        assert config.num_agents == 2
        # Should NOT be accepted as a constructor parameter
        with pytest.raises(ValidationError):
            MultiAgentConfig(
                arm_configs=[
                    {"role": "surgeon", "robot_ref": "r1"},
                    {"role": "assistant", "robot_ref": "r2"},
                ],
                num_agents=3,
            )

    def test_get_arm_by_role(self):
        """get_arm() returns correct ArmConfig by role."""
        config = MultiAgentConfig(
            arm_configs=[
                {"role": "surgeon", "robot_ref": "r1"},
                {"role": "assistant", "robot_ref": "r2"},
            ]
        )
        surgeon = config.get_arm(ArmRole.SURGEON)
        assert surgeon is not None
        assert surgeon.robot_ref == "r1"

        assistant = config.get_arm("assistant")
        assert assistant is not None
        assert assistant.robot_ref == "r2"

        camera = config.get_arm("camera")
        assert camera is None

    def test_shared_policy_override(self):
        """shared_policy can be set to False."""
        config = MultiAgentConfig(
            arm_configs=[
                {"role": "surgeon", "robot_ref": "r1"},
                {"role": "assistant", "robot_ref": "r2"},
            ],
            shared_policy=False,
        )
        assert config.shared_policy is False


# ============================================================================
# Task 2: Cross-validation + Round-trip + SceneLoader
# ============================================================================


class TestMultiAgentCrossValidation:
    """Tests for SceneDefinition multi_agent cross-validation."""

    @staticmethod
    def _make_robot(name: str) -> RobotConfig:
        """Create a minimal RobotConfig for testing."""
        return RobotConfig(
            name=name,
            type="davinci",
            urdf_path="fake_robot.urdf",  # Needed to satisfy RobotConfig validator
            base_pose={"position": {"x": 0, "y": 0, "z": 0}},
        )

    def test_missing_robot_ref_raises(self):
        """SceneDefinition with multi_agent pointing to missing robot_ref raises."""
        with pytest.raises(ValidationError, match="robot_ref"):
            SceneDefinition(
                robots=[
                    self._make_robot("robot_1"),
                ],
                multi_agent={
                    "arm_configs": [
                        {"role": "surgeon", "robot_ref": "robot_1"},
                        {"role": "assistant", "robot_ref": "robot_2_does_not_exist"},
                    ]
                },
            )

    def test_valid_dual_arm_scene(self):
        """SceneDefinition with multi_agent pointing to 2 valid robot names validates."""
        scene = SceneDefinition(
            robots=[
                self._make_robot("davinci_left"),
                self._make_robot("davinci_right"),
            ],
            multi_agent={
                "arm_configs": [
                    {"role": "surgeon", "robot_ref": "davinci_left"},
                    {"role": "assistant", "robot_ref": "davinci_right"},
                ]
            },
        )
        assert scene.multi_agent is not None
        assert scene.multi_agent.num_agents == 2
        assert scene.multi_agent.num_agents == 2

    def test_null_multi_agent_validates(self):
        """SceneDefinition with multi_agent=None validates (single-arm backward compat)."""
        scene = SceneDefinition(
            robots=[self._make_robot("robot_1")],
            multi_agent=None,
        )
        assert scene.multi_agent is None

    def test_multi_agent_not_provided_validates(self):
        """SceneDefinition without multi_agent defaults to None."""
        scene = SceneDefinition(
            robots=[self._make_robot("robot_1")],
        )
        assert scene.multi_agent is None


class TestMultiAgentRoundTrip:
    """Round-trip serialization tests."""

    def test_json_round_trip(self):
        """JSON round-trip: dump -> load produces identical MultiAgentConfig."""
        config = MultiAgentConfig(
            arm_configs=[
                {"role": "surgeon", "robot_ref": "r1"},
                {"role": "assistant", "robot_ref": "r2"},
            ],
            shared_policy=False,
            cooperative=True,
            observation_sharing=True,
        )
        json_str = config.model_dump_json()
        config2 = MultiAgentConfig.model_validate_json(json_str)
        assert config2.arm_configs[0].role == ArmRole.SURGEON
        assert config2.arm_configs[0].robot_ref == "r1"
        assert config2.arm_configs[1].role == ArmRole.ASSISTANT
        assert config2.arm_configs[1].robot_ref == "r2"
        assert config2.shared_policy is False
        assert config2.cooperative is True
        assert config2.observation_sharing is True
        assert config2.num_agents == 2

    def test_yaml_round_trip(self):
        """YAML round-trip preserves ArmConfig values with Enum->string conversion."""
        config = MultiAgentConfig(
            arm_configs=[
                {"role": "surgeon", "robot_ref": "r1"},
                {"role": "assistant", "robot_ref": "r2"},
            ]
        )
        d = config.model_dump()
        # model_dump returns Enum objects, not values
        assert d["arm_configs"][0]["role"] == ArmRole.SURGEON
        assert d["arm_configs"][1]["role"] == ArmRole.ASSISTANT
        # Re-validate from dict
        config2 = MultiAgentConfig.model_validate(d)
        assert config2.arm_configs[0].role == ArmRole.SURGEON
        assert config2.arm_configs[0].robot_ref == "r1"

    def test_scene_definition_json_round_trip(self):
        """SceneDefinition dual-arm JSON round-trip."""
        scene = SceneDefinition(
            robots=[
                TestMultiAgentCrossValidation._make_robot("r1"),
                TestMultiAgentCrossValidation._make_robot("r2"),
            ],
            multi_agent={
                "arm_configs": [
                    {"role": "surgeon", "robot_ref": "r1"},
                    {"role": "assistant", "robot_ref": "r2"},
                ]
            },
        )
        json_str = scene.model_dump_json()
        scene2 = SceneDefinition.model_validate_json(json_str)
        assert scene2.multi_agent is not None
        assert scene2.multi_agent.num_agents == 2
        assert scene2.multi_agent.get_arm("surgeon").robot_ref == "r1"


class TestMultiAgentSceneLoader:
    """SceneLoader integration tests for dual-arm scenes."""

    def test_loader_loads_dual_arm_json(self, tmp_path):
        """SceneLoader loads a dual-arm JSON scene file with multi_agent populated."""

        from surg_rl.scene_definition.loader import SceneLoader

        scene_dict = {
            "metadata": {"name": "Dual Arm Scene"},
            "robots": [
                {
                    "name": "davinci_left",
                    "type": "davinci",
                    "urdf_path": "fake_left.urdf",
                    "base_pose": {"position": {"x": -0.2, "y": 0, "z": 0}},
                },
                {
                    "name": "davinci_right",
                    "type": "davinci",
                    "urdf_path": "fake_right.urdf",
                    "base_pose": {"position": {"x": 0.2, "y": 0, "z": 0}},
                },
            ],
            "multi_agent": {
                "arm_configs": [
                    {"role": "surgeon", "robot_ref": "davinci_left"},
                    {"role": "assistant", "robot_ref": "davinci_right"},
                ],
                "shared_policy": True,
                "cooperative": True,
                "observation_sharing": False,
            },
        }
        scene_path = tmp_path / "dual_arm_scene.json"
        scene_path.write_text(json.dumps(scene_dict))

        loader = SceneLoader()
        scene = loader.load(scene_path, use_cache=False)

        assert scene.multi_agent is not None
        assert scene.multi_agent.num_agents == 2
        assert scene.multi_agent.shared_policy is True
        surgeon = scene.multi_agent.get_arm("surgeon")
        assert surgeon is not None
        assert surgeon.robot_ref == "davinci_left"
        assistant = scene.multi_agent.get_arm("assistant")
        assert assistant is not None
        assert assistant.robot_ref == "davinci_right"
