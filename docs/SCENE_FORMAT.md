# Scene Format Specification

This document describes the complete scene definition format used by Surg-RL.

## Overview

Scenes are defined using JSON or YAML files with a comprehensive Pydantic schema. Each scene contains:

- Metadata (name, description, version)
- Physics configuration
- Environment settings (lights, cameras, ground)
- Robots
- Tissues
- Instruments
- Task definition
- Domain randomization settings

## Basic Structure

### JSON Format

```json
{
  "metadata": {
    "name": "My Surgical Scene",
    "description": "A training scene",
    "version": "1.0.0"
  },
  "simulator": "mujoco",
  "physics": {
    "gravity": [0.0, 0.0, -9.81],
    "timestep": 0.002
  },
  "environment": {...},
  "robots": [...],
  "tissues": [...],
  "instruments": [...],
  "task": {...}
}
```

### YAML Format

```yaml
metadata:
  name: My Surgical Scene
  description: A training scene
  version: 1.0.0

simulator: mujoco

physics:
  gravity: [0.0, 0.0, -9.81]
  timestep: 0.002

environment: {...}
robots: [...]
tissues: [...]
instruments: [...]
task: {...}
```

## Schema Reference

### Metadata

```yaml
metadata:
  name: string              # Required
  description: string      # Optional
  version: string          # Optional, default "1.0.0"
  author: string           # Optional
  created: string          # Optional (ISO date)
  modified: string         # Optional (ISO date)
  tags: [string]           # Optional list of tags
```

### Physics Configuration

```yaml
physics:
  gravity: [0.0, 0.0, -9.81]    # Gravity vector (m/s²)
  timestep: 0.002                 # Simulation timestep (s)
  solver_iterations: 50           # Solver iterations
  integrator: implicit            # implicit or euler
  contact_model: constraint       # constraint or penalty
  air_resistance: 0.0             # Air resistance coefficient
  ground_plane: true              # Enable ground plane
  ground_friction: 0.8            # Ground friction
  ground_restitution: 0.0        # Ground restitution
  materials:                      # Physics materials
    - name: soft_tissue
      friction: 0.3
      restitution: 0.0
      damping: 0.5
```

### Environment Configuration

```yaml
environment:
  name: operating_room
  background_color:           # RGBA color
    r: 0.05
    g: 0.05
    b: 0.05
    a: 1.0
  ambient_light: [0.1, 0.1, 0.1]  # RGB ambient light
  
  lights:
    - name: main_light
      type: directional       # directional, point, spotlight, ambient
      direction: [0.0, 0.0, -1.0]
      color:
        r: 1.0
        g: 1.0
        b: 1.0
        a: 1.0
      intensity: 1.0
      cast_shadows: true
      
  cameras:
    - name: main_camera
      type: perspective        # perspective or orthographic
      pose:
        position:
          x: 0.5
          y: 0.0
          z: 0.8
        orientation:
          w: 0.924
          x: 0.0
          y: 0.383
          z: 0.0
      fov: 45.0
      near: 0.01
      far: 100.0
      active: true
      
  ground_plane:
    enabled: true
    size: [2.0, 2.0]
    color:
      r: 0.3
      g: 0.3
      b: 0.3
      a: 1.0
    friction: 0.8
```

### Robot Configuration

```yaml
robots:
  - name: surgical_arm
    type: robotic_arm          # robotic_arm, davinci, laparoscopic, custom
    description: Primary surgical manipulator
    urdf_path: assets/robots/surgical_arm.urdf
    
    base_pose:
      position:
        x: 0.0
        y: 0.0
        z: 0.0
      orientation:
        w: 1.0
        x: 0.0
        y: 0.0
        z: 0.0
    
    control_mode: position    # position, velocity, torque
    control_rate: 100.0        # Hz
    max_linear_velocity: 0.5   # m/s
    max_angular_velocity: 1.0   # rad/s
    
    joints:                    # Optional joint configurations
      - name: joint_1
        type: revolute
        limits:
          lower: -3.14159
          upper: 3.14159
        damping: 0.1
        
    end_effectors:
      - name: needle_driver
        type: needle_driver
        max_aperture: 0.02      # meters
        force_limit: 10.0       # Newtons
```

### Tissue Configuration

```yaml
tissues:
  - name: skin_pad
    type: skin                # skin, muscle, organ, vessel, fat, cartilage, bone, custom
    description: Practice skin pad
    
    geometry:
      mesh:                    # Optional mesh reference
        path: assets/meshes/skin.obj
        scale: [1.0, 1.0, 1.0]
      primitive: box          # box, sphere, cylinder, capsule, plane
      dimensions: [0.1, 0.1, 0.01]
    
    physics:
      stiffness: 5000.0       # N/m
      damping: 0.15
      density: 1100.0          # kg/m³
      poissons_ratio: 0.45
      youngs_modulus: 15000.0  # Pa
      tear_threshold: 5000.0   # Pa
    
    pose:
      position:
        x: 0.3
        y: 0.0
        z: 0.05
      orientation:
        w: 1.0
        x: 0.0
        y: 0.0
        z: 0.0
    
    color:
      r: 0.95
      g: 0.85
      b: 0.8
      a: 1.0
    
    attachments:
      - name: corner_1
        position:
          x: -0.05
          y: -0.05
          z: 0.0
        fixed: true
```

