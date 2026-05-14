---
phase: 20-real-surgical-assets
plan: 04
subsystem: assets
tags: [assets, cli, download, mesh, typer]
dependencies:
  requires: []
  provides: [download_meshes, list_local_meshes, CLI assets commands]
  affects: [cli.py, download.py, assets/meshes/]
tech-stack:
  added: []
  patterns: [Typer sub-app, optional HTTP client fallback]
key-files:
  created: [src/surg_rl/assets/download.py]
  modified: [src/surg_rl/cli.py]
decisions:
  - "Placeholder example.com URLs for all 13 meshes until real dataset URLs provided"
  - "HTTP client selection: try requests first, fall back to httpx"
  - "assets download requires explicit user flags (--instruments, --organs, --all)"
  - "assets info lists all 13 tracked meshes with present/missing status"
metrics:
  duration: "~5min"
  completed_date: 2026-05-14
---

# Phase 20 Plan 04: Mesh Download CLI Commands Summary

**One-liner:** CLI commands for downloading real surgical instrument and organ OBJ meshes from configurable URLs with explicit user consent and graceful error handling for missing HTTP libraries.

## Summary

Added two new Typer CLI commands under a `surg-rl assets` sub-app group. The `download` command fetches OBJ mesh files from configurable public dataset URLs (defaulting to example.com placeholders) to `assets/meshes/`. The `info` command lists which meshes are available for download vs. already present locally. Both commands require explicit user action — no automatic downloads. The download module gracefully handles missing `requests` or `httpx` HTTP clients with clear install hints.

Created `src/surg_rl/assets/download.py` with `download_meshes()`, `list_local_meshes()`, and `check_mesh_available()` functions, plus `DEFAULT_MESH_URLS` (13 entries: 9 instruments + 4 organs), `ALL_INSTRUMENT_NAMES`, and `ALL_ORGAN_NAMES` constants.

## Tasks Executed

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 | Create download.py with mesh download and listing functions | ✅ | `590c750` |
| 2 | Add assets download and assets info CLI commands | ✅ | `47cf26e` |

## Verification

- `PYTHONPATH=src python -c "from surg_rl.assets.download import ..."` — all functions and constants verified
- `PYTHONPATH=src python -c "from surg_rl.cli import app; ..."` — Typer CliRunner confirms `assets --help`, `assets info`, and `assets download` all work correctly
- `PYTHONPATH=src python -m surg_rl.cli assets --help` — CLI invoked via module entrypoint works
- Full test suite (`pytest tests/`) has a pre-existing environment issue (pydantic-core version mismatch 2.46.3 vs 2.46.4) unrelated to this plan's changes

## Deviations from Plan

### Out-of-scope discoveries logged to deferred-items.md

- **Pydantic-core version mismatch:** The installed `pydantic-core` 2.46.4 is incompatible with `pydantic` which requires 2.46.3. This is a pre-existing environment issue, not caused by this plan's changes, and is out of scope.

Otherwise: None — plan executed exactly as written.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: network-ingress | src/surg_rl/assets/download.py | HTTP download from remote URLs — documented in plan threat model (T-20-05), placeholder URLs mitigate until real dataset URLs are configured |

## Known Stubs

- `DEFAULT_MESH_URLS` uses `example.com` placeholder URLs for all 13 meshes — intentional per plan design (real dataset URLs to be configured later by users via env/config). Not a gap; the mechanism is complete.

## Self-Check

- [x] `src/surg_rl/assets/download.py` exists and verified
- [x] Commit `590c750` found in git log
- [x] Commit `47cf26e` found in git log
- [x] CLI commands registered and functional

## Self-Check: PASSED

All files and commits verified.
