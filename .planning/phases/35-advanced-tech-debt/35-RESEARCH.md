---
gsd_research_version: 1.0
phase: 35
topic: organ-mesh-licensing
status: complete
---

# Organ Mesh Licensing Research Spike

## Objective

Identify candidate sources for realistic human organ meshes that can be used in
surgical robotics simulation, assess their license terms, and recommend whether
to adopt, adapt, or procedurally generate assets for the v0.6.0 milestone.

## Candidates

### 1. SARAS/SurgToolLoc multi-task dataset

**Source:** University of Verona / SARAS project surgical tool and scene data.  
**License:** Typically distributed under academic/research terms with
restrictions on commercial use and redistribution. Exact license varies by
specific release; most versions are **not** permissive open source.

**Pros:**
- Real surgical scenes and tool trajectories.
- High relevance to the target domain.

**Cons:**
- License likely prohibits commercial use and broad redistribution.
- Organ/tissue geometry is often secondary to tool localization; extracting
clean, watertight organ meshes may require significant cleanup.
- No clear CC0/MIT path.

**Verdict for v0.6.0:** Not recommended as the primary source unless a specific
permissively licensed subset is identified and documented.

### 2. MakeHuman

**Source:** `http://www.makehumancommunity.org/`  
**License:** CC0 for exported assets (public domain dedication) when using the
official export targets; the MakeHuman application itself is AGPLv3.

**Pros:**
- CC0 export means no attribution or share-alike requirements for the mesh
assets themselves.
- Procedural parametric human body generation allows coarse organ placement via
proxy geometry.
- Can produce anatomically inspired base meshes without legal encumbrance.

**Cons:**
- MakeHuman exports a full human body, not detailed internal organs; internal
anatomy must be approximated or modeled separately.
- High-quality organ meshes require additional sculpting/retopology.
- The application is AGPLv3, but the exported CC0 assets are separable.

**Verdict for v0.6.0:** Strong candidate for external body shell / proxy
anatomy, with the understanding that internal organs need additional work.

### 3. BodyParts3D / Anatomography (Life Science Databases Center, Japan)

**Source:** `https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html`  
**License:** CC Attribution 2.1 Japan (CC BY 2.1 JP) — requires attribution and
permits non-commercial use. Some derived datasets may carry additional
restrictions.

**Pros:**
- Realistic, segmented human organ models derived from CT/mri data.
- Direct relevance to surgical simulation.

**Cons:**
- CC BY requires prominent attribution in docs and any redistributed assets.
- The original license has a non-commercial flavor in some interpretations;
commercial use must be carefully evaluated.
- Files are in specialized formats (MHA/RAW/VOI) and require conversion to
OBJ/VTK for the simulator pipeline.

**Verdict for v0.6.0:** Viable for research/non-commercial demos if attribution
is acceptable; risky for a permissively licensed project redistributing assets.

## License Comparison

| Source | License | Commercial OK | Redistribute OK | Attribution | Organs Quality |
|---|---|---|---|---|---|
| SurgToolLoc | Academic / non-commercial | Likely no | Restricted | Required | Medium |
| MakeHuman export | CC0 | Yes | Yes | None | Low-Medium (body shell) |
| BodyParts3D | CC BY 2.1 JP | Ambiguous | Yes (with attribution) | Required | High |

## Recommendation

**Defer the organ-mesh asset decision to v0.6.0.** The v0.5.0 milestone should
not commit to a specific licensed organ-mesh source. Instead:

1. Keep the existing procedural primitive fallback in `scene_builder` as the
   default asset path.
2. For v0.6.0, evaluate either:
   - Procedural generation of organ-like shapes via the existing `trimesh` /
     tetgen pipeline, keeping the project fully self-contained and permissively
     licensed; or
   - Adopting MakeHuman CC0 body-shell exports plus internally modeled internal
     organ proxies, with a clear attribution page if BodyParts3D-derived assets
     are later incorporated.
3. If a permissively licensed surgical dataset is discovered, document it in a
   follow-up research spike before committing to import.

## Action Items

- v0.5.0: No new organ mesh assets are added; only this research doc.
- v0.6.0: Re-open the asset decision with a cost/benefit analysis of
  procedural generation vs. CC0/MakeHuman vs. BodyParts3D-with-attribution.
- Update `STATE.md` to record that the organ-mesh licensing question is
  researched and deferred to v0.6.0.
