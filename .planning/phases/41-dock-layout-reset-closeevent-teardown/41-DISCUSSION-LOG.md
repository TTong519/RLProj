# Phase 41: Dock Layout Reset & CloseEvent Teardown - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-15
**Phase:** 41-Dock Layout Reset & CloseEvent Teardown
**Areas discussed:** Reset Layout semantics, closeEvent teardown harness, update_scene refactor depth, objectName + test approach

---

## Reset Layout semantics

### Q1 — Factory-default capture mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Capture at first showEvent | QByteArray snapshot once at first showEvent; Reset = restoreState(default). Robust to code drift. | |
| Hardcoded rebuild | Build default layout in code; Reset calls it directly. Simpler but duplicates layout definition. | |
| Both | Capture at first showEvent AND keep a code-level rebuild as fallback if snapshot missing/corrupt. | ✓ |

**User's choice:** Both
**Notes:** Belt-and-suspenders — snapshot is primary (reflects actual built layout), code rebuild is the fallback.

### Q2 — Reset Layout action count

| Option | Description | Selected |
|--------|-------------|----------|
| Factory default only | One action: Reset restores factory default (discards customization). Matches SC#1. | ✓ |
| Factory default + Restore Saved | Two actions: Reset to factory + Restore Saved Layout re-applies last-saved without restart. | |

**User's choice:** Factory default only
**Notes:** Keep menu minimal; user's last-saved arrangement reappears only via close+reopen (SC#2).

### Q3 — User-saved restore timing on open

| Option | Description | Selected |
|--------|-------------|----------|
| Keep __init__ restore | Restore in __init__ via _restore_geometry() (docks built before it); fix recreation, not timing. | ✓ |
| Defer to showEvent | Defer restoreState to showEvent/QTimer.singleShot(0); robust to "restore before docks exist" pitfall. | |

**User's choice:** Keep __init__ restore
**Notes:** The bug is widget recreation in _refresh_viewport_and_tree, not restore timing. Pitfall 2 timing-defer not needed.

---

## closeEvent teardown harness

### Q1 — Teardown structure (milestone-wide contract)

| Option | Description | Selected |
|--------|-------------|----------|
| aboutToClose signal (registry) | closeEvent emits aboutToClose; panels register stop() as slots. New panels declare stop()+connect — no closeEvent edit. | ✓ |
| Explicit enumerated stop()s | closeEvent calls each panel's stop() in order. Simple but every new panel needs a manual edit (how bug #3 was born). | |
| aboutToClose + explicit fallback | Both: signal primary + explicit enumerated fallback for core panels. | |

**User's choice:** aboutToClose signal (registry)
**Notes:** Milestone-wide contract — Phase 42/46/48/51 workers plug in by declaring stop() + connecting to aboutToClose.

### Q2 — stop() behavior on hung worker

| Option | Description | Selected |
|--------|-------------|----------|
| wait(3000) then proceed | Cancel flag + thread.quit() + wait(3000); on timeout log warning and proceed (best-effort, never block quit). | ✓ |
| wait(3000) then terminate() | Escalate to thread.terminate() if wait times out. Guarantees no leak but risky for parser holding SDK state. | |
| wait(5000) then proceed | Longer grace for slow LLM calls, then proceed (no terminate). | |

**User's choice:** wait(3000) then proceed
**Notes:** No thread.terminate() — best-effort, never block the user from quitting.

---

## update_scene refactor depth

### Q1 — Refactor reach

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal (viewport + tree) | update_scene() on ViewportPanel + SceneTreeView only; New/Open/LLM-accept stop disrupting docks. undo/redo keep calling _refresh_viewport_and_tree (now safe). | ✓ |
| Broader (+ undo/redo + form) | Also direct update_scene() on undo/redo and fold PropertyForm into in-place update. Smoother undo but more code + undo-stack interaction. | |

**User's choice:** Minimal (viewport + tree)
**Notes:** Smallest change that closes bug #3; lowest risk. Broader refactor deferred unless undo/redo flicker reported.

---

## objectName + test approach

### Q1 — objectName enforcement (SC#4)

| Option | Description | Selected |
|--------|-------------|----------|
| Introspection test | pytest builds EditorWindow offscreen, asserts all QDockWidget children have non-empty unique objectName. | ✓ |
| Call-site guard helper | _register_dock wrapper asserts objectName before addDockWidget. Stronger but wraps every call. | |
| Both | Call-site helper + introspection test backstop. | |

**User's choice:** Introspection test
**Notes:** Non-invasive regression guard; runs in existing test suite.

### Q2 — Bug-fix verification (SC#1/#2/#3)

| Option | Description | Selected |
|--------|-------------|----------|
| Offscreen + mock slow parser | Offscreen QApplication; dock round-trip via API; close-mid-call via monkeypatched slow parser. Headless CI-friendly. | |
| Offscreen + real gated call | Offscreen dock round-trip; close-mid-call uses real short provider call skipif-no-key. Closer to real but flaky/skipped without keys. | ✓ |
| Manual only | No automated GUI-state tests. Fastest now but bug #3 needs an automated guard. | |

**User's choice:** Offscreen + real gated call
**Notes:** Real provider path verified when keys present.

### Q3 — SC#3 backstop without keys (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Real-gated only | Keep only the real-gated close-mid-call test (skips without key). SC#3 unguarded without keys. | |
| Real-gated + mock backstop | Real-gated primary + mock-slow-parser test that ALWAYS runs offscreen as SC#3 regression backstop. | ✓ |

**User's choice:** Real-gated + mock backstop
**Notes:** Mock guards teardown mechanics even without keys; real guards the true provider path. Belt-and-suspenders.

---

## Claude's Discretion

- Exact objectName strings for new docks (follow `dock_*` convention).
- DockStateManager internal shape; aboutToClose as plain Signal vs registry mixin — implementer's choice so long as the D-04 contract holds.
- Test file naming/placement (follow `tests/test_gui_scaffold.py` offscreen pattern).
- Status-bar wording on Reset Layout / close.

## Deferred Ideas

- "Restore Saved Layout" separate menu item — future UX nicety, not this phase.
- Hardcoded rebuild as primary reset — rejected (snapshot primary), kept as D-01 fallback only.
- thread.terminate() force-kill on timeout — rejected (SDK-state risk).
- Broader update_scene refactor (PropertyForm in-place + direct undo/redo update_scene) — deferred unless undo/redo flicker reported.
- Duplicated `_refresh_recent_menu` fix — Phase 48 (GUI-17), NOT Phase 41. The v0.7.0 research SUMMARY's older draft mentioned folding it in, but the final ROADMAP/REQUIREMENTS assigns GUI-17 to Phase 48.