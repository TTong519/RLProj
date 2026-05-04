# 12-03 Summary: CLI ros2-control Command

**Plan:** 12-03-PLAN.md
**Status:** Complete
**Commits:** 1

## Accomplishments

- Added `ros2-control` typer command to CLI with:
  - `scene` positional argument (path to scene definition)
  - `--controller-yaml` option (defaults to configs/ros2_control.yaml)
  - `--launch` option for optional .launch.py file usage
- macOS graceful degradation: check `HAS_ROS2`, warn + exit 0
- Launch mode: delegates to `ros2 launch surg_rl <file>`
- Direct mode: creates SurgicalEnv with use_ros2_control=True, runs idle loop with clean Ctrl+C shutdown

## Files Modified

| File | Change |
|------|--------|
| `src/surg_rl/cli.py` | +55 lines: `ros2-control` command |

## Self-Check: PASSED

- `--help` output includes ros2-control with both options
- macOS path exits 0 with warning (no crash)
- Command parses all arguments correctly
