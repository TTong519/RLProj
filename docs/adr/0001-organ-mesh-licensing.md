# ADR-0001: Organ-mesh licensing — procedural generation as default, SurgToolLoc rejected

- Date: 2026-06-27
- Status: accepted
- Deciders: surg-rl maintainers
- Tags: assets,licensing,organ-mesh

## Context

v0.4.0 Phase 20 introduced deformable-tissue simulation and required four
organ OBJ meshes (liver, kidney, spleen, gallbladder-class structures) as
inputs to the volumetric cutting and soft-tissue deformation modules. The
repository's `assets/` directory ships **no real mesh files** — this is a
documented known limitation (see `CLAUDE.md` → "Known Limitations: `assets/`
has no real mesh files; simulators use primitive shape fallbacks"). The
`scene_builder.py` fallback path generates OBJ primitives at runtime, and
the deformable modules currently rely on parametric / procedural geometry.

The asset track carried forward six requirement items (ASET-01 through
ASET-05, plus this ADR closing ASET-06) that progressively constrained what
organ-mesh source the project may adopt:

- ASET-01..03 — established that any organ-mesh source must be
  license-compatible with the project's MIT distribution model and must not
  introduce a redistribution wall.
- ASET-04..05 — confirmed that no permissively-licensed, validated public
  organ-mesh dataset had been identified at the time of those phases; the
  question was deferred to this ADR.
- ASET-06 — requires that the organ-mesh licensing decision be **recorded as
  an ADR** so future asset work has a single, auditable source of truth and
  the question does not relitigate on every subsequent asset phase.

This ADR closes that loop: it records the default organ-mesh source
(procedural generation), the rejected alternative (SurgToolLoc), and the
dual grounds for rejection (modality mismatch — primary; licensing
incompatibility — secondary). It is the cite-able closure artifact for the
asset track.

## Considered Options

### Option 1 — Procedural generation (trimesh primitives / parametric organ meshes) — DEFAULT

Generate organ geometry at runtime from parametric descriptions (e.g.
trimesh primitives, analytic surfaces, signed-distance-field-derived
isosurfaces) or from procedurally-deformed primitive shapes. This is the
approach already in use via `scene_builder.py`'s OBJ-primitive fallback and
is consistent with the project's existing "no real asset files" posture.

### Option 2 — SurgToolLoc dataset — REJECTED

The SurgToolLoc 2023 dataset published by Intuitive Surgical as part of
the MICCAI / EndoVis sub-challenge series. This option is rejected on dual
grounds documented under `## Rationale` below: the dataset is not organ
geometry at all (modality mismatch — primary), and its challenge
guidelines prohibit commercial use and redistribution (licensing
incompatibility — secondary).

### Option 3 — Other public organ-mesh repositories (future candidates)

Public organ-mesh repositories such as the KAIST Abdomen atlas, MeshLab
organ-model collections, or permissively-licensed (CC0 / CC BY / MIT)
anatomical reconstructions. These are **out of scope for this ADR** and are
noted only as future candidates if photorealism requirements later
override the procedural-generation default. Any future adoption of such
a dataset must itself be recorded as a follow-up ADR with its own
licensing audit.

## Decision Outcome

**Procedural generation is the DEFAULT organ-mesh source for surg-rl.**

**SurgToolLoc is REJECTED** as an organ-mesh source, on the dual grounds
documented in `## Rationale`.

Decision status: `accepted`.

## Rationale

SurgToolLoc is rejected on two independent grounds. **Both must be cited**
so that future asset work cannot relitigate the question by addressing
only one of them.

### PRIMARY — modality mismatch

SurgToolLoc is **24,695 endoscopic video clips** with **tool-presence
labels** for 14 tools across 4 robotic arms. It is **endoscopic video +
tool-presence labels, NOT organ geometry**. There are **no organ meshes**
in SurgToolLoc.

This modality fact is sourced from the public data-description page:
https://surgtoolloc23.grand-challenge.org/data-description/

Adopting SurgToolLoc as an organ-mesh source would be a category error:
the dataset does not contain the artifact class (organ OBJ / tetrahedral
meshes) that the v0.4.0 Phase 20 deformable-tissue modules require. No
amount of license-cleaning can recover organ geometry from a dataset that
does not contain it; the modality mismatch is therefore the **primary**
rejection rationale and is independent of any licensing concern.

### SECONDARY — licensing incompatibility

Even setting modality aside, SurgToolLoc is incompatible with the
project's MIT distribution model. The MICCAI / EndoVis challenge guidelines
prohibit commercial use and redistribution. Clause 2 of the public
challenge-guidelines page reads, verbatim:

> Your team will use the provided data only in the scope of the challenge and neither pass it on to a third party nor use it for any publication or for commercial uses.

This clause is sourced from the public challenge-guidelines page:
https://surgtoolloc23.grand-challenge.org/challenge-guidelines/

Clause 13 of the same page adds a publication embargo:

> The data used for SurgToolLoc 2023 can only be used for publication purposes after the results of this challenge have been submitted for publication.

The combination of "no commercial use" and "no pass-it-on to a third
party" is directly incompatible with:

- The project's MIT license, which permits commercial use and
  redistribution of derived artifacts.
- The project's distribution model, which ships `assets/` (and any future
  bundled mesh data) inside a public, commercially-usable repository.