### Instrument Configuration

```yaml
instruments:
  - name: surgical_needle
    type: custom              # scalpel, forceps, needle_driver, scissors, etc.
    description: Curved surgical needle
    
    mesh:
      path: assets/instruments/curved_needle.obj
      scale: [1.0, 1.0, 1.0]
    
    physics:
      mass: 0.001             # kg
      friction: 0.2
      damping: 0.01
    
    pose:
      position:
        x: 0.35
        y: 0.0
        z: 0.1
      orientation:
        w: 1.0
        x: 0.0
        y: 0.0
        z: 0.0
    
    sterile: true
```

### Task Configuration

```yaml
task:
  name: suturing_task
  description: Thread a needle through tissue
  
  objectives:
    - name: needle_pickup
      description: Pick up the surgical needle
      success_criteria: Needle grasped with correct orientation
      weight: 1.0
      
    - name: tissue_penetration
      description: Penetrate the tissue with the needle
      success_criteria: Needle passes through tissue
      weight: 2.0
      
    - name: suture_completion
      description: Complete the suture
      success_criteria: Suture correctly placed
      weight: 3.0
  
  constraints:
    - name: force_limit
      type: force
      target_entity: surgical_arm
      limits: [0.0, 10.0]
      penalty_weight: 5.0
      
    - name: workspace_limit
      type: position
      target_entity: surgical_arm
      limits: [-0.5, 0.5]
      penalty_weight: 10.0
  
  reward_shaping:
    success_reward: 100.0
    failure_penalty: -100.0
    time_penalty: -0.01
    distance_reward_scale: 1.0
    collision_penalty: -10.0
    tissue_damage_penalty: -50.0
  
  max_episode_length: 1000
  time_limit: 120.0           # seconds
```

### Domain Randomization

```yaml
domain_randomization:
  physics:
    enabled: true
    mass_range: [0.9, 1.1]
    friction_range: [0.4, 0.6]
    stiffness_range: [4500.0, 5500.0]
    
  visual:
    enabled: true
    color_range: [0.9, 1.1]
    texture_randomization: false
    lighting_variation: [0.8, 1.2]
    
  dynamics:
    enabled: false
    joint_noise: [0.0, 0.02]
    action_noise: [0.0, 0.05]
    
  randomize_each_episode: true
  seed: 42                    # For reproducibility
```

## Example Scenes

### Minimal Scene

```json
{
  "metadata": {
    "name": "Minimal Scene",
    "description": "A minimal scene for testing"
  },
  "simulator": "mujoco"
}
```

### Suturing Scene

```yaml
metadata:
  name: Suturing Practice
  description: Basic suturing practice scene
  
simulator: mujoco

physics:
  gravity: [0.0, 0.0, -9.81]
  timestep: 0.002

robots:
  - name: surgical_arm
    type: robotic_arm
    urdf_path: assets/robots/surgical_arm.urdf
    base_pose:
      position: {x: 0.0, y: 0.0, z: 0.0}

tissues:
  - name: skin_pad
    type: skin
    geometry:
      primitive: box
      dimensions: [0.1, 0.1, 0.01]
    pose:
      position: {x: 0.3, y: 0.0, z: 0.05}

instruments:
  - name: needle
    type: needle_driver
    pose:
      position: {x: 0.35, y: 0.0, z: 0.1}

task:
  name: suturing
  objectives:
    - name: pickup
      description: Pick up the needle
      weight: 1.0
```

## Loading Scenes

### Python API

```python
from surg_rl.scene_definition import load_scene, SceneDefinition

# Load from file
scene = load_scene("my_scene.json")
scene = load_scene("my_scene.yaml")

# Access scene elements
print(scene.metadata.name)
print(len(scene.robots))
print(len(scene.tissues))
```

### CLI

```bash
# Generate scene from template
surg-rl generate --template suturing --output scene.json

# Generate from text (requires LLM)
surg-rl generate --text "Create a surgical scene" --provider ollama
```

## Validation

All scenes are validated against the Pydantic schema. Invalid fields will raise clear error messages:

```python
from surg_rl.scene_definition import SceneDefinition
from pydantic import ValidationError

try:
    scene = SceneDefinition(metadata={"invalid": "data"})
except ValidationError as e:
    print(e)
```

## Best Practices

1. **Use meaningful names**: Give entities descriptive names for easy reference
2. **Set appropriate physics**: Use realistic physics values for your simulation
3. **Organize assets**: Keep meshes organized in `assets/` subdirectories
4. **Version your scenes**: Use metadata.version to track changes
5. **Use tags**: Add tags to metadata for filtering and categorization
