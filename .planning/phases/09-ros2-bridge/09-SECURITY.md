---
phase: 09
slug: ros2-bridge
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-03
---

# Phase 09 — Security

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| External ROS2 nodes → Ros2BridgeNode subscriber | Untrusted DDS data on `/surg_rl/commands` topic | Float64MultiArray commands |
| multiprocessing Process → main process | Bridge process queue data — process isolation protects memory | NumPy action arrays |
| Ros2BridgeNode subscriber → EnvironmentController | External commands injected into RL action pipeline | Action vector |
| SB3 checkpoint file → TrajectoryReplay | Untrusted pickle data (research tool, trusted internally) | Serialized model |
| CLI command args → Ros2BridgeConfig | User-provided --config file path | YAML configuration |
| CLI args → ros2-replay | User-provided --checkpoint file | SB3 zip checkpoint |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-09-01 | Spoofing | `Ros2BridgeNode._on_command` | mitigate | Dimension check: `len(data) != len(joint_names)` → zero action / warn | closed |
| T-09-02 | Tampering | `Ros2BridgeNode.publish_state` | mitigate | `np.isfinite()` validation; raise raise (raise ValueError) or sanitize (np.nan_to_num) | closed |
| T-09-03 | Info Disclosure | `Ros2BridgeNode.publish_state` | accept | JointState on ROS2 DDS intentional for research tool | closed |
| T-09-04 | DoS | `Ros2BridgeNode._on_command` | mitigate | `multiprocessing.Queue(maxsize=1)` keep-latest; full → discard → overwrite | closed |
| T-09-05 | Elevation | Bridge process boundary | accept | OS process isolation sufficient for research tool | closed |
| T-09-06 | Tampering | `SurgicalEnv.step()` action pipeline | mitigate | Two-layer validation: dimension check + NaN/Inf check before simulator | closed |
| T-09-07 | DoS | Bridge Process zombie | mitigate | terminate→join(5s)→kill→join(2s) escalation; daemon=True; close() before sim cleanup | closed |
| T-09-08 | Spoofing | `EnvironmentController.get_action` | mitigate | Real/sim mode flag; explicit `set_real_robot_mode(True)` API call | closed |
| T-09-09 | Tampering | `TrajectoryReplay.__init__` | mitigate | Validate `0 < speed <= 1.0`; reject with ValueError | closed |
| T-09-10 | DoS | `run_replay` loop | mitigate | `max_steps` bounds loop; `terminate()` clean exit; KeyboardInterrupt caught | closed |
| T-09-11 | Spoofing | `ros2-bridge --config` | mitigate | Config validated by Ros2BridgeConfig Pydantic v2 model | closed |
| T-09-12 | Tampering | `ros2-replay --checkpoint` | accept | SB3 checkpoint trusted internally (research artifact) | closed |
| T-09-13 | Info Disclosure | CLI help output | accept | Help text shows topic names intentionally | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| A-09-01 | T-09-03 | JointState data on ROS2 DDS topic is intentional — research tool, not clinical device | GSD | 2026-05-03 |
| A-09-02 | T-09-05 | Bridge runs as separate multiprocessing.Process — OS process isolation sufficient; no privilege escalation path | GSD | 2026-05-03 |
| A-09-03 | T-09-12 | SB3 checkpoint is a research artifact — trusted internally; pickle safety relies on user not using untrusted checkpoints | GSD | 2026-05-03 |
| A-09-04 | T-09-13 | Help text shows topic names — these are configurable endpoints, intentional disclosure | GSD | 2026-05-03 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-03 | 13 | 13 | 0 | OpenCode (gsd-security-auditor) |

---

## Gap Closure Verification (09.1)

| Gap | Threat Reference | Status |
|-----|-----------------|--------|
| CR-01: queue.Queue not process-safe | T-09-04, T-09-06 | FIXED — multiprocessing.Queue injected from parent |
| WR-01: frame_id hardcoded | T-09-03 | WIRED — frame_id from config through node to publish |
| WR-02: qos_profile unused | T-09-04 | APPLIED — qos_profile_sensor_data at publisher creation |
| WR-04: Error strategies hardcoded | T-09-01, T-09-02 | CONFIGURABLE — raise/sanitize and zero/warn branching |
| WR-05: on_missing_topic missing | — | IMPLEMENTED — startup liveness check |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-03
