# /parallel-plan

## Description
Generate a dependency-ordered plan for parallel feature implementation, with collision warnings and branch suggestions.

## Usage
```
/parallel-plan feature1 feature2 ...
```

## Examples
```
/parallel-plan soft-body-physics vectorized-envs tensorboard-callbacks
```

## Steps

1. Read the current branch and recent commits to establish the base commit.
2. For each feature, identify the primary files it will touch by searching the codebase for related keywords (e.g., "soft body" → `scene_builder.py`, `mujoco_simulator.py`, `schema.py`).
3. Build a dependency graph:
   - Schema changes (`scene_definition/schema.py`) must come first.
   - Simulator changes (`simulators/*.py`) depend on schema.
   - Scene generation (`scene_generation/*.py`) depends on simulators.
   - RL/training changes (`rl/*.py`) depend on simulators and scene generation.
   - Tests depend on everything.
4. Warn about file collisions: if two features both modify `scene_builder.py` or `test_simulators.py`, flag them as high-conflict and suggest either:
   - Assigning one agent to own the shared file and others to produce patches, OR
   - Merging sequentially rather than in parallel.
5. Output:
   - Ordered feature list (dependency order)
   - For each feature: branch name, estimated files, collision risk (low/medium/high)
   - Suggested merge order
   - Reminder: limit per-agent debug loops to 3; use Python scripts, not `sed`, for multi-line edits.

## Rules
- Branch names: `feature/<kebab-case-name>`
- Base commit: current HEAD
- Collision threshold: 2+ features touching the same file = HIGH risk
- Always include `pytest` after each merge step in the suggested order