### Public-source note (auditability)

The dataset-specific End-User License Agreement (EULA) is gated behind
a registration / agreement form (`isi.challenges@intusurg.com`) and is
**NOT publicly citable** — a future auditor cannot re-fetch it without
registering and agreeing to the form. The **public challenge-guidelines
page** is therefore the authoritative citable source for the
non-commercial / no-redistribution terms. This ADR quotes only the public
guidelines page and does **not** quote the private EULA. This follows
the guidance in `39-RESEARCH.md` Pitfall #6 (cite the public guidelines,
not the gated EULA).

## Consequences

### Positive

- **MIT-clean**: no external license dependency enters the project's
  distribution. The default organ-mesh source is generated in-house from
  parametric / analytic descriptions, so its output inherits the project's
  MIT license with no downstream encumbrance.
- **Reproducible**: procedural generation is deterministic given the
  parametric inputs; the build does not depend on fetching a remote
  dataset that could be retracted or re-licensed.
- **Matches the existing posture**: this decision is consistent with the
  already-documented `assets/` primitive-fallback approach in `CLAUDE.md`
  ("simulators use primitive shape fallbacks"). It does not introduce a
  new asset-acquisition workflow.
- **Auditable closure**: ASET-06 is satisfied; the asset track
  (ASET-01..06) has a single cite-able decision artifact and the
  SurgToolLoc question does not relitigate on every future asset phase.

### Negative

- **Lower photorealism**: parametric organ meshes are visually and
  geometrically simpler than validated real-anatomy reconstructions. The
  deformable-tissue modules will exercise procedural geometry rather than
  patient-specific anatomy.
- **Future revisit risk**: if a later phase requires validated
  organ geometry (e.g. for realistic resection-margin simulation), this
  ADR's Option 3 (public permissively-licensed organ-mesh repositories)
  becomes the next investigation. Any such adoption must be recorded as a
  follow-up ADR with its own licensing audit; this ADR does **not**
  pre-empt that future decision.

## References

- SurgToolLoc 2023 Challenge Guidelines (public) —
  https://surgtoolloc23.grand-challenge.org/challenge-guidelines/
- SurgToolLoc 2023 Data Description (public, confirms modality:
  24,695 endoscopic video clips + tool-presence labels, no organ meshes) —
  https://surgtoolloc23.grand-challenge.org/data-description/
- arXiv:2305.07152 — "Intuitive Surgical SurgToolLoc and SurgVU Challenges
  Results: 2022-2025" overview paper —
  https://arxiv.org/abs/2305.07152
- ASET-06 in `.planning/REQUIREMENTS.md` — the requirement this ADR closes.
- `CLAUDE.md` → "Known Limitations" — documents the existing
  `assets/` primitive-fallback posture this decision is consistent with.