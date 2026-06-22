# Organ Mesh Licensing Research Spike

## Objective

Identify candidate sources of realistic, reusable 3D organ meshes for the
surgical-robotics simulation pipeline and record their license constraints so
that v0.6.0 can choose a procurement or generation strategy without revisiting
this discovery work.

Scope: static polygonal organ models (liver, kidney, spleen, stomach, etc.)
that can be imported as `.obj`/`.vtk`/`.stl` and used as tissue/scene props.
Animation, haptics, and patient-specific segmentation are out of scope for
this spike.

## Candidates

### 1. SurgToolLoc / SARAS

The [SurgToolLoc challenge](https://surgtoolloc.grand-challenge.org/) and the
related SARAS project publish surgical scene data and tool models for research
use. Their asset licenses are typically academic / research-only and often
prohibit commercial redistribution.

- **Typical license:** research-only, non-commercial
- **Commercial use:** generally not permitted
- **Redistribution:** restricted
- **Attribution:** required per dataset terms
- **Organ quality:** low to medium; the focus is surgical tools and endoscopic
  video frames, not high-fidelity organ meshes.

### 2. MakeHuman

[MakeHuman](http://www.makehumancommunity.org/) exports body proxies under CC0.
The MakeHuman *application* is AGPLv3, but exported `.obj`/`.mhx2` assets are
explicitly released as CC0 and can be used without attribution or license
contamination concerns in downstream projects.

- **License:** CC0 for exported meshes
- **Commercial use:** yes
- **Redistribution:** yes
- **Attribution:** not required
- **Organ quality:** low for internal organs; MakeHuman is a human-body shell.
  Liver, kidneys, etc. would need to be modeled or sourced separately and then
  fitted to the body proxy.

### 3. BodyParts3D / Anatomography

The BodyParts3D dataset (hosted by the Database Center for Life Science and
linked from the Anatomography project) provides segmented, high-quality 3D organ
models derived from medical imaging. The dataset is released under
CC BY 2.1 JP.

- **License:** CC BY 2.1 JP
- **Commercial use:** yes, with attribution
- **Redistribution:** yes, with attribution and same-license considerations for
  derivatives
- **Attribution:** required
- **Organ quality:** high; organs are segmented from real CT/MRI data and are
  suitable as scene props after format conversion and decimation.

## License Comparison

| Source | License | Commercial OK | Redistribute OK | Attribution | Organs Quality |
|--------|---------|---------------|-----------------|-------------|----------------|
| SurgToolLoc / SARAS | Research / non-commercial | No | Restricted | Yes | Low |
| MakeHuman (exported) | CC0 | Yes | Yes | No | Low (body shell only) |
| BodyParts3D / Anatomography | CC BY 2.1 JP | Yes (with attribution) | Yes (with attribution) | Yes | High |

## Recommendation

Defer the organ-mesh asset decision to **v0.6.0**.

For the remainder of v0.5.0, keep the existing **procedural fallback geometry**
as the default tissue representation. Procedural meshes avoid all licensing
uncertainty, keep the repository self-contained, and are sufficient for the
current RL training and editor workflows.

In v0.6.0, re-evaluate three paths:

1. **Procedural generation** — continue investing in `scene_builder` primitive
   and tetrahedral-mesh generation; no external license needed.
2. **MakeHuman CC0 proxies** — if the project needs a visible patient body shell,
   import MakeHuman-exported CC0 meshes and model internal organs on top.
3. **BodyParts3D with attribution** — if anatomical fidelity is required, use
   CC BY 2.1 JP organ meshes and add the required attribution to the README and
   packaging metadata.

Avoid SurgToolLoc/SARAS assets for any commercial or redistributable build
unless the project negotiates an explicit commercial license with the dataset
maintainers.

## Action Items

- **v0.5.0:** Do not add any external organ meshes to the repository. Ship this
  research document only.
- **v0.6.0:** Re-open the decision when milestone planning begins; pick one of
  the three paths above and update `docs/research/organ-mesh-licensing.md` with
  the chosen license and attribution notice.
