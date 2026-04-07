#!/usr/bin/env python3
"""Scene visualization example for Surg-RL.

This script demonstrates how to visualize surgical scenes using various methods.
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from surg_rl.scene_definition import load_scene


def print_scene_tree(scene_data: dict, indent: int = 0):
    """Print scene structure as a tree."""
    prefix = "  " * indent
    
    if isinstance(scene_data, dict):
        for key, value in scene_data.items():
            if isinstance(value, (dict, list)):
                if isinstance(value, dict) and len(value) == 0:
                    print(f"{prefix}{key}: {{}}")
                elif isinstance(value, list) and len(value) == 0:
                    print(f"{prefix}{key}: []")
                elif isinstance(value, list) and len(value) > 0:
                    print(f"{prefix}{key}: [{len(value)} items]")
                    for i, item in enumerate(value[:3]):  # Show first 3
                        if isinstance(item, dict):
                            print(f"{prefix}  [{i}]:")
                            print_scene_tree(item, indent + 2)
                        else:
                            print(f"{prefix}  [{i}]: {item}")
                    if len(value) > 3:
                        print(f"{prefix}  ... and {len(value) - 3} more")
                else:
                    print(f"{prefix}{key}:")
                    print_scene_tree(value, indent + 1)
            else:
                print(f"{prefix}{key}: {value}")
    else:
        print(f"{prefix}{scene_data}")


def visualize_scene_ascii(scene):
    """Create ASCII visualization of scene."""
    print("\n" + "="*80)
    print("  SCENE VISUALIZATION (ASCII)")
    print("="*80)
    
    # Metadata
    print(f"\nScene: {scene.metadata.name}")
    print(f"Version: {scene.metadata.version}")
    print(f"Description: {scene.metadata.description}")
    print(f"Tags: {', '.join(scene.metadata.tags)}")
    
    # Top-down view (simplified)
    print("\nTop-Down View (simplified):")
    print("  " + "─"*70)
    print("  │" + " "*68 + "│")
    
    # Draw robots
    for robot in scene.robots:
        pos = robot.base_pose.position
        x = int((pos.x + 0.5) * 30)  # Scale to fit
        y = int((pos.y + 0.5) * 30)
        print(f"  │  Robot '{robot.name}' at ({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f})")
    
    # Draw tissues
    for tissue in scene.tissues:
        pos = tissue.pose.position
        print(f"  │  Tissue '{tissue.name}' at ({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f})")
        if tissue.geometry.primitive == "box":
            dims = tissue.geometry.dimensions
            print(f"  │    Dimensions: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} m")
    
    # Draw instruments
    for instrument in scene.instruments:
        pos = instrument.pose.position
        print(f"  │  Instrument '{instrument.name}' at ({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f})")
    
    print("  │" + " "*68 + "│")
    print("  " + "─"*70)
    
    # Physics configuration
    print("\nPhysics Configuration:")
    print(f"  Gravity: {scene.physics.gravity}")
    print(f"  Timestep: {scene.physics.timestep}s")
    print(f"  Solver: {scene.physics.integrator} ({scene.physics.solver_iterations} iterations)")
    
    # Task information
    print(f"\nTask: {scene.task.name}")
    print(f"  Objectives: {len(scene.task.objectives)}")
    for i, obj in enumerate(scene.task.objectives, 1):
        print(f"    {i}. {obj.name}: {obj.description}")
    
    print("\n" + "="*80)


def export_scene_summary(scene, output_file: str):
    """Export scene summary to JSON."""
    summary = {
        "metadata": {
            "name": scene.metadata.name,
            "version": scene.metadata.version,
            "description": scene.metadata.description,
            "tags": scene.metadata.tags
        },
        "statistics": {
            "num_robots": len(scene.robots),
            "num_tissues": len(scene.tissues),
            "num_instruments": len(scene.instruments),
            "num_cameras": len(scene.environment.cameras),
            "num_lights": len(scene.environment.lights),
            "num_objectives": len(scene.task.objectives),
            "num_constraints": len(scene.task.constraints)
        },
        "physics": {
            "gravity": scene.physics.gravity,
            "timestep": scene.physics.timestep,
            "integrator": scene.physics.integrator
        },
        "task": {
            "name": scene.task.name,
            "max_episode_length": scene.task.max_episode_length,
            "time_limit": scene.task.time_limit
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✓ Scene summary exported to {output_file}")


def generate_scene_report(scene, output_dir: str):
    """Generate a comprehensive scene report."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)
    
    # Text report
    report_file = output_path / f"{scene.metadata.name.replace(' ', '_')}_report.txt"
    
    with open(report_file, 'w') as f:
        f.write(f"{'='*80}\n")
        f.write(f"SCENE REPORT: {scene.metadata.name}\n")
        f.write(f"{'='*80}\n\n")
        
        f.write("METADATA\n")
        f.write(f"{'─'*80}\n")
        f.write(f"Name: {scene.metadata.name}\n")
        f.write(f"Version: {scene.metadata.version}\n")
        f.write(f"Author: {scene.metadata.author}\n")
        f.write(f"Created: {scene.metadata.created}\n")
        f.write(f"Description: {scene.metadata.description}\n")
        f.write(f"Tags: {', '.join(scene.metadata.tags)}\n\n")
        
        f.write("PHYSICS\n")
        f.write(f"{'─'*80}\n")
        f.write(f"Gravity: {scene.physics.gravity}\n")
        f.write(f"Timestep: {scene.physics.timestep}s\n")
        f.write(f"Integrator: {scene.physics.integrator}\n")
        f.write(f"Solver Iterations: {scene.physics.solver_iterations}\n")
        f.write(f"Materials: {len(scene.physics.materials)}\n\n")
        
        f.write("ROBOTS\n")
        f.write(f"{'─'*80}\n")
        for i, robot in enumerate(scene.robots, 1):
            f.write(f"\nRobot {i}: {robot.name}\n")
            f.write(f"  Type: {robot.type}\n")
            f.write(f"  Description: {robot.description}\n")
            f.write(f"  Control Mode: {robot.control_mode}\n")
            f.write(f"  Control Rate: {robot.control_rate} Hz\n")
            f.write(f"  End Effectors: {len(robot.end_effectors)}\n")
            for ee in robot.end_effectors:
                f.write(f"    - {ee.name} ({ee.type})\n")
        
        f.write("\n\nTISSUES\n")
        f.write(f"{'─'*80}\n")
        for i, tissue in enumerate(scene.tissues, 1):
            f.write(f"\nTissue {i}: {tissue.name}\n")
            f.write(f"  Type: {tissue.type}\n")
            f.write(f"  Description: {tissue.description}\n")
            f.write(f"  Stiffness: {tissue.physics.stiffness} N/m\n")
            f.write(f"  Damping: {tissue.physics.damping}\n")
            f.write(f"  Density: {tissue.physics.density} kg/m³\n")
        
        f.write("\n\nINSTRUMENTS\n")
        f.write(f"{'─'*80}\n")
        for i, inst in enumerate(scene.instruments, 1):
            f.write(f"\nInstrument {i}: {inst.name}\n")
            f.write(f"  Type: {inst.type}\n")
            f.write(f"  Description: {inst.description}\n")
            f.write(f"  Mass: {inst.physics.mass} kg\n")
        
        f.write("\n\nTASK\n")
        f.write(f"{'─'*80}\n")
        f.write(f"Name: {scene.task.name}\n")
        f.write(f"Description: {scene.task.description}\n")
        f.write(f"Max Episode Length: {scene.task.max_episode_length}\n")
        f.write(f"Time Limit: {scene.task.time_limit}s\n\n")
        
        f.write("Objectives:\n")
        for i, obj in enumerate(scene.task.objectives, 1):
            f.write(f"  {i}. {obj.name}\n")
            f.write(f"     {obj.description}\n")
            f.write(f"     Success: {obj.success_criteria}\n")
            f.write(f"     Weight: {obj.weight}\n")
        
        f.write("\nConstraints:\n")
        for i, constraint in enumerate(scene.task.constraints, 1):
            f.write(f"  {i}. {constraint.name} ({constraint.type})\n")
            f.write(f"     Target: {constraint.target_entity}\n")
            f.write(f"     Limits: {constraint.limits}\n")
        
        f.write("\n\nDOMAIN RANDOMIZATION\n")
        f.write(f"{'─'*80}\n")
        f.write(f"Physics: {scene.domain_randomization.physics.enabled}\n")
        f.write(f"Visual: {scene.domain_randomization.visual.enabled}\n")
        f.write(f"Randomize Each Episode: {scene.domain_randomization.randomize_each_episode}\n")
        
        f.write(f"\n\n{'='*80}\n")
        f.write(f"END OF REPORT\n")
        f.write(f"{'='*80}\n")
    
    print(f"✓ Scene report saved to {report_file}")
    
    # Also save JSON summary
    summary_file = output_path / f"{scene.metadata.name.replace(' ', '_')}_summary.json"
    export_scene_summary(scene, summary_file)


