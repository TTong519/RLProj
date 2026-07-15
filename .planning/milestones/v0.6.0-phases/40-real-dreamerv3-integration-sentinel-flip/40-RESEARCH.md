# Phase 40: Real DreamerV3 Integration + Sentinel Flip - Research

**Researched:** 2026-07-11
**Domain:** DreamerV3 JAX training (process-isolated subprocess), checkpoint persistence/resume, CI GPU smoke testing
**Confidence:** HIGH (upstream API verified by downloading + inspecting the actual PyPI tarball and repo source; stub code read in full)

## Summary

Phase 40 replaces 5 stub functions in `src/surg_rl/dreamer/subprocess.py` with real DreamerV3 training implementations, adds per-task/obs-type checkpoint persistence+resume, inverts the Phase 30 sentinel E2E test from a negative stub assertion to a positive real-agent assertion, and stands up a CI GPU smoke test. The subprocess protocol (`_JsonStdout`, JSON-over-stdio, `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4`) stays unchanged; all changes are inside the child-process functions.

**The single most important finding:** the `dreamerv3~=1.5.0` PyPI package (pinned in pyproject.toml, published Feb 2023) has a **DIFFERENT API** from the current `danijar/dreamerv3` GitHub repo main branch (setup.py `name='dreamer', version='3.3.1'`). The PyPI 1.5.0 API is object-based (`embodied.run.train(agent, env, replay, logger, args)`, `Agent(obs_space, act_space, step, config)` — 4 args); the current repo is factory-based (`embodied.run.train(make_agent, make_replay, make_env, make_stream, make_logger, args)`, `Agent(obs_space, act_space, config)` — 3 args, uses `elements.*` not `embodied.*`). Because the pin is `~=1.5.0`, the **PyPI 1.5.0 object-based API is the one the stubs must target.** The STATE.md blocker naming `make_agent`/`make_replay`/`make_stream`/`make_logger` factory composition describes the CURRENT repo, NOT the pinned PyPI package — this drift must be resolved during discuss-phase before planning the stub bodies.

