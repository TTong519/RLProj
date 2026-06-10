"""Tests for DreamerV3 subprocess isolation and message protocol."""

import inspect
import json
import os
from unittest.mock import patch

import pytest

from surg_rl.dreamer import subprocess as dreamer_subprocess_mod
from surg_rl.dreamer.subprocess import DreamerSubprocess, _JsonStdout


class FakePipe:
    """Mock for a multiprocessing Pipe end.

    Both ends of a Pipe share the same underlying queue (multiprocessing.Pipe
    is bidirectional and both ends see the same buffer).  For our tests we
    treat send() and recv() as operating on a shared list, so we can model
    either end the same way.
    """

    def __init__(self, shared_messages=None):
        self._messages = shared_messages if shared_messages is not None else []
        self._sent = []
        self._read_idx = 0

    def send(self, obj):
        self._sent.append(obj)

    def recv(self):
        if self._read_idx >= len(self._messages):
            raise EOFError("no more messages")
        msg = self._messages[self._read_idx]
        self._read_idx += 1
        return msg

    def close(self):
        pass

    def fileno(self):
        return 0


class FakeProcess:
    """Mock for multiprocessing.Process."""

    def __init__(self):
        self._alive = True
        self.terminated = False
        self.joined = False
        self.killed = False

    def start(self):
        pass

    def is_alive(self):
        return self._alive

    def terminate(self):
        self.terminated = True
        self._alive = False

    def join(self, timeout=None):
        self.joined = True

    def kill(self):
        self.killed = True
        self._alive = False


class FakeContext:
    """Mock for multiprocessing context returned by get_context('spawn').

    The DreamerSubprocess.spawn() code calls Pipe() twice:
    - pipe 1: stores its first end as self._stdin and its second end is the
      child end the subprocess receives on.  In our mock, we use the second
      end as the channel the parent reads from to model the bidirectional
      behavior the code expects.
    - pipe 2: stores its second end as self._stdout and its first end is the
      child end.  In our mock, we use the first end as the channel the
      parent reads messages from.
    """

    def __init__(self, parent_read_messages=None, eof_after=None):
        self._parent_read_messages = parent_read_messages or []
        self._eof_after = eof_after
        self.process = FakeProcess()
        self._call_count = 0
        self._eof_count = 0

    def _make_pipe_pair(self):
        pipe_a = FakePipe()
        encoded = [json.dumps(m) for m in self._parent_read_messages]
        pipe_b = FakePipe(shared_messages=encoded)
        return pipe_a, pipe_b

    def Pipe(self):
        self._call_count += 1
        return self._make_pipe_pair()

    def Process(self, target, args, daemon):
        return self.process


def _make_ctx(messages=None):
    return FakeContext(parent_read_messages=messages or [])


class TestProcessIsolationImport:
    """Verify that importing DreamerSubprocess does not set JAX env vars."""

    def test_no_jax_mem_fraction_after_import(self):
        os.environ.pop("XLA_PYTHON_CLIENT_MEM_FRACTION", None)
        import surg_rl.dreamer.subprocess  # noqa: F401

        assert "XLA_PYTHON_CLIENT_MEM_FRACTION" not in os.environ

    def test_no_jax_or_dreamerv3_loaded_in_main_process(self):
        import sys

        sys.modules.pop("jax", None)
        sys.modules.pop("dreamerv3", None)
        import surg_rl.dreamer.subprocess  # noqa: F401

        assert "jax" not in sys.modules
        assert "dreamerv3" not in sys.modules


class TestDreamerSubprocessSpawn:
    """Test the spawn() method and ready handshake."""

    def test_spawn_sends_ready_and_marks_spawned(self):
        ctx = _make_ctx([{"type": "READY", "jax_version": "0.4.0"}])
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess({"memory_fraction": 0.3})
            proc.spawn()
            assert proc._spawned is True

    def test_spawn_raises_runtime_error_on_eof(self):
        ctx = _make_ctx([])
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            with pytest.raises(RuntimeError, match="Subprocess died"):
                proc.spawn()

    def test_spawn_raises_when_first_message_not_ready(self):
        ctx = _make_ctx([{"type": "ERROR", "error": "boom"}])
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            with pytest.raises(RuntimeError, match="Subprocess failed to start"):
                proc.spawn()

    def test_spawn_is_idempotent(self):
        ctx = _make_ctx([{"type": "READY"}])
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            proc.spawn()
            assert proc._spawned is True


