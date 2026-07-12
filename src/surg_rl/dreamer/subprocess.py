"""DreamerV3 JAX subprocess with process isolation.

Spawns a separate Python process for JAX/dreamerv3 to avoid GPU memory
conflicts with PyTorch. Communicates via stdin/stdout JSON protocol.
"""

import contextlib
import json
import multiprocessing
import os
import sys
from collections.abc import Iterator
from typing import Any


def _subprocess_main(child_stdin, child_stdout, config: dict[str, Any]) -> None:
    """Entry point for JAX subprocess - must be at module level for pickling."""
    # Set JAX memory fraction BEFORE importing JAX
    memory_fraction = float(config.get("memory_fraction", 0.4))
    os.environ["XLA_PYTHON_CLIENT_MEM_FRACTION"] = str(memory_fraction)
    os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

    # Redirect stdout/stderr for clean JSON communication
    sys.stdout = _JsonStdout(child_stdout)
    sys.stderr = os.fdopen(2, "w", buffering=1)

    _run_subprocess_loop(child_stdin)


class _JsonStdout:
    """stdout replacement that ships lines over a multiprocessing Pipe.

    Replaces the previous `os.fdopen(child_stdout.fileno(), "w", ...)` pattern
    which was fragile on Windows (multiprocessing Pipe connections do not always
    expose a real fileno for the parent's send end) and could race with the
    parent's recv(). Now every `print(..., flush=True)` call inside the
    subprocess ends up as a single `pipe.send(json_payload)` call.
    """

    def __init__(self, pipe: Any) -> None:
        self._pipe = pipe

    def write(self, s: str) -> int:
        if not s:
            return 0
        if s == "\n":
            return 1
        # Strip trailing newline added by `print`
        payload = s.rstrip("\n")
        self._pipe.send(payload)
        return len(s)

    def flush(self) -> None:
        pass


def _run_subprocess_loop(stdin_pipe) -> None:
    """Main loop inside JAX subprocess - imports JAX/dreamerv3 here."""
    # Import JAX and DreamerV3 INSIDE subprocess
    import jax

    # Signal ready
    print(json.dumps({"type": "READY", "jax_version": jax.__version__}), flush=True)

    # Process config
    config = None
    agent = None

    while True:
        try:
            line = stdin_pipe.recv()
            if not line:
                break
            msg = json.loads(line)
        except (EOFError, json.JSONDecodeError):
            break

        msg_type = msg.get("type", "")

        if msg_type == "CONFIG":
            config = msg.get("config", {})
            # Build DreamerV3 agent config
            agent = _build_agent(config)
            print(json.dumps({"type": "CONFIG_ACK"}), flush=True)

        elif msg_type == "TRAIN":
            if agent is None:
                print(json.dumps({"type": "ERROR", "error": "Agent not configured"}), flush=True)
                continue
            total_steps = msg.get("total_steps", 100000)
            eval_every = msg.get("eval_every", 10000)
            for metrics in _train_loop(agent, total_steps, eval_every):
                print(json.dumps({"type": "METRICS", **metrics}), flush=True)
            print(json.dumps({"type": "TRAIN_COMPLETE"}), flush=True)

        elif msg_type == "EVAL":
            if agent is None:
                print(json.dumps({"type": "ERROR", "error": "Agent not configured"}), flush=True)
                continue
            checkpoint = msg.get("checkpoint")
            n_episodes = msg.get("n_episodes", 10)
            metrics = _evaluate(agent, checkpoint, n_episodes)
            print(json.dumps({"type": "EVAL_RESULT", "metrics": metrics}), flush=True)

        elif msg_type == "CHECKPOINT":
            action = msg.get("action", "save")
            path = msg.get("path")
            if action == "save" and agent:
                _save_checkpoint(agent, path)
                print(json.dumps({"type": "CHECKPOINT_SAVED", "path": path}), flush=True)
            elif action == "load" and agent:
                _load_checkpoint(agent, path)
                print(json.dumps({"type": "CHECKPOINT_LOADED", "path": path}), flush=True)

        elif msg_type == "SHUTDOWN":
            print(json.dumps({"type": "SHUTDOWN_ACK"}), flush=True)
            break

    # Cleanup
    if agent:
        with contextlib.suppress(Exception):
            agent.close()