def main():
    """Main visualization function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Visualize Surg-RL scenes")
    parser.add_argument("scene_file", help="Path to scene file (JSON or YAML)")
    parser.add_argument("--output-dir", "-o", default="scene_visualizations",
                        help="Output directory for reports")
    parser.add_argument("--ascii", action="store_true", help="Show ASCII visualization")
    parser.add_argument("--report", action="store_true", help="Generate full report")
    
    args = parser.parse_args()
    
    # Load scene
    print(f"\nLoading scene: {args.scene_file}")
    scene = load_scene(args.scene_file)
    print(f"✓ Scene loaded successfully")
    
    # Show ASCII visualization
    if args.ascii:
        visualize_scene_ascii(scene)
    
    # Generate report
    if args.report:
        generate_scene_report(scene, args.output_dir)
    
    # Default: show summary
    if not args.ascii and not args.report:
        print(f"\nScene Summary:")
        print(f"  Name: {scene.metadata.name}")
        print(f"  Robots: {len(scene.robots)}")
        print(f"  Tissues: {len(scene.tissues)}")
        print(f"  Instruments: {len(scene.instruments)}")
        print(f"  Task: {scene.task.name}")
        print(f"\nUse --ascii for visual representation")
        print(f"Use --report to generate full report")


if __name__ == "__main__":
    main()
