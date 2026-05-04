# 12-02 Summary: URDF ros2_control Tags

**Plan:** 12-02-PLAN.md
**Status:** Complete
**Commits:** 1

## Accomplishments

- Added `_inject_ros2_control_tags()` static method to `SceneBuilder` — injects standard `<ros2_control>` XML with position/velocity interfaces and `mock_components/GenericSystem` hardware plugin
- Added `create_urdf()` method to `SceneBuilder` — generates minimal URDF with optional ros2_control tag injection
- Added `_collect_joint_names()` helper to extract joint names from robot configs
- Uses existing `xml.etree.ElementTree` patterns already in `create_mjcf()`

## Files Modified

| File | Change |
|------|--------|
| `src/surg_rl/simulators/scene_builder.py` | +72 lines: `_inject_ros2_control_tags`, `create_urdf`, `_collect_joint_names` |

## Self-Check: PASSED

- `_inject_ros2_control_tags()` produces valid XML with correct interface entries
- Multiple joints produce correct interface count (2 state interfaces each)
- `mock_components/GenericSystem` plugin referenced correctly