def _build_agent(config: dict[str, Any]) -> Any:
    """Build DreamerV3 agent from config (PyPI 1.5.0 object API, D-04).

    Constructs a real ``dreamerv3.Agent`` bundle against the pinned PyPI 1.5.0
    object-based API (``Agent(obs_space, act_space, step, config)`` — 4 args),
    NOT the current-repo factory API (factory functions + the separate
    config package that describes ``danijar/dreamerv3`` main, not what the
    ``~=1.5.0`` pin installs). Returns a bundle dict with keys ``agent``,
    ``env``, ``checkpoint``, ``replay``, ``step`` that the downstream
    ``_train_loop`` / ``_evaluate`` / ``_save_checkpoint`` /
    ``_load_checkpoint`` (owned by 40-02) unpack.

    All ``jax`` / ``dreamerv3`` / ``embodied`` imports live INSIDE this
    function body (SC#5: JAX isolation — importing
    ``surg_rl.dreamer.subprocess`` in the parent process must not pull JAX
    into ``sys.modules``). The runtime GREEN (actually constructing a real
    agent) is GPU-gated and deferred to the CI ``dreamer-gpu`` job (40-04);
    locally the runtime path skips per INV-8 (dreamerv3 not installed on
    macOS). Items marked VERIFY must be confirmed against the installed
    dreamerv3 1.5.0 package on the GPU host.
    """
    # --- child-process-only imports (SC#5: JAX isolation) ---
    from pathlib import Path

    import embodied  # vendored inside dreamerv3 1.5.0 (dreamerv3/embodied/)
    from dreamerv3.agent import Agent  # 4-arg ctor (PyPI 1.5.0, D-04)
    from gymnasium import spaces

    # Local imports for the project helpers (CLAUDE.md rl-subpackage
    # import-chain fragility rule — keep these lazy/local, not module-top).
    from surg_rl.dreamer.training import _create_env, _create_scene_for_task
    from surg_rl.dreamer.wrapper import GymToEmbodiedWrapper

    task = config["task"]
    obs_type = config["obs_type"]
    pixel_resolution = tuple(config["pixel_resolution"])

    # Construct the SurgicalEnv inside the child (JAX-safe) and wrap it in
    # the project's GymToEmbodiedWrapper (D-05 — NOT dreamerv3's built-in gym
    # adapter, which pins the old gym==0.19.0 and conflicts with
    # gymnasium>=0.29.0). The wrapper already emits image/state +
    # is_first/is_last/is_terminal dict keys that dreamerv3 1.5.0 expects.
    scene = _create_scene_for_task(task, obs_type, pixel_resolution)
    env = _create_env(scene)
    wrapped = GymToEmbodiedWrapper(env, obs_type=obs_type, pixel_resolution=pixel_resolution)

    # embodied.Counter is the global step counter (not a plain int); it
    # implements save()/load() so it can be registered on embodied.Checkpoint.
    # VERIFY: embodied.Counter exists under embodied.* in the installed 1.5.0
    # (repo-main moved it to the separate config package).
    step = embodied.Counter()

    # Build the agent config tree from the CONFIG-message dict.
    # VERIFY: embodied.Config ctor signature in the installed 1.5.0.
    agent_config = embodied.Config(**config.get("agent", {}))

    # obs_space: dict of space objects (from the wrapped env).
    obs_space = dict(wrapped.observation_space)
    # act_space: dict with 'action' (the env's Box) + 'reset' (bool space).
    # Agent.__init__ extracts act_space['action'] internally (research A4).
    # The wrapper's action_space property returns the bare env Box; the
    # embodied-protocol dict shaping lives here in _build_agent so the
    # wrapper keeps clean env-action-space semantics.
    act_space = {"action": wrapped.action_space, "reset": spaces.Discrete(2)}

    # 4-arg ctor — PyPI 1.5.0 object API (D-04). NOT the 3-arg repo-main
    # ctor and NOT the current-repo factory API.
    agent = Agent(obs_space, act_space, step, agent_config)

    # Replay buffer (VERIFY ctor + kwargs against installed 1.5.0). FIFO
    # eviction; set capacity from config, not unbounded.
    replay = embodied.replay.Replay(length=config.get("replay_length", 10_000))

    # Checkpoint registration + resume-or-init (D-09). The {task}_{obs_type}
    # scoping prevents cross-config collisions (Pitfall 6). Checkpoint
    # __setattr__ requires each registered object to implement save()/load();
    # Agent (jaxagent.py save/load), Replay, and Counter all qualify. Do NOT
    # register the env or driver. .pt compat shim is intentionally absent
    # (D-09 — .pt naming retired with the stub era).
    ckpt_dir = Path(f"models/dreamerv3/{task}_{obs_type}")
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    cp = embodied.Checkpoint(ckpt_dir / "checkpoint.ckpt")
    cp.step = step
    cp.agent = agent
    cp.replay = replay
    cp.load_or_save()  # resume if checkpoint.ckpt exists, else save initial state

    return {"agent": agent, "env": wrapped, "checkpoint": cp, "replay": replay, "step": step}


def _train_loop(agent: Any, total_steps: int, eval_every: int) -> Iterator[dict[str, Any]]:
    """Training loop yielding metrics."""
    yield {"step": 0, "loss": 0.0, "reconstruction_loss": 0.0, "reward_loss": 0.0}


