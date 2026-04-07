# Surg-RL Demos

This directory contains demonstration scripts for the Surg-RL project.

## Demo Scripts

### demo.py - Scene Visualization

Interactive visualization of surgical scenes using MuJoCo or PyBullet.

**Usage:**

```bash
# View with MuJoCo (opens window)
python demos/demo.py --scene scenes/simple_suturing.json

# View with PyBullet (opens window)
python demos/demo.py --scene scenes/simple_suturing.json --backend pybullet

# Headless mode (no window, for testing/CI)
python demos/demo.py --scene scenes/minimal_scene.json --headless --steps 100
```

**Options:**

| Argument | Description | Default |
|----------|-------------|---------|
| `--scene, -s` | Path to scene file | `scenes/simple_suturing.json` |
| `--backend, -b` | Simulator backend (`mujoco` or `pybullet`) | `mujoco` |
| `--headless` | Run without GUI window | `false` |
| `--steps` | Number of simulation steps | `1000` |

**Controls:**

- MuJoCo: Close window to exit
- PyBullet: Mouse drag to rotate, scroll to zoom, close window to exit

## What the Demo Shows

When you run the demo, you'll see:

1. **Robot Arm** - Blue box at the origin (primitive fallback)
2. **Tissue** - Pink/peach box representing surgical tissue
3. **Instrument** - Gray box representing a surgical instrument
4. **Ground Plane** - Dark gray floor

**Note:** Since actual mesh files (URDFs, OBJs) are not included, the simulator uses primitive shapes (boxes, spheres, cylinders) as visual fallbacks. The objects are static because joint control is not yet implemented.

## Scene Files

Available scenes in `scenes/`:

| Scene | Description |
|-------|-------------|
| `simple_suturing.json` | Basic suturing scene with robot, tissue, needle |
| `laparoscopic_dissection.yaml` | Dual-arm laparoscopic scene |
| `minimal_scene.json` | Minimal scene for testing |

## Troubleshooting

### "Cannot start viewer: no display available"

This means no graphical display is available. Run in a terminal with a display, or use `--headless` mode.

### "invalid CoreGraphics connection" (macOS)

MuJoCo requires a GUI session on macOS. Use `--headless` mode if running in a terminal without display access.

### PyBullet window closes immediately

This is expected if running headless. Add `--headless` flag to suppress the warning.

## Future Demos

Coming soon (when Steps 6-8 are complete):

- Robot joint control demo
- RL training demo
- Tissue manipulation demo
- Needle passing demo
