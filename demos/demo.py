#!/usr/bin/env python3
"""Interactive scene visualization demo for Surg-RL.

This demo opens a window to visualize surgical scenes using MuJoCo or PyBullet.
Run with: python demos/demo.py --scene scenes/simple_suturing.json
"""

import argparse
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np

from surg_rl.scene_definition import load_scene
from surg_rl.simulators import MuJoCoSimulator, PyBulletSimulator


def run_mujoco_demo(scene_file: str, headless: bool = False, steps: int = 1000):
    """Run visualization demo using MuJoCo backend.
    
    Args:
        scene_file: Path to scene JSON/YAML file.
        headless: If True, run without GUI (for testing).
        steps: Number of simulation steps to run.
    """
    print(f"\n{'='*60}")
    print("  MuJoCo Scene Visualization Demo")
    print(f"{'='*60}")
    
    # Load scene
    print(f"\n📂 Loading scene: {scene_file}")
    scene = load_scene(scene_file)
    print(f"   ✓ Scene: {scene.metadata.name}")
    print(f"   ✓ Robots: {len(scene.robots)}")
    print(f"   ✓ Tissues: {len(scene.tissues)}")
    print(f"   ✓ Instruments: {len(scene.instruments)}")
    
    # Create simulator
    print("\n🎮 Initializing MuJoCo simulator...")
    assets_dir = Path(__file__).parent.parent / "assets"
    sim = MuJoCoSimulator(
        timestep=scene.physics.timestep if hasattr(scene, 'physics') else 0.002,
        render_width=640,
        render_height=480,
        assets_dir=assets_dir,
    )
    
    # Load scene into simulator
    print("   ✓ Building scene...")
    sim.load_scene(scene)
    
    # Reset to initial state
    print("   ✓ Resetting simulation...")
    obs = sim.reset()
    
    print("\n🚀 Starting visualization...")
    print("   Controls:")
    print("   - Close window to exit")
    print("   - The scene will animate for demonstration")
    print(f"   - Running {steps} simulation steps")
    print()
    
    if headless:
        # Just run steps without rendering to window
        for i in range(steps):
            # Small random action for demo
            action = np.zeros(7)  # Placeholder action
            result = sim.step(action)
            if i % 100 == 0:
                print(f"   Step {i}/{steps}")
        print("   ✓ Completed headless run")
    else:
        # Interactive visualization using passive viewer
        try:
            # Start the passive viewer
            print("   Launching viewer window...")
            sim.start_viewer()
            
            for i in range(steps):
                # Small random action for demonstration
                action = np.zeros(7)  # Placeholder action
                result = sim.step(action)
                
                # Sync the viewer
                sim.render(mode="human")
                
                # Small delay for visualization
                time.sleep(0.01)
                
                if i % 100 == 0:
                    print(f"   Step {i}/{steps} - Reward: {result.reward:.4f}")
                    
        except KeyboardInterrupt:
            print("\n   Interrupted by user")
        finally:
            sim.close()
    
    print("\n✓ Demo completed")


def run_pybullet_demo(scene_file: str, headless: bool = False, steps: int = 1000):
    """Run visualization demo using PyBullet backend.
    
    Args:
        scene_file: Path to scene JSON/YAML file.
        headless: If True, run without GUI (DIRECT mode).
        steps: Number of simulation steps to run.
    """
    print(f"\n{'='*60}")
    print("  PyBullet Scene Visualization Demo")
    print(f"{'='*60}")
    
    # Load scene
    print(f"\n📂 Loading scene: {scene_file}")
    scene = load_scene(scene_file)
    print(f"   ✓ Scene: {scene.metadata.name}")
    print(f"   ✓ Robots: {len(scene.robots)}")
    print(f"   ✓ Tissues: {len(scene.tissues)}")
    print(f"   ✓ Instruments: {len(scene.instruments)}")
    
    # Create simulator
    print("\n🎮 Initializing PyBullet simulator...")
    assets_dir = Path(__file__).parent.parent / "assets"
    
    render_mode = "DIRECT" if headless else "GUI"
    sim = PyBulletSimulator(
        timestep=scene.physics.timestep if hasattr(scene, 'physics') else 0.002,
        render_width=640,
        render_height=480,
        assets_dir=assets_dir,
        render_mode=render_mode,
    )
    
    # Load scene into simulator
    print("   ✓ Building scene...")
    sim.load_scene(scene)
    
    # Reset to initial state
    print("   ✓ Resetting simulation...")
    obs = sim.reset()
    
    print("\n🚀 Starting visualization...")
    print("   Controls:")
    print("   - Close window to exit")
    print("   - Mouse drag to rotate view")
    print("   - Scroll to zoom")
    print(f"   - Running {steps} simulation steps")
    print()
    
    try:
        for i in range(steps):
            # Small random action for demonstration
            action = np.zeros(7)  # Placeholder action
            result = sim.step(action)
            
            if not headless:
                # PyBullet GUI mode handles rendering automatically
                sim.render(mode="human")
            
            # Small delay for visualization
            time.sleep(0.01)
            
            if i % 100 == 0:
                print(f"   Step {i}/{steps} - Reward: {result.reward:.4f}")
                
    except KeyboardInterrupt:
        print("\n   Interrupted by user")
    finally:
        sim.close()
    
    print("\n✓ Demo completed")


def main():
    parser = argparse.ArgumentParser(
        description="Visualize surgical robotics scenes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View scene with MuJoCo (default)
  python demos/demo.py --scene scenes/simple_suturing.json
  
  # View scene with PyBullet
  python demos/demo.py --scene scenes/simple_suturing.json --backend pybullet
  
  # Run headless (no GUI, for testing)
  python demos/demo.py --scene scenes/minimal_scene.json --headless
  
  # Run for more steps
  python demos/demo.py --scene scenes/simple_suturing.json --steps 5000
        """,
    )
    
    parser.add_argument(
        "--scene", "-s",
        type=str,
        default="scenes/simple_suturing.json",
        help="Path to scene file (JSON or YAML)",
    )
    parser.add_argument(
        "--backend", "-b",
        type=str,
        choices=["mujoco", "pybullet"],
        default="mujoco",
        help="Simulator backend to use (default: mujoco)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without GUI window (for testing)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=1000,
        help="Number of simulation steps to run (default: 1000)",
    )
    
    args = parser.parse_args()
    
    # Check if scene file exists
    scene_path = Path(args.scene)
    if not scene_path.exists():
        # Try relative to project root
        project_root = Path(__file__).parent.parent
        scene_path = project_root / args.scene
        if not scene_path.exists():
            print(f"Error: Scene file not found: {args.scene}")
            sys.exit(1)
    
    # Run appropriate demo
    if args.backend == "mujoco":
        run_mujoco_demo(str(scene_path), headless=args.headless, steps=args.steps)
    else:
        run_pybullet_demo(str(scene_path), headless=args.headless, steps=args.steps)


if __name__ == "__main__":
    main()