def _evaluate(agent: Any, checkpoint: str, n_episodes: int) -> dict[str, Any]:
    """Run evaluation."""
    return {"reconstruction_mse": 0.0, "reward_mae": 0.0, "success_rate": 0.0}


def _save_checkpoint(agent: Any, path: str) -> None:
    """Save checkpoint."""
    pass


def _load_checkpoint(agent: Any, path: str) -> None:
    """Load checkpoint."""
    pass


class DreamerSubprocess:
    """Process-isolated JAX subprocess for DreamerV3 training."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize subprocess controller.

        Args:
            config: DreamerConfig dict with process_isolation, memory_fraction, etc.
        """
        self.config = config or {}
        self.process: multiprocessing.Process | None = None
        self._stdin: Any | None = None
        self._stdout: Any | None = None
        self._stderr: Any | None = None
        self._spawned = False

    def spawn(self) -> None:
        """Spawn the JAX subprocess."""
        if self._spawned:
            return

        # Set up multiprocessing with spawn method for clean isolation
        ctx = multiprocessing.get_context("spawn")

        # Create pipes for communication
        parent_stdin, child_stdout = ctx.Pipe()
        child_stdin, parent_stdout = ctx.Pipe()

        self._stdin = parent_stdin
        self._stdout = parent_stdout

        self.process = ctx.Process(
            target=_subprocess_main,
            args=(child_stdin, child_stdout, self.config),
            daemon=True,
        )
        self.process.start()

        # Close child ends in parent
        child_stdout.close()
        child_stdin.close()

        # Wait for subprocess to signal ready (with timeout)
        try:
            ready_msg = self._read_message()
            if ready_msg.get("type") != "READY":
                raise RuntimeError(f"Subprocess failed to start: {ready_msg}")
        except EOFError as exc:
            raise RuntimeError("Subprocess died before sending READY") from exc

        self._spawned = True

    def send_config(self, config_dict: dict[str, Any]) -> None:
        """Send CONFIG message to subprocess."""
        self._send_message({"type": "CONFIG", "config": config_dict})
        ack = self._read_message()
        if ack.get("type") != "CONFIG_ACK":
            raise RuntimeError(f"Config failed: {ack}")

    def train(self, total_steps: int, eval_every: int = 10000) -> Iterator[dict[str, Any]]:
        """Start training, yield metrics."""
        self._send_message({"type": "TRAIN", "total_steps": total_steps, "eval_every": eval_every})
        while True:
            msg = self._read_message()
            if msg.get("type") == "METRICS":
                yield msg
            elif msg.get("type") == "TRAIN_COMPLETE":
                break
            elif msg.get("type") == "ERROR":
                raise RuntimeError(f"Training error: {msg.get('error')}")

    def evaluate(self, checkpoint_path: str, n_episodes: int = 10) -> dict[str, Any]:
        """Run evaluation on checkpoint."""
        self._send_message(
            {"type": "EVAL", "checkpoint": checkpoint_path, "n_episodes": n_episodes}
        )
        result = self._read_message()
        if result.get("type") == "EVAL_RESULT":
            return result.get("metrics", {})
        raise RuntimeError(f"Evaluation failed: {result}")

    def save_checkpoint(self, path: str) -> None:
        """Save checkpoint."""
        self._send_message({"type": "CHECKPOINT", "action": "save", "path": path})
        result = self._read_message()
        if result.get("type") != "CHECKPOINT_SAVED":
            raise RuntimeError(f"Checkpoint save failed: {result}")

    def load_checkpoint(self, path: str) -> None:
        """Load checkpoint."""
        self._send_message({"type": "CHECKPOINT", "action": "load", "path": path})
        result = self._read_message()
        if result.get("type") != "CHECKPOINT_LOADED":
            raise RuntimeError(f"Checkpoint load failed: {result}")

    def shutdown(self) -> None:
        """Shutdown subprocess gracefully."""
        if not self._spawned:
            return
        try:
            self._send_message({"type": "SHUTDOWN"})
            self._read_message()  # SHUTDOWN_ACK
        except Exception:
            pass
        finally:
            if self.process and self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
                if self.process.is_alive():
                    self.process.kill()
            self._spawned = False

    def _send_message(self, msg: dict[str, Any]) -> None:
        """Send JSON message to subprocess."""
        if self._stdin:
            self._stdin.send(json.dumps(msg))

    def _read_message(self) -> dict[str, Any]:
        """Read JSON message from subprocess."""
        if self._stdout:
            line = self._stdout.recv()
            return json.loads(line)
        return {"type": "ERROR", "error": "No stdout pipe"}

    def __enter__(self) -> "DreamerSubprocess":
        self.spawn()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()
