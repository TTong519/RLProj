#!/usr/bin/env python3
"""Capture a ~30s demo GIF from a Surg-RL demo scene.

Usage:
  python demos/capture_demo_gif.py --task suturing --output docs/demos/suturing.gif
  python demos/capture_demo_gif.py --task knot_tying --output docs/demos/knot_tying.gif --frames 300
  python demos/capture_demo_gif.py --task needle_passing --output docs/demos/needle_passing.gif

Dependencies:
  - imageio (bundled with `[gui]` extra, or install manually)
  - The matching demo module (demos/{task}_demo.py) for reward construction helpers.

The script runs the simulator headlessly and collects rgb_array frames.
If imageio is unavailable, an ffmpeg-based fallback can be produced by
pointing ffmpeg at a pre-rendered frame sequence; this script uses imageio
as the preferred writer.
"""

# fmt: off
import sys as _omp_sys
from pathlib import Path as _omp_Path
_omp_sys.path.insert(0, str(_omp_Path(__file__).resolve().parent))
import _omp_compat  # noqa: F401, E402
import _platform_guard  # noqa: F401, E402
# fmt: on

import argparse
import sys
from pathlib import Path

# Add repo root so src/ and demos/ are importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

try:
    import imageio
except Exception as exc:  # pragma: no cover - runtime dependency hint
    print(
        "imageio is required for GIF capture. Install it with:\n"
        "  pip install imageio\n"
        "or install the [simulation] extra:\n"
        "  pip install -e '.[simulation]'"
    )
    raise SystemExit(1) from exc

from demos._common import resolve_scene
from surg_rl.rl.environment import make_env

_TASK_REWARDS = {
    "suturing": "demos.suturing_demo:build_suturing_reward",
    "knot_tying": "demos.knot_tying_demo:build_knot_tying_reward",
    "needle_passing": "demos.needle_passing_demo:build_needle_passing_reward",
}

_TASK_SCENES = {
    "suturing": "scenes/suturing_demo.json",
    "knot_tying": "scenes/knot_tying.json",
    "needle_passing": "scenes/needle_passing.json",
}


def _import_callable(dotted: str):
    mod_name, attr = dotted.rsplit(":", 1)
    mod = __import__(mod_name, fromlist=[attr])
    return getattr(mod, attr)


def _build_env(task: str, backend: str, max_episode_steps: int):
    scene_path = resolve_scene(_TASK_SCENES[task])
    reward_builder = _import_callable(_TASK_REWARDS[task])
    reward = reward_builder()
    env = make_env(
        scene_path=str(scene_path),
        simulator_type=backend,
        render_mode="rgb_array",
        max_episode_steps=max_episode_steps,
    )
    env._reward_fn = reward
    return env


def capture(
    task: str,
    output: Path,
    backend: str = "mujoco",
    frames: int = 300,
    fps: int = 10,
    max_episode_steps: int = 2000,
    deterministic: bool = True,
) -> None:
    output = output.resolve()
    repo_root = Path(__file__).resolve().parent.parent
    try:
        output.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"Output path must be inside repo root {repo_root}, got {output}") from exc

    env = _build_env(task, backend, max_episode_steps)
    obs, _info = env.reset(seed=42)

    frames_list = []

    for _ in range(frames):
        if deterministic:
            action = np.zeros_like(env.action_space.sample())
        else:
            action = env.action_space.sample()
        obs, _reward, terminated, truncated, _info = env.step(action)
        rgb = env.render()
        if rgb is not None:
            # imageio/PIL expect uint8 RGB arrays
            frames_list.append(np.asarray(rgb, dtype=np.uint8))
        if terminated or truncated:
            obs, _info = env.reset(seed=42)

    env.close()

    if not frames_list:
        raise RuntimeError("No frames were captured")

    duration_ms = int(1000 / fps)
    imageio.mimsave(str(output), frames_list, duration=duration_ms)
    print(
        f"Wrote {len(frames_list)} frames to {output} ({len(frames_list) / fps:.1f}s at {fps} FPS)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a Surg-RL demo GIF")
    parser.add_argument(
        "--task",
        required=True,
        choices=list(_TASK_SCENES.keys()),
        help="Demo task to capture",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output GIF path")
    parser.add_argument("--backend", default="mujoco", choices=["mujoco", "pybullet"])
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--max-episode-steps", type=int, default=2000)
    parser.add_argument("--deterministic", action="store_true", default=True)
    parser.add_argument("--stochastic", dest="deterministic", action="store_false")
    args = parser.parse_args()

    capture(
        task=args.task,
        output=args.output,
        backend=args.backend,
        frames=args.frames,
        fps=args.fps,
        max_episode_steps=args.max_episode_steps,
        deterministic=args.deterministic,
    )


if __name__ == "__main__":
    main()
