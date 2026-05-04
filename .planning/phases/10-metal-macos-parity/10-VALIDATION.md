---
phase: 10-metal-macos-parity
total_requirements: 7
covered: 7
partial: 0
missing: 0
nyquist_compliant: true
audited: 2026-05-03
---

# Validation Strategy — Phase 10: Metal GPU Compute + macOS Test Parity

## Test Infrastructure

| Tool | Config | Command |
|------|--------|---------|
| pytest | `pytest.ini`, `pyproject.toml` | `PYTHONPATH=src pytest tests/ -m "not integration"` |

## Requirement Coverage Map

| Requirement | Status | Test File | Test Function(s) | Verified |
|-------------|--------|-----------|-------------------|----------|
| METAL-01 | COVERED | `tests/test_gpu_integration.py` | `test_get_torch_device_auto`, `test_get_torch_device_passthrough` | yes |
| METAL-02 | COVERED | `tests/test_gpu_integration.py` | `test_metal_memory_info_on_macos`, `test_metal_memory_info_on_non_macos` | yes |
| METAL-03 | COVERED | `tests/test_gpu_integration.py` | `test_mps_fallback_warns_once` | yes |
| MACOS-01 | COVERED | `tests/test_ci_config.py` | `test_ci_has_macos_runner`, `test_macos_runner_python_311`, `test_ci_fail_fast_disabled` | yes |
| MACOS-02 | COVERED | `tests/test_simulators.py` | `test_pybullet_soft_body_state_roundtrip` (xfail removed) | yes |
| MACOS-03 | COVERED | `tests/test_ci_config.py`, `tests/unit/test_rendering.py` | `test_ci_has_mjpython_step`, CI guard on `test_macos_raises_without_mjpython` | yes |
| MACOS-04 | COVERED | `tests/test_ci_config.py`, `.planning/REQUIREMENTS.md` | `test_ci_ignores_ros2_on_macos`, Out of Scope docs | yes |

## Per-Task Map

| Plan | Task | Requirement(s) | Automated | Status |
|------|------|---------------|-----------|--------|
| 10-01 | task 1: resolve MPS device string | METAL-01, METAL-02 | `test_get_torch_device_auto` | PASSED |
| 10-01 | task 2: wire MPS into RLlib | METAL-01 | import verification | PASSED |
| 10-01 | task 3: MPS memory info | METAL-02 | `test_metal_memory_info_on_macos` | PASSED |
| 10-02 | task 1: MPS logging | METAL-02 | covered by task above | PASSED |
| 10-02 | task 2: MPS fallback | METAL-03 | `test_mps_fallback_warns_once` | PASSED |
| 10-02 | task 3: MPS-specific tests | METAL-01..03 | 5 tests in `test_gpu_integration.py` | PASSED |
| 10-03 | task 1: macOS CI matrix | MACOS-01, MACOS-03 | `test_ci_has_macos_runner`, `test_ci_has_mjpython_step` | PASSED |
| 10-03 | task 2: rendering CI guard | MACOS-03 | `tests/unit/test_rendering.py` CI guard | PASSED |
| 10-04 | task 1: remove xfail | MACOS-02 | `test_pybullet_soft_body_state_roundtrip` | PASSED |
| 10-04 | task 2: verify full suite | MACOS-02 | full `test_simulators.py` suite | PASSED |
| 10-04 | task 3: ROS2 exclusion | MACOS-04 | `test_ci_ignores_ros2_on_macos`, REQUIREMENTS.md | PASSED |

## Manual-Only

None — all requirements have automated verification.

## Sign-Off

- [x] All requirements have automated verification
- [x] No manual-only gaps remain
- [x] Test suite: 5 new CI config tests + 5 Metal tests + 1 xfail removal

---

## Validation Audit 2026-05-03

| Metric | Count |
|--------|-------|
| Gaps found | 1 (MACOS-01 — no CI config test) |
| Resolved | 1 (`tests/test_ci_config.py` with 5 tests) |
| Escalated | 0 |