class TestDreamerSubprocessConfig:
    """Test CONFIG message protocol."""

    def test_send_config_writes_json_to_stdin(self):
        ctx = _make_ctx([{"type": "READY"}, {"type": "CONFIG_ACK"}])
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            proc.send_config({"obs_type": "state", "memory_fraction": 0.4})
            assert proc._stdin is not None
            assert len(proc._stdin._sent) == 1
            sent = json.loads(proc._stdin._sent[0])
            assert sent["type"] == "CONFIG"
            assert sent["config"]["obs_type"] == "state"

    def test_send_config_raises_on_missing_ack(self):
        ctx = _make_ctx([{"type": "READY"}, {"type": "ERROR", "error": "no config"}])
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            with pytest.raises(RuntimeError, match="Config failed"):
                proc.send_config({"obs_type": "state"})


class TestDreamerSubprocessTrain:
    """Test train() yields metrics and completes."""

    def test_train_yields_metrics_until_complete(self):
        messages = [
            {"type": "READY"},
            {"type": "METRICS", "step": 0, "loss": 0.5, "reconstruction_loss": 0.1},
            {"type": "METRICS", "step": 1, "loss": 0.4, "reconstruction_loss": 0.09},
            {"type": "TRAIN_COMPLETE"},
        ]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            metrics_seen = list(proc.train(total_steps=2, eval_every=1))
            assert len(metrics_seen) == 2
            assert metrics_seen[0]["step"] == 0
            assert metrics_seen[1]["step"] == 1

    def test_train_sends_train_message(self):
        messages = [{"type": "READY"}, {"type": "TRAIN_COMPLETE"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            list(proc.train(total_steps=100, eval_every=10))
            sent = json.loads(proc._stdin._sent[0])
            assert sent["type"] == "TRAIN"
            assert sent["total_steps"] == 100
            assert sent["eval_every"] == 10

    def test_train_raises_on_error_message(self):
        messages = [{"type": "READY"}, {"type": "ERROR", "error": "agent crashed"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            with pytest.raises(RuntimeError, match="Training error"):
                list(proc.train(total_steps=10))


class TestDreamerSubprocessEvaluate:
    """Test evaluate() returns metrics dict."""

    def test_evaluate_returns_metrics_dict(self):
        eval_result = {
            "type": "EVAL_RESULT",
            "metrics": {
                "reconstruction_mse": 0.005,
                "reward_mae": 0.2,
                "success_rate": 0.7,
            },
        }
        messages = [{"type": "READY"}, eval_result]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            metrics = proc.evaluate("models/test.pt", n_episodes=5)
            assert metrics["reconstruction_mse"] == 0.005
            assert metrics["reward_mae"] == 0.2
            assert metrics["success_rate"] == 0.7

    def test_evaluate_sends_eval_message(self):
        messages = [
            {"type": "READY"},
            {"type": "EVAL_RESULT", "metrics": {"reconstruction_mse": 0.0}},
        ]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            proc.evaluate("models/test.pt", n_episodes=3)
            sent = json.loads(proc._stdin._sent[0])
            assert sent["type"] == "EVAL"
            assert sent["checkpoint"] == "models/test.pt"
            assert sent["n_episodes"] == 3

    def test_evaluate_raises_on_non_result_message(self):
        messages = [{"type": "READY"}, {"type": "ERROR", "error": "boom"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            with pytest.raises(RuntimeError, match="Evaluation failed"):
                proc.evaluate("models/test.pt")


class TestDreamerSubprocessCheckpoint:
    """Test checkpoint save/load."""

    def test_save_checkpoint_sends_save_message(self):
        messages = [{"type": "READY"}, {"type": "CHECKPOINT_SAVED", "path": "/x.pt"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            proc.save_checkpoint("/x.pt")
            sent = json.loads(proc._stdin._sent[0])
            assert sent["type"] == "CHECKPOINT"
            assert sent["action"] == "save"
            assert sent["path"] == "/x.pt"

    def test_save_checkpoint_raises_on_wrong_ack(self):
        messages = [{"type": "READY"}, {"type": "ERROR", "error": "no disk"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            with pytest.raises(RuntimeError, match="Checkpoint save failed"):
                proc.save_checkpoint("/x.pt")

    def test_load_checkpoint_sends_load_message(self):
        messages = [{"type": "READY"}, {"type": "CHECKPOINT_LOADED", "path": "/x.pt"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            proc.load_checkpoint("/x.pt")
            sent = json.loads(proc._stdin._sent[0])
            assert sent["type"] == "CHECKPOINT"
            assert sent["action"] == "load"
            assert sent["path"] == "/x.pt"

    def test_load_checkpoint_raises_on_wrong_ack(self):
        messages = [{"type": "READY"}, {"type": "CHECKPOINT_SAVED", "path": "/x.pt"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            with pytest.raises(RuntimeError, match="Checkpoint load failed"):
                proc.load_checkpoint("/x.pt")


class TestDreamerSubprocessShutdown:
    """Test shutdown behavior."""

    def test_shutdown_sends_shutdown_message(self):
        messages = [{"type": "READY"}, {"type": "SHUTDOWN_ACK"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            proc.shutdown()
            assert proc._stdin._sent[0] == json.dumps({"type": "SHUTDOWN"})

    def test_shutdown_terminates_alive_process(self):
        messages = [{"type": "READY"}, {"type": "SHUTDOWN_ACK"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            proc.shutdown()
            assert ctx.process.terminated is True
            assert ctx.process.joined is True

    def test_shutdown_skips_when_not_spawned(self):
        proc = DreamerSubprocess()
        proc.shutdown()
        assert proc._spawned is False

    def test_shutdown_swallows_pipe_errors(self):
        ctx = _make_ctx([{"type": "READY"}])
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            proc = DreamerSubprocess()
            proc.spawn()
            proc._stdin = None
            proc._stdout = FakePipe(shared_messages=[])
            proc.shutdown()
            assert ctx.process.terminated is True


class TestDreamerSubprocessContextManager:
    """Test __enter__ / __exit__."""

    def test_enter_spawns_and_exit_shuts_down(self):
        messages = [{"type": "READY"}, {"type": "SHUTDOWN_ACK"}]
        ctx = _make_ctx(messages)
        with patch("surg_rl.dreamer.subprocess.multiprocessing.get_context", return_value=ctx):
            with DreamerSubprocess() as proc:
                assert proc._spawned is True
            assert ctx.process.terminated is True


class TestSubprocessStdoutProtocol:
    """Regression tests for the stdout wrapper used inside _subprocess_main (Phase 26 D-02).

    The original code used `os.fdopen(child_stdout.fileno(), "w", ...)` to
    redirect stdout to a Pipe connection. That pattern is fragile on
    Windows and can race with the parent's recv(). The fix introduces
    `_JsonStdout`, a thin wrapper that uses the Pipe connection's send()
    method directly (no FD manipulation).

    These tests cover the wrapper in isolation; the protocol-level
    test (Test 4) additionally asserts that `_subprocess_main` actually
    wires up `_JsonStdout` (and not os.fdopen) on the stdout channel.
    """

    def test_json_stdout_write_sends_payload_to_pipe(self):
        """`.write('{"type":"READY"}\\n')` records one send with newline stripped."""
        pipe = FakePipe()
        stdout = _JsonStdout(pipe)
        n = stdout.write('{"type":"READY"}\n')
        assert n == len('{"type":"READY"}\n')
        assert pipe._sent == ['{"type":"READY"}']

    def test_json_stdout_write_handles_empty_string(self):
        """`.write("")` returns 0 and does not call send()."""
        pipe = FakePipe()
        stdout = _JsonStdout(pipe)
        assert stdout.write("") == 0
        assert pipe._sent == []

    def test_json_stdout_write_handles_lone_newline(self):
        """`.write("\\n")` returns 1 and does not call send() (newline-only is a no-op)."""
        pipe = FakePipe()
        stdout = _JsonStdout(pipe)
        assert stdout.write("\n") == 1
        assert pipe._sent == []

    def test_json_stdout_flush_is_noop(self):
        """`.flush()` does not raise and does not send (no-op for our protocol)."""
        pipe = FakePipe()
        _JsonStdout(pipe).flush()
        assert pipe._sent == []

    def test_subprocess_main_does_not_use_fdopen_for_stdout(self):
        """Source-level guard: stdout assignment must use `_JsonStdout`, not `os.fdopen` on a Pipe FD.

        The only acceptable `os.fdopen(...)` call in `_subprocess_main` is on
        file descriptor 2 (stderr) — anything else indicates the fragile
        FD-on-Pipe pattern has regressed.
        """
        src = inspect.getsource(dreamer_subprocess_mod._subprocess_main)
        # The stdout line must use _JsonStdout
        assert "_JsonStdout(child_stdout)" in src, (
            f"_subprocess_main must wire stdout through _JsonStdout:\n{src}"
        )
        # No os.fdopen on the Pipe connection (no child_stdout.fileno() call)
        assert "child_stdout.fileno()" not in src, (
            f"_subprocess_main still uses child_stdout.fileno() — fragile:\n{src}"
        )
        # Stderr may use os.fdopen(2, ...) — that's allowed
        assert "os.fdopen(2" in src, "expected stderr to use os.fdopen(2, ...)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
