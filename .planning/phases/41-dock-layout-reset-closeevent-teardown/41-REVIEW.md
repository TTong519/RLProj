---
phase: 41-dock-layout-reset-closeevent-teardown
reviewed: 2026-07-16T01:58:13Z
depth: deep
files_reviewed: 6
files_reviewed_list:
  - src/surg_rl/editor/dock_state.py
  - src/surg_rl/editor/llm_panel.py
  - src/surg_rl/editor/main_window.py
  - src/surg_rl/editor/tree_view.py
  - src/surg_rl/editor/viewport.py
  - tests/test_dock_state.py
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 41: Code Review Report

**Reviewed:** 2026-07-16T01:58:13Z
**Depth:** deep
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Deep cross-file review of the Phase 41 dock-layout-reset + closeEvent-teardown
delta (6 files vs diff_base 286dff6). The in-place `update_scene` swap invariant
(D-06), the `aboutToClose → LLMPanel.stop()` chain (D-04), the QThread
cooperative teardown body (D-05 — no `terminate()`/`deleteLater()` in the
executable body), and the `aboutToClose`-emitted-BEFORE-`super().closeEvent()`
ordering are all correctly wired and verified end-to-end.

However, one Critical correctness bug defeats the headline feature
(GUI-18 "Reset Layout"): the factory-default snapshot is captured at first
`showEvent`, *after* `_restore_geometry()` has already re-applied the user's
saved QSettings layout in `__init__`. "Reset Layout" therefore resets to the
user's last-saved arrangement, not the factory default. This was confirmed
empirically. Three additional Warnings cover a dead cancel flag (the `stop()`
docstring falsely claims the worker polls it), a duplicate `currentChanged`
connection that double-fires `node_selected` after every scene load, and a
test that gives false confidence by completing naturally before the 3s
`wait()` timeout.

## Critical Issues

### CR-01: Factory-default snapshot captures the user's restored layout, not the factory default

**File:** `src/surg_rl/editor/main_window.py:91-92, 379-385` (and `src/surg_rl/editor/dock_state.py:41-50`)

**Issue:**
`EditorWindow.__init__` calls `self._restore_geometry()` at line 91, which
calls `self.restoreState(state)` with the user's previously-saved QSettings
dock layout. Only *after* that does the first `showEvent` (line 379) fire
`DockStateManager.capture_factory_default(self)`, which snapshots
`window.saveState()` — i.e. the **user's restored arrangement**, not the
code-built factory arrangement.

Consequence: when a saved layout exists in QSettings, `Reset Layout`
(`_action_reset_layout → reset_to_default → restoreState(factory_state)`)
resets to the user's last-saved layout instead of the factory default. This
directly contradicts D-01/GUI-18 ("factory-default dock layout") and makes
the feature a no-op in the common case (a returning user).

