---
phase: 39
plan: 02
subsystem: assets-licensing
tags: [adr, licensing, organ-mesh, documentation, assets]
requires: [ASET-01, ASET-02, ASET-03, ASET-04, ASET-05]
provides: [ASET-06, adr-template, organ-mesh-default-decision]
affects: [docs/adr/, future-asset-phases]
tech-stack:
  added: []
  patterns: [MADR (Markdown Any Decision Record), 4-digit zero-padded ADR numbering]
key-files:
  created:
    - docs/adr/0001-organ-mesh-licensing.md
    - docs/adr/README.md
  modified: []
decisions:
  - Procedural generation is the DEFAULT organ-mesh source for surg-rl (status: accepted)
  - SurgToolLoc is REJECTED as an organ-mesh source on dual grounds — modality mismatch (primary) + licensing incompatibility (secondary)
  - MADR format adopted as the repo's ADR template; docs/adr/ is the canonical ADR directory
  - Only the public challenge-guidelines page is cited for the SurgToolLoc non-commercial clause; the gated dataset EULA is explicitly NOT quoted
metrics:
  duration: ~12m
  completed: 2026-06-27
  tasks: 2
  files: 2
status: complete
---

# Phase 39 Plan 02: Organ-Mesh Licensing ADR Summary

Recorded the repository's first Architecture Decision Record (ADR-0001) closing
the organ-mesh licensing question (ASET-06): procedural generation is the
default organ-mesh source, and the SurgToolLoc dataset is rejected on dual
grounds — modality mismatch (primary) and MICCAI/EndoVis challenge-guidelines
licensing incompatibility (secondary), with both public URLs cited and clause
2 quoted verbatim for auditability.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create docs/adr/0001-organ-mesh-licensing.md (MADR) | 5aa95fd | docs/adr/0001-organ-mesh-licensing.md |
| 2 | Create docs/adr/README.md ADR index | 106e32b | docs/adr/README.md |

## What Was Built

### docs/adr/0001-organ-mesh-licensing.md

MADR-format ADR (status: accepted) with the required sections in order:
Title heading, metadata block (Date / Status / Deciders / Tags), Context,
Considered Options (3 options — procedural generation default,
SurgToolLoc rejected, other public repositories as future candidates),
Decision Outcome, Rationale (PRIMARY modality mismatch + SECONDARY
licensing incompatibility, both cited), Consequences (positive + negative),
References (two public URLs + arXiv overview paper + ASET-06 + CLAUDE.md).

Key auditability tokens present (SC#5 grep gate):
- `challenge-guidelines` (literal)
- `data-description` (literal)
- `neither pass it on to a third party nor use it for any publication or for commercial uses` (verbatim clause 2, single-line)
- `modality` and `endoscopic` (PRIMARY rationale markers)
- `procedural generation` (default) and `rejected` (SurgToolLoc disposition)
- `Status: accepted`

Both public URLs cited in References:
- https://surgtoolloc23.grand-challenge.org/challenge-guidelines/
- https://surgtoolloc23.grand-challenge.org/data-description/

### docs/adr/README.md

Short ADR directory index page: H1 title, one-paragraph intro stating ADRs
record significant decisions and that ADR-0001 is the repo's first, a MADR
format-convention note (4-digit zero-padded numbering, metadata block +
sections), and a 4-column table (`ADR | Title | Status | Date`) with a
single row linking `0001` to `./0001-organ-mesh-licensing.md`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Verbatim clause text wrapped across blockquote lines**
- **Found during:** Task 1 verification (SC#5 grep gate)
- **Issue:** The verbatim clause 2 text and clause 13 text were initially
  split across three blockquote lines for readability. The plan's SC#5
  acceptance gate uses `grep -F` against the single-line phrase
  `neither pass it on to a third party nor use it for any publication or for commercial uses`,
  which does not match across line breaks.
- **Fix:** Collapsed both blockquote clauses to single lines so the
  verbatim phrase is grep-matchable as written. Clause text remains
  verbatim — only line wrapping changed.
- **Files modified:** docs/adr/0001-organ-mesh-licensing.md
- **Commit:** included in 5aa95fd (pre-commit fix, same task)

No other deviations. Plan executed as written.

## Threat Model Compliance

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-39-06 (Info Disclosure — private EULA quoted) | mitigate | Mitigated — ADR quotes only the public challenge-guidelines page; the gated EULA is explicitly noted as non-citable, with the `isi.challenges@intusurg.com` contact mentioned only to document the gate (per plan action step 6), NOT quoted. The EULA text itself is absent. |
| T-39-07 (Info Disclosure — dataset-sample links) | mitigate | Mitigated — References section contains only the two public challenge-site URLs; no downloadable dataset samples or participant-only artifacts are linked. |
| T-39-08 (Repudiation — non-auditable decision) | mitigate | Mitigated — clause 2 quoted verbatim on a single grep-matchable line AND both public URLs cited; SC#5 grep gate passes. |
| T-39-09 (Spoofing/Tampering — misrepresent SurgToolLoc as organ geometry) | mitigate | Mitigated — Rationale PRIMARY section states "There are no organ meshes in SurgToolLoc" and cites the data-description URL; the modality is explicitly named as endoscopic video + tool-presence labels. |

No new threat surface introduced beyond the plan's threat model.

## Known Stubs

None. The ADR and README are complete documentation artifacts; no stubs,
placeholders, TODOs, or unwired data sources.

## TDD Gate Compliance

N/A — this plan has `type: execute` (not `tdd`); no TDD RED/GREEN/REFACTOR
gate applies. Both tasks are documentation creation with static grep-based
acceptance gates, all of which pass.

## Self-Check

- ADR file exists: FOUND (docs/adr/0001-organ-mesh-licensing.md)
- README index exists: FOUND (docs/adr/README.md)
- Commit 5aa95fd (Task 1): FOUND
- Commit 106e32b (Task 2): FOUND
- No file deletions in either task commit: confirmed
- No unexpected untracked files: confirmed (only pre-existing
  `.planning/research/.cache/`)

## Self-Check: PASSED

## Success Criteria

- SC#4 (ADR records organ-mesh licensing decision with cited rationale):
  MET — docs/adr/0001-organ-mesh-licensing.md records procedural
  generation as default and SurgToolLoc as rejected, with modality
  mismatch (primary) and MICCAI/EndoVis non-commercial clause (secondary)
  both cited.
- SC#5 (ADR cites public challenge-guidelines URL AND quotes verbatim
  clause text for auditability): MET — both public URLs cited in
  References, clause 2 quoted verbatim on a single grep-matchable line.
- ASET-06 closed: MET — requirement ASET-06 in REQUIREMENTS.md is
  addressed by this ADR and will be marked complete via
  `requirements mark-complete`.

## Artifacts

- `docs/adr/0001-organ-mesh-licensing.md` — MADR-format ADR (status: accepted)
- `docs/adr/README.md` — ADR directory index (ADR-0001 row, status accepted,
  date 2026-06-27, link to the ADR file)