**Primary recommendation:** Implement `_build_agent` using the PyPI 1.5.0 `Agent(obs_space, act_space, step, config)` constructor + the project's existing `GymToEmbodiedWrapper` (not dreamerv3's `FromGym`, which pins `gym==0.19.0` conflicting with `gymnasium>=0.29.0`). Use `embodied.Checkpoint` for resume (attribute registration pattern: `cp.agent=agent; cp.replay=replay; cp.step=step; cp.load_or_save()`), not a hand-rolled `agent.save(path)` call. Keep all JAX/dreamerv3 imports inside `_run_subprocess_loop` (child process only). Redirect the embodied logger to stderr.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DMV3-07 | Replace 5 stubs (`_build_agent`/`_train_loop`/`_evaluate`/`_save_checkpoint`/`_load_checkpoint`) with real dreamerv3.Agent / embodied.run.train | Upstream API findings (Section: Upstream API), stub inventory (Section: Current State of the 5 Stubs) |
| DMV3-08 | Checkpoints persist per task/obs-type under `models/dreamerv3/{task}_{obs_type}/` and resume across subprocess restarts | Checkpoint design (Section: Checkpoint Persistence + Resume Design), embodied.Checkpoint API |
| DMV3-09 | Phase 30 E2E test inverted: positive real-agent assertion + `_build_agent is None` regression guard | Sentinel inversion design (Section: Sentinel Inversion Design for DMV3-09) |
| DMV3-10 | CI GPU smoke test asserts structural properties only (finite/non-increasing loss, checkpoint exists); macOS skips per INV-8 | CI GPU smoke design (Section: CI GPU Smoke Test Design for DMV3-10) |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| DreamerV3 agent construction (`_build_agent`) | Child subprocess (JAX) | — | JAX/dreamerv3 imports MUST stay in child to preserve parent-isolation invariant (SC#5); agent is a JAX object |
| Training loop (`_train_loop`) | Child subprocess (JAX) | — | `embodied.run.train` or equivalent loop runs in child; metrics shipped via `_JsonStdout` pipe |
| Evaluation (`_evaluate`) | Child subprocess (JAX) | — | Agent policy inference requires JAX; results shipped as JSON |
| Checkpoint save/load | Child subprocess (JAX) | Disk (models/dreamerv3/) | `embodied.Checkpoint` runs in child; writes to filesystem; parent only sends CHECKPOINT messages |
| Subprocess protocol (JSON-over-stdio) | Parent process (Python) | Child subprocess | Parent `DreamerSubprocess` class manages pipe lifecycle — UNCHANGED by this phase |
| JAX isolation (XLA_PYTHON_CLIENT_MEM_FRACTION) | Child subprocess (OS env) | — | Set before first `import jax` in child — UNCHANGED |
| Sentinel test (E2E) | Test layer (pytest) | CI GPU host | `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — inverted assertions |
| CI GPU smoke test | CI layer (GitHub Actions) | GPU host runner | New CI job or Dockerfile.cuda extension |

## Current State of the 5 Stubs

All 5 stubs live in `src/surg_rl/dreamer/subprocess.py` and are called from `_run_subprocess_loop` (line 57-122). They are module-level functions (not methods) so they can be pickled for the `multiprocessing.spawn` context.

### Stub 1: `_build_agent` (line 125-129)
```python
def _build_agent(config: dict[str, Any]) -> Any:
    """Build DreamerV3 agent from config."""
    # This will be implemented when dreamerv3 is available
    # For now, return a mock that can be replaced
    return None
```
**Current behavior:** Returns `None`. Called at line 83: `agent = _build_agent(config)` during the CONFIG message handler. When `agent is None`, the TRAIN and EVAL branches emit `{"type": "ERROR", "error": "Agent not configured"}` — this is the sentinel the Phase 30 E2E test asserts.

### Stub 2: `_train_loop` (line 132-134)
```python
def _train_loop(agent: Any, total_steps: int, eval_every: int) -> Iterator[dict[str, Any]]:
    """Training loop yielding metrics."""
    yield {"step": 0, "loss": 0.0, "reconstruction_loss": 0.0, "reward_loss": 0.0}
```
**Current behavior:** Yields one dummy metrics dict then returns. Never trains.

### Stub 3: `_evaluate` (line 137-139)
```python
def _evaluate(agent: Any, checkpoint: str, n_episodes: int) -> dict[str, Any]:
    """Run evaluation."""
    return {"reconstruction_mse": 0.0, "reward_mae": 0.0, "success_rate": 0.0}
```
**Current behavior:** Returns dummy metrics. Never evaluates.

### Stub 4: `_save_checkpoint` (line 142-144)
```python
def _save_checkpoint(agent: Any, path: str) -> None:
    """Save checkpoint."""
    pass
```
**Current behavior:** No-op. The CHECKPOINT message handler at line 108-110 sends `CHECKPOINT_SAVED` regardless.

### Stub 5: `_load_checkpoint` (line 147-149)
```python
def _load_checkpoint(agent: Any, path: str) -> None:
    """Load checkpoint."""
    pass
```
**Current behavior:** No-op. The CHECKPOINT message handler at line 111-113 sends `CHECKPOINT_LOADED` regardless.

## The Unchanged Contract (SC#1 — what must NOT change)

These are the load-bearing invariants the stub-replacement must preserve. They are explicitly called out in SC#1 and SC#5.

### 1. `_JsonStdout` wrapper (subprocess.py:30-53)
```python
class _JsonStdout:
    def __init__(self, pipe: Any) -> None:
        self._pipe = pipe
    def write(self, s: str) -> int:
        if not s: return 0
        if s == "\n": return 1
        payload = s.rstrip("\n")
        self._pipe.send(payload)
        return len(s)
    def flush(self) -> None:
        pass
```
**Why it must not change:** Every `print(..., flush=True)` in the subprocess becomes a `pipe.send()` call. If this is reverted to `os.fdopen`, the parent's `recv()` races with the child's writes (Phase 26 fix #1). The `_JsonStdout` wrapper is the foundation of the JSON-over-stdio pipe.

### 2. JSON-over-stdio subprocess protocol (subprocess.py:57-122)
The message types and their handlers:
- `READY` (child→parent): `{"type": "READY", "jax_version": ...}` — sent after `import jax`
- `CONFIG` / `CONFIG_ACK` (parent→child / child→parent): builds agent
- `TRAIN` / `METRICS` / `TRAIN_COMPLETE` (parent→child / child→parent): training loop yields metrics
- `EVAL` / `EVAL_RESULT` (parent→child / child→parent): evaluation
- `CHECKPOINT` / `CHECKPOINT_SAVED` / `CHECKPOINT_LOADED` (bidirectional): save/load
- `SHUTDOWN` / `SHUTDOWN_ACK` (bidirectional): graceful shutdown

**Why it must not change:** The parent `DreamerSubprocess` class (line 152-282) reads these messages via `_read_message()` / `_send_message()`. The protocol is the parent-child contract. SC#1 says it is unchanged.

### 3. `XLA_PYTHON_CLIENT_MEM_FRACTION=0.4` isolation (subprocess.py:19-20)
```python
memory_fraction = float(config.get("memory_fraction", 0.4))
os.environ["XLA_PYTHON_CLIENT_MEM_FRACTION"] = str(memory_fraction)
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
```
Set inside `_subprocess_main` (line 16) BEFORE `import jax` (which happens at line 60 inside `_run_subprocess_loop`). This prevents JAX from preallocating 75% of GPU memory, which would conflict with PyTorch in the parent process. `[VERIFIED: docs.jax.dev/en/latest/gpu_memory_allocation.html]` — `XLA_PYTHON_CLIENT_MEM_FRACTION=.XX` makes JAX preallocate XX% instead of default 75%.

### 4. JAX isolation boundary (SC#5)
`import jax` happens ONLY at `subprocess.py:60` inside `_run_subprocess_loop`, which runs in the child process. The parent `DreamerSubprocess` class (line 152-282) never imports jax or dreamerv3. The `__init__.py` uses `LazyImport("dreamerv3", "dreamer")` so parent-package imports don't pull jax. **This must be preserved** — no `import jax` or `import dreamerv3` may appear in any module imported by the parent process.

## Upstream API Findings

### KEY FINDING: PyPI 1.5.0 vs Current Repo — API Drift

The `dreamerv3~=1.5.0` pin in pyproject.toml resolves to PyPI `dreamerv3==1.5.0` (published 2023-02-22). This package has a **DIFFERENT API** from the current `danijar/dreamerv3` GitHub repo main branch. I verified this by downloading the actual PyPI tarball (`pip download dreamerv3==1.5.0`), extracting it, and reading the source code directly.

| Aspect | PyPI dreamerv3==1.5.0 (PINNED — applies) | Current repo main (setup.py `name='dreamer' v3.3.1` — NOT pinned) |
|--------|------------------------------------------|------------------------------------------------------------------|
| Train entry point | `embodied.run.train(agent, env, replay, logger, args)` — objects | `embodied.run.train(make_agent, make_replay, make_env, make_stream, make_logger, args)` — factory functions |
| Agent constructor | `Agent(obs_space, act_space, step, config)` — 4 args | `Agent(obs_space, act_space, config)` — 3 args |
| Config/Flags/Path | `embodied.Flags`, `embodied.Config`, `embodied.Path` | `elements.Flags`, `elements.Config`, `elements.Path` (separate `elements` package) |
| `embodied` location | Vendored inside `dreamerv3/embodied/` | Still vendored but uses `elements` for config |
| Gym dependency | `gym==0.19.0` (old gym) | `gym` via `gymnasium`-compatible wrappers |
| Extra deps | `jax`, `jaxlib`, `optax`, `rich`, `ruamel.yaml`, `tensorflow-cpu`, `tensorflow_probability` | `jax[cuda12]==0.4.33`, `elements>=3.19.1`, `portal>=3.5.0`, `ninjax>=3.5.1`, `numpy<2` |
| Entry script | `dreamerv3/train.py` (module-level `main()`) | `dreamerv3/main.py` (module-level `main()`) |
| `example.py` | Referenced in PyPI description but 404 on repo (confirmed) | Does not exist |

`[VERIFIED: pip download dreamerv3==1.5.0 + tarball inspection + raw.githubusercontent.com source fetch]`

**Implication for the stubs:** The STATE.md blocker names `make_agent`/`make_replay`/`make_stream`/`make_logger` factory composition + `encoder.mlp_keys`/`cnn_keys` — these are the CURRENT REPO API, NOT the pinned PyPI 1.5.0 API. The stubs must target the **PyPI 1.5.0 object-based API** because that is what `pip install '.[dreamer]'` installs. This is the #1 open question for discuss-phase (see Open Questions Q1).

### PyPI 1.5.0 `embodied.run.train` signature
`[VERIFIED: dreamerv3-1.5.0/dreamerv3/embodied/run/train.py line 6]`
```python
def train(agent, env, replay, logger, args):
    # agent: Agent instance (already constructed)
    # env: embodied.Env (already wrapped)
    # replay: embodied.replay.Replay
    # logger: embodied.Logger
    # args: embodied.Config with logdir, batch_steps, train_ratio, etc.
```
This takes OBJECTS, not factory functions. The stub `_train_loop` should construct agent+env+replay+logger inside the child and call `embodied.run.train(...)` — OR replicate the loop manually if the full `embodied.run.train` is too heavyweight for the subprocess protocol (it manages its own checkpointing internally).

### PyPI 1.5.0 `Agent` constructor
`[VERIFIED: dreamerv3-1.5.0/dreamerv3/agent.py]`
```python
class Agent(nj.Module):
    def __init__(self, obs_space, act_space, step, config):
        # obs_space: dict of space objects (from wrapped env)
        # act_space: dict with 'action' key + 'reset' key
        # step: embodied.Counter() — the global step counter
        # config: embodied.Config (the full config tree)
        self.config = config
        self.obs_space = obs_space
        self.act_space = act_space['action']  # NOTE: extracts 'action' key
        self.step = step
        self.wm = WorldModel(obs_space, act_space, config, name='wm')
        self.task_behavior = getattr(behaviors, config.task_behavior)(...)
```
The `step` arg is a `embodied.Counter()` (not an int). The `act_space` is expected to have an `'action'` key (extracted via `act_space['action']`). The existing `GymToEmbodiedWrapper.action_space` returns a `spaces.Box` — it needs to return a dict `{"action": box, "reset": bool}` to match the embodied protocol.

### PyPI 1.5.0 Checkpoint API
`[VERIFIED: dreamerv3-1.5.0/dreamerv3/embodied/core/checkpoint.py + embodied/run/train.py:94-102]`
```python
checkpoint = embodied.Checkpoint(logdir / 'checkpoint.ckpt')
checkpoint.step = step        # embodied.Counter
checkpoint.agent = agent      # Agent (must have .save() and .load())
checkpoint.replay = replay    # Replay buffer (must have .save() and .load())
if args.from_checkpoint:
    checkpoint.load(args.from_checkpoint)
checkpoint.load_or_save()  # loads if exists, saves if new
# ... later in loop:
if should_save(step):
    checkpoint.save()
```

**Critical constraint:** `Checkpoint.__setattr__` (line 24-33) raises `ValueError` if the assigned object does NOT implement both `save()` and `load()` methods. The Agent and Replay both implement these. The stubs `_save_checkpoint(agent, path)` / `_load_checkpoint(agent, path)` do NOT match this pattern — upstream uses `Checkpoint` wrapping agent+replay+step, not standalone `agent.save(path)`.

**Agent.save/load:** `[VERIFIED: dreamerv3-1.5.0/dreamerv3/jaxagent.py:101-120]`
```python
def save(self):
    varibs = jax.device_get(self.varibs)
    return tree_map(np.asarray, varibs)  # returns numpy dict

def load(self, state):
    self.varibs = jax.device_put(state, self.train_devices[0])
    self.sync()
```

### PyPI 1.5.0 `FromGym` wrapper (gym vs gymnasium conflict)
`[VERIFIED: dreamerv3-1.5.0/dreamerv3/embodied/envs/from_gym.py]`
```python
import gym  # OLD gym, NOT gymnasium
class FromGym(embodied.Env):
    def __init__(self, env, obs_key='image', act_key='action', **kwargs):
        if isinstance(env, str):
            self._env = gym.make(env, **kwargs)
        else:
            self._env = env  # can pass an existing env instance
```
The `FromGym` wrapper accepts a pre-constructed env instance (not just a string id). BUT it imports `gym` (old gym), and the PyPI 1.5.0 requirements pin `gym==0.19.0`. The project uses `gymnasium>=0.29.0`. **Resolution: use the project's existing `GymToEmbodiedWrapper` (wrapper.py) instead of `FromGym`** — it already implements the embodied.Env protocol (`is_first`/`is_last`/`is_terminal`, reset-in-action) against a Gymnasium `SurgicalEnv`. This avoids the gym-vs-gymnasium version conflict entirely.

### JAX subprocess isolation + stdout capture
`[CITED: docs.jax.dev/en/latest/gpu_memory_allocation.html]`
- `XLA_PYTHON_CLIENT_MEM_FRACTION=.4` → JAX preallocates 40% (not default 75%). Correct for subprocess co-existing with PyTorch parent.
- `XLA_PYTHON_CLIENT_PREALLOCATE=false` (already set) → disables preallocation; allocates on demand (more fragmentation, lower footprint).
- The env var MUST be set before the first `import jax`. The existing code sets it at `subprocess.py:19-20` inside `_subprocess_main` before `_run_subprocess_loop` (which does `import jax` at line 60). This ordering is correct and MUST be preserved.

**Logger-to-stderr concern (SC#5):** The embodied logger (`embodied.Logger` with `TerminalOutput`) writes to stdout by default. Since `_JsonStdout` replaces `sys.stdout` (subprocess.py:23), any `print()` inside the child goes through the JSON pipe. BUT the embodied logger may bypass `sys.stdout` (e.g. via `sys.__stdout__` or direct fd writes). The stub replacement must explicitly configure the logger to write to stderr (`sys.stderr`), OR suppress TerminalOutput entirely and rely on JSONL file output + the METRICS messages shipped via the pipe. `[ASSUMED]` — the exact logger redirection mechanism needs verification during implementation (the PyPI 1.5.0 `embodied.Logger` API would need inspection of `embodied/core/logger.py`).

## Standard Stack

### Core (already pinned in pyproject.toml — no new deps)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dreamerv3 | ~=1.5.0 | DreamerV3 agent + embodied library (vendored) | The only PyPI-published DreamerV3; pinned in pyproject `[dreamer]` extra |
| jax | ~=0.4.20 | JAX array computing + autodiff | Pinned in pyproject; must be installed with CUDA support on GPU host |
| jaxlib | (transitive) | JAX XLA backend | Required for GPU; installed alongside jax[cuda] |
| optax | >=0.1.7 | Gradient processing + optimizers | DreamerV3 dependency; pinned in pyproject |
| gymnasium | >=0.29.0 | SurgicalEnv base | Already a core dep; GymToEmbodiedWrapper adapts it |

### Supporting (vendored inside dreamerv3 1.5.0 — no separate install)
| Library | Location | Purpose | When to Use |
|---------|----------|---------|-------------|
| embodied | dreamerv3/embodied/ | Env protocol, Checkpoint, Driver, Replay, Logger, Config, Flags, Path | The entire training infrastructure — train loop, checkpoint, env wrapping |
| ninjax | (dreamerv3 dep) | JAX module system (nj.Module base class) | Agent extends nj.Module; required for variable management |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyPI dreamerv3 1.5.0 (object API) | Current repo main (factory API, `name='dreamer'`) | Would require changing the pyproject pin to a git install; newer API but unpinned on PyPI; breaks the `~=1.5.0` version constraint. NOT recommended — stay on the pinned PyPI package. |
| dreamerv3's `FromGym` wrapper | Project's `GymToEmbodiedWrapper` | `FromGym` imports `gym==0.19.0` (conflicts with `gymnasium>=0.29.0`); the project wrapper already implements the embodied.Env protocol against Gymnasium. Use the project wrapper. |
| `embodied.run.train` (full loop) | Manual loop inside `_train_loop` | `embodied.run.train` manages its own checkpointing + logging internally, which may conflict with the subprocess's CHECKPOINT message protocol. A manual loop (driver + agent.train + periodic cp.save) gives more control over the JSON pipe. Discuss-phase should decide. |

**Installation (already declared — no pyproject changes needed):**
```bash
pip install -e ".[dreamer]"  # installs dreamerv3~=1.5.0, jax~=0.4.20, optax>=0.1.7
# On GPU host: install jax with CUDA separately first:
pip install "jax[cuda12]==0.4.20"  # or the ~=0.4.20 compatible version
```

**Version verification:**
```bash
pip show dreamerv3    # 1.5.0 (verified via pip download)
pip show jax         # ~=0.4.20 (pyproject pin; installed 0.10.2 on THIS macOS dev box — NOT the pin)
pip show optax       # >=0.1.7
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| dreamerv3 | PyPI | 3+ yrs (Feb 2023) | unknown (niche) | github.com/danijar/dreamerv3 (3469 stars) | SUS (unknown-downloads) | Approved — niche ML package, verified via tarball inspection + GitHub repo |
| jax | PyPI | ongoing | unknown | github.com/jax-ml/jax | SUS (too-new on latest) | Approved — Google JAX team; pin `~=0.4.20` targets stable line |
| optax | PyPI | ongoing | unknown | (DeepMind) | SUS (no-repository) | Approved — standard JAX optimizer lib |
| elements | PyPI | recent | unknown | github.com/danijar/elements | SUS (unknown-downloads) | NOT needed for PyPI 1.5.0 (uses embodied.*, not elements.*); only needed for current-repo API |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious [SUS]:** dreamerv3, jax, optax — all SUS due to "unknown-downloads" (PyPI doesn't expose download counts via this check). All are well-known niche ML packages from verified authors (Danijar Hafner for dreamerv3/elements, Google JAX team for jax/optax). The dreamerv3 package was verified by downloading and inspecting the actual tarball. No `checkpoint:human-verify` needed — these are the established dreamerv3 ecosystem packages, already pinned in pyproject.toml since Phase 24.

*Note: The `elements` package is only needed if switching to the current-repo factory API (Open Question Q1). If the project stays on PyPI 1.5.0 (recommended), `elements` is NOT installed.*

## Architecture Patterns

### System Architecture Diagram

```
PARENT PROCESS (no JAX)                    CHILD SUBPROCESS (JAX + dreamerv3)
================================           ============================================
                                           
  run_dreamer_training()                    _subprocess_main()
    │                                         ├─ os.environ[XLA_PYTHON_CLIENT_MEM_FRACTION=0.4]
    ├─ DreamerSubprocess(config)              ├─ os.environ[XLA_PYTHON_CLIENT_PREALLOCATE=false]
    │    ├─ spawn()  ──────────────────►      ├─ sys.stdout = _JsonStdout(pipe)  [SC#1 unchanged]
    │    │      (multiprocessing.spawn)       ├─ sys.stderr = fdopen(2)           [logger→stderr, SC#5]
    │    │                                   │
    │    ├─ send_config(config_dict) ──►      └─ _run_subprocess_loop(stdin_pipe)
    │    │◄── CONFIG_ACK                     │     ├─ import jax               [child-only, SC#5]
    │    │                                   │     ├─ send READY
    │    ├─ train(steps) ──────────►         │     │
    │    │◄── METRICS (per step) ◄───        │     ├─ CONFIG → _build_agent(config)  [STUB→REAL]
    │    │◄── TRAIN_COMPLETE ◄──────         │     │     ├─ construct SurgicalEnv + GymToEmbodiedWrapper
    │    │                                   │     │     ├─ Agent(obs_space, act_space, step, config)
    │    ├─ evaluate(ckpt) ─────────►        │     │     └─ embodied.Checkpoint(ckpt_dir)
    │    │◄── EVAL_RESULT ◄──────────        │     │           cp.agent=agent; cp.replay=replay; cp.step=step
    │    │                                   │     │           cp.load_or_save()  [DMV3-08 resume]
    │    ├─ save_checkpoint(path) ───►        │     │
    │    │◄── CHECKPOINT_SAVED ◄─────         │     ├─ TRAIN → _train_loop(agent, steps, eval_every)  [STUB→REAL]
    │    │                                   │     │     ├─ embodied.Driver(env) + agent.train batches
    │    ├─ load_checkpoint(path) ───►        │     │     ├─ yield METRICS via _JsonStdout pipe
    │    │◄── CHECKPOINT_LOADED ◄────         │     │     └─ cp.save() periodically  [DMV3-08 persist]
    │    │                                   │     │
    │    └─ shutdown() ──────────────►        │     ├─ EVAL → _evaluate(agent, ckpt, n_eps)  [STUB→REAL]
    │       ◄── SHUTDOWN_ACK ────────         │     │     └─ agent.policy rollouts → metrics
    │                                        │     │
                                            │     ├─ CHECKPOINT save → cp.save()  [STUB→REAL]
                                            │     ├─ CHECKPOINT load → cp.load()   [STUB→REAL]
                                            │     └─ SHUTDOWN → agent.close()
                                            │
  models/dreamerv3/{task}_{obs_type}/        models/dreamerv3/{task}_{obs_type}/
    ├─ checkpoint.ckpt  ◄── written by child (embodied.Checkpoint)
    ├─ final.pt
    └─ training_metrics.json
```

### Recommended Project Structure (unchanged — this phase modifies in place)
```
src/surg_rl/dreamer/
├── __init__.py       # LazyImport guards — UNCHANGED (JAX isolation)
├── spike.py          # Feasibility spike — UNCHANGED (DMV3-01 spike, not in scope)
├── subprocess.py     # 5 stubs replaced HERE; _JsonStdout + protocol UNCHANGED
├── training.py       # run_dreamer_training() — minor: checkpoint path scoping (DMV3-08)
└── wrapper.py        # GymToEmbodiedWrapper — minor: act_space dict shape fix

tests/dreamer/
└── test_dreamerv3_subprocess_e2e.py  # SENTINEL FLIPPED HERE (DMV3-09)
```

### Pattern 1: Stub-replacement inside the child subprocess
**What:** Replace the body of each stub function with a real implementation using the PyPI 1.5.0 `embodied` API, keeping the function signature (so the callers in `_run_subprocess_loop` don't change).
**When to use:** All 5 stubs.
**Example (illustrative — actual implementation decided at plan time):**
```python
# Source: dreamerv3-1.5.0/dreamerv3/embodied/run/train.py + agent.py [VERIFIED via tarball]
def _build_agent(config: dict[str, Any]) -> Any:
    """Build DreamerV3 agent from config — REAL implementation."""
    import embodied  # vendored inside dreamerv3 1.5.0
    from dreamerv3.agent import Agent
    # Construct env inside child (JAX-safe)
    from surg_rl.dreamer.wrapper import GymToEmbodiedWrapper
    from surg_rl.dreamer.training import _create_scene_for_task, _create_env
    scene = _create_scene_for_task(config["task"], config["obs_type"], tuple(config["pixel_resolution"]))
    env = _create_env(scene)
    wrapped = GymToEmbodiedWrapper(env, obs_type=config["obs_type"], pixel_resolution=tuple(config["pixel_resolution"]))
    step = embodied.Counter()
    agent_config = embodied.Config(...)  # from config dict
    agent = Agent(wrapped.obs_space, wrapped.act_space, step, agent_config)
    # Checkpoint for resume (DMV3-08)
    ckpt_dir = Path(f"models/dreamerv3/{config['task']}_{config['obs_type']}")
    cp = embodied.Checkpoint(ckpt_dir / "checkpoint.ckpt")
    cp.step = step
    cp.agent = agent
    # replay attached when available
    cp.load_or_save()  # resume if exists, save if new
    return {"agent": agent, "env": wrapped, "checkpoint": cp, "step": step}
```

### Pattern 2: Checkpoint resume via embodied.Checkpoint
**What:** Use `embodied.Checkpoint.load_or_save()` at agent construction time to auto-resume.
**When to use:** DMV3-08 (restart-then-continue).
**Key insight:** The `--logdir` directory IS the resume key. Running the same command again with the same logdir auto-resumes. The `cp.load_or_save()` call checks for an existing checkpoint at `ckpt_dir/checkpoint.ckpt` and loads it if present.

### Pattern 3: Logger-to-stderr redirection
**What:** Configure the embodied logger to write to `sys.stderr`, not `sys.stdout`.
**When to use:** SC#5 (stdout stays clean for JSON pipe).
**Why:** `_JsonStdout` replaces `sys.stdout` with a pipe sender. If the embodied logger writes to stdout (via `print` or `sys.__stdout__`), it corrupts the JSON pipe. The logger must be configured with `TerminalOutput(sys.stderr)` or suppressed (JSONL file output only).

### Anti-Patterns to Avoid
- **Importing jax/dreamerv3 in the parent process:** SC#5 violation. All JAX imports must stay inside `_run_subprocess_loop` or functions called from it. The `__init__.py` `LazyImport` guard must be preserved.
- **Using `agent.save(path)` directly instead of `embodied.Checkpoint`:** The upstream API uses `Checkpoint` wrapping agent+replay+step with `load_or_save()`. Calling `agent.save()` directly returns a numpy dict but doesn't persist to disk — `Checkpoint._save()` is what writes. The stubs `_save_checkpoint`/`_load_checkpoint` should delegate to `cp.save()`/`cp.load()`, not call agent methods directly.
- **Reintroducing the v0.4.0 spike's `MSE<0.01` convergence thresholds in CI:** DMV3-10 explicitly says structural properties only. The spike's `DEFAULT_THRESHOLDS = {"reconstruction_mse": 0.01, "reward_mae": 0.5}` in `spike.py:16-18` is the OUT-OF-SCOPE convergence bar. CI smoke must assert finite/non-increasing loss, NOT a threshold.
- **Changing the subprocess protocol message types:** SC#1 says the protocol is unchanged. The parent `DreamerSubprocess` class must not be modified.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Training loop | Manual step loop + gradient updates | `embodied.run.train` or `embodied.Driver` + `agent.train()` | DreamerV3's training loop has RSSM world-model updates, policy/behavior heads, replay batching, and consecutive-sequence sampling — reimplementing these is thousands of lines |
| Checkpoint save/load | `pickle.dump(agent.state)` / custom format | `embodied.Checkpoint` with attribute registration | Handles JAX device_get/put, tree_map, async save via ThreadPoolExecutor, and the load_or_save resume pattern |
| Replay buffer | List of transitions | `embodied.replay.Replay` | Capacity management, prioritized/uniform sampling, chunk-based consecutive sampling for DreamerV3's sequence model |
| Env protocol adaptation | Manual obs/action dict shaping | `GymToEmbodiedWrapper` (already exists) | Already implements is_first/is_last/is_terminal + reset-in-action against Gymnasium SurgicalEnv |
| Config parsing | Manual dict → config object | `embodied.Config` / `embodied.Flags` | DreamerV3's config tree is nested YAML with CLI override support; manual parsing misses defaults |

**Key insight:** The `embodied` library (vendored inside dreamerv3 1.5.0) provides the entire training infrastructure. The stubs should be thin adapters that construct embodied objects and delegate to `embodied.run.train` or a manual `Driver`+`agent.train()` loop — NOT reimplementations of the training algorithm.

## Common Pitfalls

### Pitfall 1: API version drift (PyPI 1.5.0 vs current repo)
**What goes wrong:** Implementing stubs against the current repo's factory-based API (`make_agent`/`make_replay`/`make_stream`/`make_logger`) when the installed package is PyPI 1.5.0 (object-based API).
**Why it happens:** The STATE.md blocker names the factory composition from DeepWiki/current-repo research; the pyproject pin is `~=1.5.0` which installs the older object-based API.
**How to avoid:** Target the PyPI 1.5.0 API (`embodied.run.train(agent, env, replay, logger, args)`, `Agent(obs_space, act_space, step, config)`). Verify against the installed package, not the repo main branch.
**Warning signs:** `ImportError: cannot import name 'make_agent'` or `TypeError: Agent.__init__() takes 3 positional arguments but 4 were given`.

### Pitfall 2: gym vs gymnasium version conflict
**What goes wrong:** dreamerv3 1.5.0 pins `gym==0.19.0` in its requirements; the project uses `gymnasium>=0.29.0`. Installing both causes namespace conflicts.
**Why it happens:** dreamerv3's `FromGym` imports `gym` (old API); gymnasium is a fork with a different import path.
**How to avoid:** Use the project's `GymToEmbodiedWrapper` (which imports `gymnasium`) instead of dreamerv3's `FromGym`. The wrapper already implements the `embodied.Env` protocol. Do NOT import `from_gym` from dreamerv3.
**Warning signs:** `ImportError: cannot import name 'gym'` or `pip resolver conflict between gym==0.19.0 and gymnasium>=0.29.0`.

### Pitfall 3: JAX leaking into parent process
**What goes wrong:** `import jax` or `import dreamerv3` in a module imported by the parent process loads JAX in the parent, allocating GPU memory and violating SC#5.
**Why it happens:** The stubs are in `subprocess.py` which is imported by the parent (for the `DreamerSubprocess` class). If the stub bodies have a top-level `import jax`, the parent process imports JAX at import time.
**How to avoid:** All JAX/dreamerv3 imports must be INSIDE the stub function bodies (deferred to call-time, which happens in the child process only). The `__init__.py` `LazyImport` guard must be preserved. The existing code already does this correctly (`import jax` is inside `_run_subprocess_loop` at line 60).
**Warning signs:** `pytest tests/ -m "not integration"` takes 30+ seconds to collect (JAX import overhead); parent process shows GPU memory allocation.

### Pitfall 4: Logger corrupting the JSON pipe
**What goes wrong:** The embodied logger writes training metrics to stdout, which goes through `_JsonStdout` and corrupts the JSON pipe with non-JSON lines.
**Why it happens:** `_JsonStdout.write()` calls `pipe.send(payload)` for every `print()`. If the logger calls `print("loss=0.5")`, the parent receives a non-JSON string and `json.loads()` fails.
**How to avoid:** Configure the embodied logger to write to `sys.stderr` (which is `fdopen(2)`, a real fd) NOT `sys.stdout`. Or suppress TerminalOutput entirely and use JSONL file output.
**Warning signs:** `json.JSONDecodeError` in the parent's `_read_message()`; intermittent protocol corruption.

### Pitfall 5: Checkpoint path scoping per task/obs-type
**What goes wrong:** Checkpoints from different tasks/obs-types overwrite each other because the checkpoint directory is shared.
**Why it happens:** The existing `_find_latest_checkpoint` (training.py:183-196) uses `models/dreamerv3/{task}_{obs_type}/` — but the stubs receive a `path` arg, not a `{task}_{obs_type}` key. If the stubs use a hardcoded path, different runs collide.
**How to avoid:** The checkpoint directory MUST be derived from `{task}_{obs_type}` and passed through the CONFIG message. The `embodied.Checkpoint` should be initialized with `models/dreamerv3/{task}_{obs_type}/checkpoint.ckpt`.
**Warning signs:** Resume loads wrong agent weights; eval metrics from task A appear in task B's checkpoint.

### Pitfall 6: macOS-skip gap (100%-skipped milestone audit failure)
**What goes wrong:** The DMV3-10 smoke test skips on every CI runner (no GPU host configured), so the requirement appears "untested" in the milestone audit.
**Why it happens:** The existing CI (ci.yml) has NO GPU job. The Dockerfile.cuda does NOT install the `[dreamer]` extra. If no GPU runner is provisioned, all dreamer tests skip.
**How to avoid:** Add a CI job (or extend Dockerfile.cuda) that installs `jax[cuda12]` + `[dreamer]` and runs the smoke test on a GPU runner. The STATE.md blocker explicitly calls this out: "must run the GPU-skipif tests, else milestone audit fails on 100%-skipped."
**Warning signs:** Milestone audit reports DMV3-10 as "skipped on all runners"; no GPU job in ci.yml.

## Checkpoint Persistence + Resume Design (DMV3-08)

### Path scheme
```
models/dreamerv3/{task}_{obs_type}/
  ├─ checkpoint.ckpt          # embodied.Checkpoint binary (agent + replay + step)
  ├─ final.pt                 # (optional) final-state convenience copy
  └─ training_metrics.json    # metrics log (already written by training.py:345)
```
The `{task}_{obs_type}` pattern is already used by `_find_latest_checkpoint` (training.py:183-196) and `run_dreamer_training` (training.py:235). The `embodied.Checkpoint` constructor takes a path: `embodied.Checkpoint(Path(f"models/dreamerv3/{task}_{obs_type}") / "checkpoint.ckpt")`.

### Resume mechanism
1. At subprocess CONFIG time, `_build_agent` constructs the `embodied.Checkpoint` pointing at `{task}_{obs_type}/checkpoint.ckpt`.
2. `cp.load_or_save()` is called: if the checkpoint file exists, it loads agent weights + replay buffer + step counter; if not, it saves the initial state.
3. Training continues from the loaded step counter.
4. Periodically (via `embodied.when.Clock(args.save_every)` or the existing `step % eval_every == 0` branch in training.py), `cp.save()` persists the current state.

### Restart-then-continue test (DMV3-08 verification)
**Test seam:** `tests/dreamer/test_dreamerv3_checkpoint_resume.py` (new) or extended in `test_dreamerv3_subprocess_e2e.py`.
**Test design:**
1. Run `run_dreamer_training(task="suturing", obs_type="state", total_steps=500, eval_every=250, checkpoint_dir=tmp_path/"run1")` — completes, writes checkpoint.
2. Assert `(tmp_path/"run1"/"checkpoint.ckpt").exists()`.
3. Run `run_dreamer_training(task="suturing", obs_type="state", total_steps=1000, eval_every=250, resume=True, checkpoint_dir=tmp_path/"run1")` — resumes from step 500.
4. Assert the step counter starts at ~500 (not 0), and training completes to step 1000.
5. Assert the final metrics log shows steps 500→1000 (not 0→1000).

This test is GPU-gated (same skipif as the existing E2E test).

## Sentinel Inversion Design (DMV3-09)

### The exact test to flip
`tests/dreamer/test_dreamerv3_subprocess_e2e.py` — class `TestDreamerV3SubprocessE2E`:

| Test method | Current (negative stub) assertion | New (positive real-agent) assertion |
|-------------|----------------------------------|-------------------------------------|
| `test_e2e_run_dreamer_training_against_stub` (line 61-79) | `pytest.raises(RuntimeError, match="Agent not configured")` | `metrics = run_dreamer_training(...)` succeeds; `assert metrics is not None`; `assert "training_curves" in metrics`; rename to `test_e2e_run_dreamer_training_real_agent` |
| `test_e2e_checkpoint_files_not_written_in_stub_state` (line 81-104) | `assert not (ckpt_dir/"final.pt").exists()` | `assert (ckpt_dir/"final.pt").exists()` OR `assert (ckpt_dir/"checkpoint.ckpt").exists()`; rename to `test_e2e_checkpoint_files_written` |
| `test_e2e_dreamer_color_constant` (line 55-59) | `assert DREAMER_COLOR == "#FF8C00"` | UNCHANGED (constant is independent of stub state) |

### The `_build_agent is None` regression guard (new test)
Add a new test method to the same class:
```python
def test_e2e_build_agent_regression_guard(self) -> None:
    """DMV3-09: _build_agent must NEVER return None again (stub regression guard)."""
    import inspect
    from surg_rl.dreamer.subprocess import _build_agent
    source = inspect.getsource(_build_agent)
    # The stub returned None; the real implementation must not.
    assert "return None" not in source, (
        "_build_agent returns None — stub regression! "
        "The real implementation must return an agent object."
    )
```
This test runs WITHOUT the GPU skipif (it's a source-inspection test, not a runtime test) — it guards against stub regression on ALL runners including macOS. `[ASSUMED]` — exact guard form (source inspection vs. call-and-assert) is a discuss-phase decision.

### The module-level skipif
The existing `pytestmark = pytest.mark.skipif(...)` gate (line 42-49) stays — the runtime tests (training, checkpoint) still require GPU + dreamerv3 + jax. The regression guard test should be in a SEPARATE module or class WITHOUT the skipif so it runs on macOS too.

## CI GPU Smoke Test Design (DMV3-10)

### Structural-only assertions (NOT convergence)
| Property | Assertion | Why structural |
|----------|-----------|----------------|
| Loss is finite | `assert math.isfinite(loss)` and `not math.isnan(loss)` | NaN/inf loss = training broken; doesn't require convergence |
| Loss is non-increasing (or non-explosive) | `assert last_loss <= first_loss * tolerance` (e.g. 2×) | Explosive loss = training broken; doesn't require convergence to a threshold |
| Checkpoint file exists | `assert (ckpt_dir / "checkpoint.ckpt").exists()` | Persistence works; doesn't require a good model |
| Training completes | `run_dreamer_training(...)` returns without RuntimeError | End-to-end path works; doesn't require a good model |
| METRICS messages received | At least N metric dicts yielded | Pipe protocol stable; doesn't require a good model |

### Step/episode budget
- **Steps:** 500–1000 (same as Phase 30's D-STEPS-01 `total_steps=1000`). This is well below the 100K production training and the 100K spike budget. At 1000 steps, the `_JsonStdout` pipe round-trips ~100 metric messages.
- **CI runtime estimate:** 3–5 min on a GPU runner (per Phase 30 D-STEPS-01).
- **Do NOT assert `reconstruction_mse < 0.01`** — this is the v0.4.0 spike convergence threshold (spike.py:17) that DMV3-10 explicitly excludes.

### macOS-skip via INV-8
The existing module-level `pytestmark = pytest.mark.skipif(...)` (line 42-49) gates on GPU + dreamerv3 + jax. macOS has no GPU (for JAX CUDA) → skips cleanly. The skip message includes `pip install '.[dreamer]'` remediation. This pattern is preserved.

### CI job provisioning gap
**Current state:** `ci.yml` has NO GPU job. The `test` job runs on `ubuntu-latest` / `macos-latest` (CPU only). The `docker-ci` job builds Docker images but doesn't run tests. The `k8s-e2e` job is CPU-only.
**Dockerfile.cuda:** Installs `[dev,tracking]` but NOT `[dreamer]`. Does not install jax with CUDA.
**What's needed (discuss-phase decision):**
1. A new CI job `dreamer-gpu` that runs on a GPU runner (`runs-on: ubuntu-latest-4-core-gpu` or similar GitHub Actions GPU runner), installs `jax[cuda12]~=0.4.20` + `pip install -e ".[dev,dreamer]"`, and runs `pytest tests/dreamer/ -v`.
2. OR extend Dockerfile.cuda to install `[dreamer]` + jax[cuda12] and run the smoke test inside the container on a GPU runner.

`[ASSUMED]` — the exact CI GPU host provisioning strategy (GitHub Actions GPU runner vs self-hosted vs Docker) is an ops decision for discuss-phase. The STATE.md blocker calls this out explicitly.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0.0 (already installed) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` (testpaths=tests, asyncio_mode=auto) |
| Quick run command | `PYTHONPATH=src pytest tests/dreamer/ -v` (skips on macOS) |
| Full suite command | `PYTHONPATH=src pytest tests/ -m "not integration" -v` (baseline gate) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DMV3-07 | 5 stubs replaced with real implementations; agent trains | e2e (GPU-gated) | `pytest tests/dreamer/test_dreamerv3_subprocess_e2e.py::TestDreamerV3SubprocessE2E::test_e2e_run_dreamer_training_real_agent -v` | ❌ Wave 0 (flip existing) |
| DMV3-07 | JAX never leaks into parent | unit (source inspection) | `pytest tests/test_dreamer_subprocess.py -v` (existing 5 tests + new import-leak guard) | ❌ Wave 0 (add leak guard) |
| DMV3-08 | Checkpoint persists per task/obs-type | e2e (GPU-gated) | `pytest tests/dreamer/test_dreamerv3_checkpoint_resume.py -v` | ❌ Wave 0 (new file) |
| DMV3-08 | Resume across restarts | e2e (GPU-gated) | `pytest tests/dreamer/test_dreamerv3_checkpoint_resume.py::test_restart_then_continue -v` | ❌ Wave 0 (new file) |
| DMV3-09 | Sentinel flipped to positive | e2e (GPU-gated) | `pytest tests/dreamer/test_dreamerv3_subprocess_e2e.py::TestDreamerV3SubprocessE2E::test_e2e_checkpoint_files_written -v` | ❌ Wave 0 (flip existing) |
| DMV3-09 | `_build_agent is None` regression guard | unit (no GPU) | `pytest tests/dreamer/test_dreamerv3_regression_guard.py -v` | ❌ Wave 0 (new file) |
| DMV3-10 | CI GPU smoke: finite loss + checkpoint exists | CI GPU smoke | `pytest tests/dreamer/ -v` (on GPU runner) | ❌ Wave 0 (CI job) |
| DMV3-10 | macOS skips cleanly | unit (skipif) | `pytest tests/dreamer/ -v -rs` (3+ skipped, 0 failed on macOS) | ✅ existing pattern |

### Sampling Rate (Nyquist)
- **Per task commit:** `PYTHONPATH=src pytest tests/dreamer/ -v` (skips on macOS; validates skipif + regression guard)
- **Per wave merge:** `PYTHONPATH=src pytest tests/ -m "not integration" -v` (full baseline gate — v0.4.0 + v0.4.2 + v0.5.0 + v0.6.0-phases-36-39 stays green)
- **Phase gate:** Full suite green on macOS (skips OK) + GPU smoke green on CI GPU host (if provisioned)

### Observable properties (runtime invariants, frequency ≥ 2× change rate)
| Invariant | Frequency | Where asserted |
|-----------|-----------|----------------|
| `_build_agent` does not return None | Every import (source inspection) | unit test (macOS + GPU) |
| JAX not imported in parent process | Every import (source inspection / import-leak guard) | unit test (macOS + GPU) |
| JSON pipe delivers METRICS without corruption | Every training step (~100 messages per 1000 steps) | e2e (GPU) |
| Checkpoint file exists after training | Once per run | e2e (GPU) |
| Loss is finite (not NaN/inf) | Every metric yield | e2e (GPU) + CI smoke |
| macOS skips (not errors) on no-GPU | Every pytest collection | skipif gate (macOS) |

### Wave 0 Gaps
- [ ] `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — flip 2 test methods from negative to positive assertions (DMV3-09)
- [ ] `tests/dreamer/test_dreamerv3_regression_guard.py` — new file: `_build_agent is None` source-inspection guard (no GPU required, runs on macOS)
- [ ] `tests/dreamer/test_dreamerv3_checkpoint_resume.py` — new file: restart-then-continue checkpoint resume test (GPU-gated)
- [ ] `tests/test_dreamer_subprocess.py` — add JAX-import-leak guard test (no GPU required)
- [ ] `.github/workflows/ci.yml` — add `dreamer-gpu` job (or extend Dockerfile.cuda) with `[dreamer]` + jax[cuda12] install
- [ ] No framework install needed (pytest already installed)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyPI `dreamerv3==1.5.0` (object-based `embodied.run.train(agent, env, ...)`) | Current repo `dreamer==3.3.1` (factory-based `embodied.run.train(make_agent, ...)`, `elements.*`) | Repo evolved after PyPI publish (Feb 2023 → 2025/2026) | The pinned PyPI package uses the OLD object-based API; stubs must target this, not the repo main branch |
| `gym==0.19.0` (old gym) | `gymnasium>=0.29.0` (maintained fork) | gymnasium forked from gym ~2023 | dreamerv3 1.5.0's `FromGym` imports `gym`; project uses `gymnasium`; use project's `GymToEmbodiedWrapper` instead |
| `embodied.Flags/Config/Path` | `elements.Flags/Config/Path` | Repo refactored embodied→elements | PyPI 1.5.0 uses `embodied.*`; current repo uses `elements.*`; stay on `embodied.*` for the pinned version |

**Deprecated/outdated:**
- `dreamerv3/train.py` (PyPI 1.5.0 entry script): uses `embodied.Flags` — still valid for the pinned version, but the current repo moved to `dreamerv3/main.py` with `elements.Flags`.
- `example.py` (referenced in PyPI description): 404 on the repo (confirmed). The canonical pattern for custom envs is `train.py:make_env()` which says "You can add custom environments by creating and returning the environment instance here."

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `embodied.Logger` TerminalOutput writes to stdout and must be redirected to stderr | Upstream API / Pattern 3 | If it already writes to stderr, no redirection needed; if it bypasses sys.stdout entirely, the pipe may be clean already |
| A2 | The exact CI GPU host provisioning strategy (GitHub Actions GPU runner vs self-hosted vs Docker) | CI GPU Smoke / DMV3-10 | If no GPU runner is available, the smoke test 100%-skips and the milestone audit fails |
| A3 | `embodied.run.train` can be driven from inside `_train_loop` without conflicting with the subprocess's own CHECKPOINT message protocol | Architecture / Pattern 1 | `embodied.run.train` manages its own checkpointing; if it conflicts with the parent's CHECKPOINT messages, a manual loop is needed |
| A4 | The `GymToEmbodiedWrapper.action_space` needs to return a dict `{"action": box, "reset": bool}` to match `Agent.__init__`'s `act_space['action']` extraction | Upstream API / Pitfall 2 | If the wrapper's current `spaces.Box` return is accepted, no change needed; if not, wrapper.py needs a minor fix |
| A5 | The `step` arg to `Agent(obs_space, act_space, step, config)` is an `embodied.Counter()` not an int | Upstream API | If it's just an int, simpler construction; verified from source that it's `embodied.Counter()` |
| A6 | `jax~=0.4.20` (pyproject pin) is compatible with `dreamerv3~=1.5.0` (PyPI 1.5.0 requires unpinned `jax`) | Version Compatibility | PyPI 1.5.0's requirements.txt has `jax` unpinned, so `~=0.4.20` should work; but jaxlib version must match |

## Open Questions for discuss-phase

1. **Q1 (CRITICAL): PyPI 1.5.0 object API vs current-repo factory API — which to target?**
   - What we know: pyproject pins `dreamerv3~=1.5.0` (installs PyPI 1.5.0, object-based API). The STATE.md blocker names factory composition from the current repo (factory-based API). These are DIFFERENT APIs.
   - What's unclear: Should the stubs target the pinned PyPI 1.5.0 API (recommended — it's what `pip install '.[dreamer]'` installs), or should the pin be changed to a git install of the current repo?
   - Recommendation: Target PyPI 1.5.0 (object-based). Do NOT change the pin. The object API is simpler (no factory functions) and is what's installed.

2. **Q2: `embodied.run.train` vs manual training loop inside `_train_loop`?**
   - What we know: `embodied.run.train(agent, env, replay, logger, args)` runs a full training loop with its own checkpointing + logging. The subprocess protocol has its own CHECKPOINT messages and METRICS yielding.
   - What's unclear: Can `embodied.run.train` be driven from inside `_train_loop` and yield METRICS via the pipe, or does its internal checkpointing/logging conflict with the subprocess protocol?
   - Recommendation: Start with a manual loop (`embodied.Driver` + `agent.train()` batches) for more control over the JSON pipe; fall back to `embodied.run.train` if the manual loop is too complex.

3. **Q3: CI GPU host provisioning — GitHub Actions GPU runner, self-hosted, or Docker?**
   - What we know: No GPU job exists in ci.yml. Dockerfile.cuda installs `[dev,tracking]` but NOT `[dreamer]`. GitHub Actions offers GPU runners (ubuntu-latest-4-core-gpu etc.) but they may not be enabled for this repo.
   - What's unclear: Which GPU runner is available? Is this an ops decision or a code decision?
   - Recommendation: Add a `dreamer-gpu` CI job using GitHub Actions GPU runner + install `jax[cuda12]~=0.4.20` + `[dreamer]`. If no GPU runner is available, document the gap and mark DMV3-10 as "pending GPU provisioning" (the test is added; it just can't run yet — same as Phase 30's status).

4. **Q4: Checkpoint format — `embodied.Checkpoint` binary vs `.pt` files?**
   - What we know: The existing code uses `checkpoint_*.pt` / `final.pt` naming (training.py:188, 315, 333). The upstream `embodied.Checkpoint` writes to a `checkpoint.ckpt` path. The file format is a binary pickle of numpy arrays.
   - What's unclear: Should the phase use `embodied.Checkpoint`'s native format (`.ckpt`) or adapt to the existing `.pt` naming?
   - Recommendation: Use `embodied.Checkpoint` with `checkpoint.ckpt` (native format); update `_find_latest_checkpoint` to glob `*.ckpt` instead of `checkpoint_*.pt`. The `.pt` naming was a stub-era placeholder.

5. **Q5: obs-type taxonomy — what are the valid obs_type values?**
   - What we know: `DreamerConfig.obs_type` is `Literal["pixels", "state"]`. The wrapper handles both. The checkpoint path uses `{task}_{obs_type}`.
   - What's unclear: Are there other obs types? Does DreamerV3 need `encoder.mlp_keys`/`cnn_keys` config to know which obs keys are image vs state?
   - Recommendation: Stay with `pixels`/`state`. The `GymToEmbodiedWrapper` already produces the right dict keys (`image`/`state` + `is_first`/`is_last`/`is_terminal`).

6. **Q6: Smoke test step budget — 500 or 1000?**
   - What we know: Phase 30 used `total_steps=1000, eval_every=500` (D-STEPS-01). CI runtime ~3-5 min.
   - Recommendation: Use `total_steps=1000` (same as Phase 30). The budget is well below production but enough to assert structural properties.

## Artifacts This Phase Will Likely Touch

### Production source (modified)
| File | Symbol | Change |
|------|--------|--------|
| `src/surg_rl/dreamer/subprocess.py` | `_build_agent` | Stub → real `Agent(obs_space, act_space, step, config)` construction |
| `src/surg_rl/dreamer/subprocess.py` | `_train_loop` | Stub → real training loop (Driver + agent.train or embodied.run.train) |
| `src/surg_rl/dreamer/subprocess.py` | `_evaluate` | Stub → real agent.policy rollouts |
| `src/surg_rl/dreamer/subprocess.py` | `_save_checkpoint` | Stub → real `cp.save()` |
| `src/surg_rl/dreamer/subprocess.py` | `_load_checkpoint` | Stub → real `cp.load()` |
| `src/surg_rl/dreamer/training.py` | `_find_latest_checkpoint` | Glob `*.ckpt` instead of `checkpoint_*.pt` (if checkpoint format changes) |
| `src/surg_rl/dreamer/wrapper.py` | `action_space` property | Return dict `{"action": box, "reset": bool}` if Agent requires it (A4) |

### Test source (modified/new)
| File | Change |
|------|--------|
| `tests/dreamer/test_dreamerv3_subprocess_e2e.py` | Flip 2 test methods negative→positive (DMV3-09) |
| `tests/dreamer/test_dreamerv3_regression_guard.py` | NEW: `_build_agent is None` source-inspection guard (no GPU) |
| `tests/dreamer/test_dreamerv3_checkpoint_resume.py` | NEW: restart-then-continue checkpoint resume (GPU-gated) |
| `tests/test_dreamer_subprocess.py` | Add JAX-import-leak guard test |

### CI config (modified/new)
| File | Change |
|------|--------|
| `.github/workflows/ci.yml` | Add `dreamer-gpu` job (GPU runner + `[dreamer]` install) |
| `Dockerfile.cuda` (optional) | Add `[dreamer]` + `jax[cuda12]` install (if Docker-based GPU CI) |

### UNCHANGED (explicitly preserved)
| File | Why unchanged |
|------|---------------|
| `src/surg_rl/dreamer/subprocess.py` `_JsonStdout` class | SC#1 — pipe protocol foundation |
| `src/surg_rl/dreamer/subprocess.py` `DreamerSubprocess` class | SC#1 — parent-side protocol |
| `src/surg_rl/dreamer/subprocess.py` `_subprocess_main` | SC#1 — env var setup before JAX import |
| `src/surg_rl/dreamer/subprocess.py` `_run_subprocess_loop` message dispatch | SC#1 — protocol handlers (only the called functions change) |
| `src/surg_rl/dreamer/__init__.py` `LazyImport` guard | SC#5 — JAX isolation |
| `src/surg_rl/dreamer/spike.py` | Out of scope (DMV3-01 spike, not modified) |
| `src/surg_rl/scene_definition/schema.py` `DreamerConfig` | No schema changes (additive phase) |

## Risks & Landmines (with mitigations)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| API version drift (PyPI 1.5.0 vs repo main) | HIGH (confirmed) | Stubs written against wrong API → ImportError/TypeError | Target PyPI 1.5.0 object-based API; verify against installed package; Q1 for discuss-phase |
| JAX leaks into parent process | MEDIUM | SC#5 violation; GPU memory conflict; slow pytest collection | All JAX imports inside stub function bodies; add import-leak guard test |
| Logger corrupts JSON pipe | MEDIUM | Protocol corruption; json.JSONDecodeError in parent | Configure embodied logger to stderr; test for clean pipe |
| gym vs gymnasium version conflict | MEDIUM | pip resolver conflict; FromGym breaks | Use project's GymToEmbodiedWrapper, NOT dreamerv3's FromGym |
| CI GPU host not provisioned | MEDIUM-HIGH | DMV3-10 100%-skipped; milestone audit fails | Add dreamer-gpu CI job; if no GPU runner, document gap explicitly |
| `embodied.run.train` conflicts with subprocess CHECKPOINT protocol | LOW-MEDIUM | Double-checkpointing; protocol confusion | Use manual loop if conflict; Q2 for discuss-phase |
| Convergence-threshold temptation | LOW | CI smoke asserts MSE<0.01 (out of scope) | DMV3-10 explicitly excludes; structural assertions only |
| Checkpoint path collision across tasks | LOW | Wrong agent weights on resume | Derive ckpt dir from `{task}_{obs_type}`; DMV3-08 test covers this |
| jax/jaxlib version incompatibility | LOW-MEDIUM | jax~=0.4.20 with dreamerv3 1.5.0 may have API gaps | Pin jax+jaxlib together; test on GPU host first |

## Environment Availability

| Dependency | Required By | Available (macOS dev) | Version | Fallback |
|------------|------------|----------------------|---------|----------|
| jax | DreamerV3 training | ✓ (installed) | 0.10.2 (NOT the ~=0.4.20 pin) | Tests skip on macOS (no GPU) |
| jaxlib | JAX XLA backend | ✓ (installed) | (transitive) | Tests skip on macOS |
| dreamerv3 | Agent + embodied lib | ✗ (not installed) | — | Tests skip (find_spec returns None) |
| optax | DreamerV3 optimizer | ✗ | — | Tests skip |
| GPU (CUDA) | JAX GPU training | ✗ (macOS, no NVIDIA GPU) | — | Tests skip per INV-8 |
| mujoco | SurgicalEnv | ✓ | >=3.0.0 | — (already a core dep) |
| gymnasium | SurgicalEnv | ✓ | >=0.29.0 | — (already a core dep) |

**Missing dependencies with no fallback:**
- None for macOS dev (tests skip cleanly per INV-8)
- GPU host requires: `jax[cuda12]~=0.4.20` + `dreamerv3~=1.5.0` + `optax>=0.1.7` (all in `[dreamer]` extra + jax CUDA install)

**Missing dependencies with fallback:**
- macOS: all dreamer tests skip (no GPU, no dreamerv3) — this is the designed behavior

## Security Domain

`security_enforcement` is not explicitly set in config.json, so it defaults to enabled. However, this phase is a stub-replacement + test-inversion phase with no new user input, no new network endpoints, and no new auth/session/crypto surface. The only external interaction is the existing subprocess pipe (already vetted in Phase 24/26/30).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — no new auth |
| V3 Session Management | no | N/A — no sessions |
| V4 Access Control | no | N/A — no new access control |
| V5 Input Validation | yes (minimal) | The CONFIG message dict is deserialized from JSON; existing `json.loads` in `_run_subprocess_loop` already handles this. No new user input paths. |
| V6 Cryptography | no | N/A — checkpoints use pickle (embodied.Checkpoint), not encryption. Same as Phase 24. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Subprocess pipe message injection | Tampering | The subprocess pipe is intra-process (multiprocessing.Pipe, not network); no external attacker surface. JSON validation via `json.loads` already in place. |
| Checkpoint file tampering | Tampering | Checkpoint files are on local disk under `models/dreamerv3/`; no network exposure. File permissions inherit from the process. |

## Sources

### Primary (HIGH confidence)
- `dreamerv3-1.5.0` PyPI tarball (downloaded + extracted + source inspected) — Agent constructor, embodied.run.train signature, Checkpoint API, FromGym wrapper, requirements.txt, setup.py
- `src/surg_rl/dreamer/subprocess.py` — the 5 stubs (read in full)
- `src/surg_rl/dreamer/wrapper.py` — GymToEmbodiedWrapper (read in full)
- `src/surg_rl/dreamer/training.py` — run_dreamer_training, _find_latest_checkpoint (read in full)
- `tests/dreamer/test_dreamerv3_subprocess_e2e.py` — the sentinel test (read in full)
- `.planning/phases/30-dreamerv3-real-subprocess-e2e-test/30-CONTEXT.md` + `30-VERIFICATION.md` — sentinel design, skipif pattern, stub-reality revision
- `.github/workflows/ci.yml` — current CI config (read in full)
- `pyproject.toml` — version pins (read in full)
- `https://raw.githubusercontent.com/danijar/dreamerv3/main/dreamerv3/main.py` — current repo factory API (verified via curl)
- `https://raw.githubusercontent.com/danijar/dreamerv3/main/requirements.txt` — current repo deps (jax[cuda12]==0.4.33, elements>=3.19.1, etc.)
- `https://raw.githubusercontent.com/danijar/dreamerv3/main/setup.py` — current repo setup.py (name='dreamer', version='3.3.1')

### Secondary (MEDIUM confidence)
- `https://docs.jax.dev/en/latest/gpu_memory_allocation.html` — XLA_PYTHON_CLIENT_MEM_FRACTION semantics
- `https://github.com/danijar/dreamerv3/blob/main/README.md` — Python 3.11+ requirement, checkpoint resume via same logdir
- `https://github.com/danijar/dreamerv3/blob/b65cf81a/embodied/run/train.py` — checkpoint setup code (via WebFetch)
- `https://github.com/danijar/dreamerv3/blob/main/dreamerv3/main.py` — factory function signatures (via WebFetch)
- `https://github.com/danijar/dreamerv3/blob/main/dreamerv3/agent.py` — Agent constructor (via WebFetch)
- `https://deepwiki.com/danijar/dreamerv3/8-environment-integration` — gym suite integration pattern
- `https://pypi.org/project/dreamerv3/` — PyPI version 1.5.0, example.py reference

### Tertiary (LOW confidence)
- `https://github.com/danijar/dreamerv3/blob/b65cf81a/embodied/core/base.py` — Agent base class (no save/load in base; via WebFetch)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified via pyproject.toml + pip download + tarball inspection
- Architecture: HIGH — stub code read in full; upstream API verified from actual PyPI package source
- Pitfalls: HIGH — API drift confirmed by direct comparison; gym/gymnasium conflict confirmed from requirements.txt
- Upstream API (PyPI 1.5.0 vs repo main): HIGH — verified by downloading and inspecting the actual tarball
- CI GPU host provisioning: MEDIUM — current ci.yml confirmed (no GPU job); provisioning strategy is an open question
- Logger-to-stderr mechanism: MEDIUM (ASSUMED) — the exact embodied logger redirection needs implementation-time verification

**Research date:** 2026-07-11
**Valid until:** 2026-08-11 (30 days — the dreamerv3 PyPI package is stable at 1.5.0 since Feb 2023; the repo main branch is fast-moving but we target the pinned PyPI version)

## RESEARCH COMPLETE

**Phase:** 40 - Real DreamerV3 Integration + Sentinel Flip
**Confidence:** HIGH

### Key Findings
1. **API drift (CRITICAL):** The pinned `dreamerv3~=1.5.0` PyPI package uses an object-based API (`embodied.run.train(agent, env, replay, logger, args)`, `Agent(obs_space, act_space, step, config)` — 4 args), DIFFERENT from the current GitHub repo main branch (factory-based API, `Agent(obs_space, act_space, config)` — 3 args, `elements.*` not `embodied.*`). The stubs must target the PyPI 1.5.0 object API.
2. **Checkpoint pattern mismatch:** The stubs `_save_checkpoint(agent, path)` / `_load_checkpoint(agent, path)` do NOT match the upstream `embodied.Checkpoint` pattern (attribute registration with `cp.agent=agent; cp.replay=replay; cp.step=step; cp.load_or_save()`). The stub replacement must use `embodied.Checkpoint`.
3. **gym vs gymnasium conflict:** dreamerv3 1.5.0 pins `gym==0.19.0`; the project uses `gymnasium>=0.29.0`. Resolution: use the project's existing `GymToEmbodiedWrapper` (already implements the embodied.Env protocol against Gymnasium), NOT dreamerv3's `FromGym`.
4. **CI GPU gap:** No GPU job exists in ci.yml; Dockerfile.cuda does NOT install `[dreamer]`. A new `dreamer-gpu` CI job is needed for DMV3-10.
5. **Sentinel inversion is precisely scoped:** 2 test methods in `tests/dreamer/test_dreamerv3_subprocess_e2e.py` flip from negative to positive; a new regression guard test (`_build_agent is None` source inspection) runs on ALL runners without GPU.

### File Created
`/Users/tt/Documents/RLProj/.planning/phases/40-real-dreamerv3-integration-sentinel-flip/40-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Versions verified via pip download + tarball inspection + pyproject.toml |
| Architecture | HIGH | Stub code read in full; upstream API verified from actual PyPI package source; subprocess protocol mapped |
| Pitfalls | HIGH | API drift confirmed by direct source comparison; gym/gymnasium conflict confirmed from requirements.txt |
| CI GPU provisioning | MEDIUM | Current ci.yml confirmed (no GPU job); provisioning strategy is an open question for discuss-phase |
| Logger-to-stderr | MEDIUM | Exact embodied logger redirection mechanism assumed; needs implementation-time verification |

### Open Questions
1. Q1: PyPI 1.5.0 object API vs current-repo factory API — which to target? (Recommendation: PyPI 1.5.0)
2. Q2: `embodied.run.train` vs manual training loop inside `_train_loop`?
3. Q3: CI GPU host provisioning strategy?
4. Q4: Checkpoint format — `embodied.Checkpoint` native `.ckpt` vs existing `.pt` naming?
5. Q5: obs-type taxonomy (encoder.mlp_keys/cnn_keys)?
6. Q6: Smoke test step budget (500 or 1000)?

### Ready for Planning
Research complete. Planner can now create PLAN.md files. The 6 open questions above should be resolved in `/gsd-discuss-phase 40` before `/gsd-plan-phase 40`.