Verified empirically: with a tabified layout saved to QSettings, a fresh
`EditorWindow` instance captures the tabified state as `_factory_state`, and
after `splitDockWidget` + `_action_reset_layout()`, the docks end up
tabified again (the user's saved state), not split (the factory default).

The regression tests in `tests/test_dock_state.py` do not catch this because
`isolated_home` starts with empty QSettings, so `_restore_geometry` is a
no-op and the first-show capture happens to equal the built factory layout.

**Fix:**
Capture the factory default in `__init__` *after* `_build_dock_widgets()` and
*before* `_restore_geometry()`. `saveState()` returns a valid `QByteArray`
before the window is shown (dock widgets are already added), and the
one-shot `_captured` guard in `DockStateManager` makes the later `showEvent`
capture a no-op, so the snapshot reflects the code-built layout regardless of
any restored user geometry.

```python
# main_window.py __init__, after self._build_dock_widgets() and before self._restore_geometry()
self._build_dock_widgets()
# Capture the factory-default snapshot from the CODE-BUILT layout before
# _restore_geometry re-applies the user's saved QSettings layout (D-01).
self._dock_state.capture_factory_default(self)
self._build_menu_bar()
...
self._restore_geometry()
```

The `showEvent` body can stay as-is (it becomes a defensive no-op via the
one-shot guard) or be reduced to `super().showEvent(event)`.

## Warnings

### WR-01: `_cancelled` cancel flag is dead code; `stop()` docstring falsely claims the worker polls it

**File:** `src/surg_rl/editor/llm_panel.py:145-149` (claim) vs `src/surg_rl/editor/llm_panel.py:36-43` (worker body); cross-file `src/surg_rl/scene_generation/text_parser.py` (no `cancel`/`_cancelled`/`property` references)

**Issue:**
`LLMPanel.stop()` sets `self._worker.setProperty("_cancelled", True)` and the
inline comment states: *"the worker's run() polls it; do NOT switch to a
Python attribute, the worker lives on the QThread and the property is the
thread-safe accessor."* A repo-wide grep confirms `_cancelled` is **only ever
set, never read**. `TextParserWorker.run()` blocks on
`self._parser.parse_sync(prompt)` until natural completion and never inspects
the property; `text_parser.py` has no cancel hook either.

So the cancel flag is pure dead code. The Cancel button (and the
`aboutToClose` teardown path) do not actually interrupt an in-flight LLM
call — they rely solely on `thread.quit()` (which cannot preempt a blocking
call that does not return to the QThread event loop) plus `thread.wait(3000)`
(which just blocks for natural completion or a 3s timeout). The
`setProperty("_cancelled", True)` line gives a false impression that
cancellation is cooperative and thread-safe.

**Fix (one of):**
- Correct the misleading comment to state that the current `TextParser`
  implementation is not cancellable, so `stop()` relies on `thread.quit()` +
  `thread.wait(3000)` + best-effort timeout log, and the `_cancelled` property
  is a forward-compatible marker for a future cancellable parser; **or**
- Actually poll the property inside `run()` (requires `parse_sync` to accept a
  cancellation hook / accept polling between chunked provider calls) and
  short-circuit with `self.failed.emit("cancelled")` when set.

```python
# Minimal honest comment fix (llm_panel.py:145-149):
if self._worker is not None:
    # Forward-compatible cancel marker. NOTE: the current TextParser.parse_sync
    # is a blocking uncancellable call; this property is NOT polled by run()
    # today. stop() therefore relies on thread.quit() + wait(3000) for
    # teardown; a future chunked/cancellable parser should poll it.
    self._worker.setProperty("_cancelled", True)
```

### WR-02: `SceneTreeView.update_scene` double-connects `currentChanged`, so `node_selected` fires twice per selection after every scene load

**File:** `src/surg_rl/editor/tree_view.py:99-120` (specifically 115-120)

**Issue:**
`update_scene` defensively re-runs `sm.currentChanged.connect(self._on_selection_changed)` after `self._model.clear()`. The comment claims *"clear() can reset the selectionModel on some Qt versions; re-wire defensively."* In reality `QStandardItemModel.clear()` triggers a model reset but does **not** replace the view's `selectionModel()` (the view owns it and it persists across the reset). The original connection from `__init__` (line 68) is therefore still live, and the defensive `connect` adds a **second** connection.

Verified empirically: after one `update_scene` call, selecting a node emits
`node_selected` **twice** (count == 2, expected 1). Downstream,
`EditorWindow._on_node_selected` re-runs `SchemaWalker().walk(...)` and
`self._property_form.set_field_specs(...)` twice per click. Today this is
wasteful but roughly idempotent; for any future handler with side effects,
double-firing is a latent correctness bug.

**Fix:**
Remove the defensive re-connect block entirely — the original connection
survives `clear()`. (If a Qt version genuinely replaces the selectionModel on
`clear()`, the correct fix would be to disconnect the old
`selectionModel().currentChanged` before connecting the new one, not to
connect unconditionally.)

```python
# tree_view.py update_scene — drop the trailing block:
def update_scene(self, scene: SceneDefinition) -> None:
    self._scene = scene
    self._model.clear()
    self._model.setHorizontalHeaderLabels(["Scene Elements"])  # clear() drops headers
    self._build_tree()
    self.expandAll()
    # NOTE: do NOT re-connect currentChanged here — the view's selectionModel
    # persists across model.clear() and the __init__ connection is still live;
    # re-connecting would double-fire node_selected.
```

### WR-03: `TestCloseMidCallMockSlow` uses `time.sleep(2)` (< `wait(3000)`), so it never exercises the teardown/timeout path

**File:** `tests/test_dock_state.py:224-262` (specifically 232, 249-258)

**Issue:**
The "always-on backstop" test monkeypatches `parse_sync` to `time.sleep(2)`
and then calls `stop()`, which does `thread.wait(3000)`. Because 2s < 3s, the
worker thread exits by **natural completion** before the wait times out, so
`wait` returns `True`, `thread.isRunning()` is `False`, and the assertion
passes — regardless of whether the cancel/teardown logic actually works. The
test gives false confidence: it proves only the happy "call finished on its
own" path, not the SC#3 "close mid-call" path it claims to guard. A sleep
longer than 3s would expose the timeout branch (log + proceed with the thread
still running), at which point the current `assert not thread.isRunning()`
would actually fail.

**Fix:**
Either (a) use `time.sleep(5)` (> 3000 ms) and assert that the warning is
logged and the thread is eventually cleaned up (not that `isRunning()` is
immediately False), or (b) keep the 2s sleep but rename/relabel the test to
honestly state it only covers natural completion + no-crash, and add a
separate test for the timeout path.

```python
# Option (b) — honest naming + a separate timeout test:
def test_close_after_natural_completion_no_crash(self, ...):  # was test_close_mid_llm_call_clean_exit_mock_slow
    ...  # time.sleep(2) — proves no segfault/RuntimeError on clean completion

def test_close_hung_worker_logs_and_proceeds(self, ...):
    # time.sleep(10) -> wait(3000) times out -> assert warning logged,
    # assert not thread.isFinished() at first, then drive event loop until
    # the worker exits and deleteLater fires.
```

## Info

### IF-01: `_refresh_recent_menu` builds the menu twice (pre-existing, not in Phase 41 delta)

**File:** `src/surg_rl/editor/main_window.py:358-368`

**Issue:**
`_refresh_recent_menu` calls `self._recent_menu.clear()` and rebuilds the
action list, then immediately calls `clear()` and rebuilds the identical
list a second time. The duplicate block is pre-existing (not touched by the
Phase 41 diff) but is dead work and a copy-paste defect. Worth fixing while
the file is being touched.

**Fix:**
Delete the second `clear()` + `for` block (lines 364-368); keep only the
first pair.

---

## Resolution

**CR-01 — FIXED.** Applied the reviewer's minimal fix: moved
`DockStateManager.capture_factory_default(self)` from `showEvent` into
`__init__`, immediately after `_build_dock_widgets()` and before
`_restore_geometry()`, so the factory snapshot is captured from the code-built
layout before the user's saved QSettings layout is re-applied. The one-shot
`_captured` guard makes the later `showEvent` capture a defensive no-op
(`showEvent` body left unchanged).

TDD RED→GREEN:

- **RED `4b9abf6`** — added
  `TestResetLayoutReturningUser::test_reset_layout_restores_factory_split_for_returning_user`.
  This exercises the **true returning-user path** the SC#1 test misses: session 1
  rearranges (tabify tree+properties) and closes (QSettings round-trips the saved
  layout via `save_window`/`sync`); session 2 reopens (`__init__`'s
  `_restore_geometry` re-applies the saved tabified layout) then Reset Layout
  must restore the **factory split**, not the saved tabified arrangement. The
  `isolated_home`-from-empty SC#1 test missed CR-01 because `_restore_geometry`
  is a no-op on empty QSettings. Failed on the capture-at-`showEvent` code with
  the exact CR-01 assertion.
- **GREEN `e9a4ab1`** — moved capture to `__init__` (before `_restore_geometry`);
  the new test passes and all 8 phase tests stay green (1 skipped — real-provider,
  no `LLM_API_KEY`). `main_window.py` is ruff-clean + black-clean.

**Deferred as follow-up (tracked here, NOT fixed in this phase per the
"Fix CR-01 now, then complete" decision):**

- **WR-01** (`_cancelled` dead code / misleading `stop()` docstring,
  `llm_panel.py:145-149`) — the current `TextParser.parse_sync` is a blocking
  uncancellable call; the cancel property is set but never polled. Honest-comment
  fix is trivial but out of scope for the CR-01-only completion.
- **WR-02** (`SceneTreeView.update_scene` double-connects `currentChanged`,
  `tree_view.py:115-120`) — `node_selected` fires twice per selection after each
  scene load; remove the defensive re-connect block (the `__init__` connection
  survives `model.clear()`). Latent double-fire; address in a follow-up editor
  phase.
- **WR-03** (`TestCloseMidCallMockSlow` `time.sleep(2)` < `wait(3000)` never
  exercises the teardown/timeout path, `tests/test_dock_state.py:224-262`) —
  relabel to cover natural-completion + add a `sleep(5)` timeout test. Test-honesty
  fix; out of scope.
- **IF-01** (`_refresh_recent_menu` builds the menu twice, `main_window.py:358-368`)
  — pre-existing, NOT in the Phase 41 delta; explicitly called out under GUI-17
  (recent-files) in `REQUIREMENTS.md`, so it will be addressed in the GUI-17 phase.

_Resolved: 2026-07-16_
_Resolving commits: 4b9abf6 (RED), e9a4ab1 (GREEN)_

---

_Reviewed: 2026-07-16T01:58:13Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_