
## Deferred: test_sim_step_worker.py flaky pause-resume test (Plan 01)

**Discovered during:** Plan 42-02 Task 3 full-suite sweep
**File:** tests/test_sim_step_worker.py::TestPauseResumeStepOne::test_pause_then_resume_advances_then_holds
**Issue:** Off-by-one (step_count 5 vs 4) when run alongside other editor tests.
The test passes consistently in isolation. The failure is a timing race between
the queued `set_paused(True)` signal and the accumulator's next `_tick` under
cross-test timing pressure (other EditorWindow instances + QThreads in the same
pytest session slow the worker thread's event-loop processing).
**Scope:** Plan 01 component (sim_step_worker.py / test_sim_step_worker.py — NOT
modified by Plan 02). Pre-existing flakiness, not a Plan 02 regression.
**Suggested fix (future phase):** increase the `_settle` wait in the test from
0.15s to 0.3s, or add a `processEvents` + `wait` loop that polls
`worker._paused` until True before asserting step_count.
