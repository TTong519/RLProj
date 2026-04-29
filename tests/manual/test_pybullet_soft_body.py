#!/usr/bin/env python3
"""Manual harness for PyBullet soft body loading.

Run directly:
    python tests/manual/test_pybullet_soft_body.py

Exit codes:
    0 - success
    1 - crash / failure
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from surg_rl.scene_definition.schema import (
    SceneDefinition,
    TissueConfig,
    TissueMeshDefinition,
    SoftBodyPhysics,
)
from surg_rl.simulators.pybullet_simulator import PyBulletSimulator


def test_load_box():
    scene = SceneDefinition(
        metadata={"name": "manual_soft"},
        robots=[],
        tissues=[
            TissueConfig(
                name="soft_box",
                geometry=TissueMeshDefinition(
                    primitive="box", dimensions=(0.1, 0.1, 0.01)
                ),
                soft_body=True,
                physics=SoftBodyPhysics(),
            )
        ],
        instruments=[],
    )
    sim = PyBulletSimulator()
    sim.load_scene(scene)
    assert "soft_box" in sim._soft_body_ids
    data = sim._pb.getMeshData(
        sim._soft_body_ids["soft_box"], physicsClientId=sim._physics_client
    )
    assert len(data[1]) > 0, "Expected >0 vertices in mesh data"
    # Step a few frames
    for _ in range(10):
        sim._pb.stepSimulation(physicsClientId=sim._physics_client)
    sim.close()
    print("PASS: box soft body loaded and stepped successfully")


def test_load_sphere():
    scene = SceneDefinition(
        metadata={"name": "manual_soft_sphere"},
        robots=[],
        tissues=[
            TissueConfig(
                name="soft_sphere",
                geometry=TissueMeshDefinition(
                    primitive="sphere",
                    dimensions=(0.05, 0.05, 0.05),
                    radius=0.05,
                ),
                soft_body=True,
                physics=SoftBodyPhysics(),
            )
        ],
        instruments=[],
    )
    sim = PyBulletSimulator()
    sim.load_scene(scene)
    assert "soft_sphere" in sim._soft_body_ids
    data = sim._pb.getMeshData(
        sim._soft_body_ids["soft_sphere"], physicsClientId=sim._physics_client
    )
    assert len(data[1]) > 0
    for _ in range(10):
        sim._pb.stepSimulation(physicsClientId=sim._physics_client)
    sim.close()
    print("PASS: sphere soft body loaded and stepped successfully")


if __name__ == "__main__":
    try:
        test_load_box()
        test_load_sphere()
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)
