# Phase 20: Real Surgical Assets — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 20-real-surgical-assets
**Areas discussed:** Mesh source strategy, OBJ to URDF/MJCF pipeline, Organ OBJ to tetgen path, Fallback behavior & granularity

---

## Mesh source strategy

### Question 1: Where do the 11 instrument and 4 organ OBJ meshes come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Procedural trimesh primitives | Procedurally generated OBJs — no external files | ✓ |
| Download from public dataset | Fetch from surgtoolloc, Thingiverse CC0 | |
| User-provided only | Scene JSON/YAML specifies paths | |
| Bundle in repo | Real meshes in git | |

**User's choice:** Procedural trimesh primitives as default fallback, optional public dataset download if internet available. User should control what gets downloaded.

### Question 2: How should the optional public dataset download work?

| Option | Description | Selected |
|--------|-------------|----------|
| CLI download command | `surg-rl assets download --instruments ...` | ✓ |
| Lazy auto-download | Silent download on first load | ✓ (combined) |

**User's choice:** Both — CLI to explicitly download, plus lazy prompt on first load asking whether to download if mesh not found and internet available.

---

## OBJ to URDF/MJCF pipeline

### Question 1: How does trimesh OBJ data flow into SceneBuilder?

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory geometry transfer | Raw NumPy arrays to SceneBuilder | |
| Generate intermediate URDF file | Save as URDF, both backends load | ✓ |

**User's choice:** Generate intermediate URDF file

### Question 2: What collision geometry should trimesh extract from instrument OBJs?

| Option | Description | Selected |
|--------|-------------|----------|
| Convex hull (Recommended) | Simple, guaranteed convex | |
| V-HACD decomposition | Multi-part convex for concave parts | ✓ |
| Bounding boxes | Fast, very approximate | |

**User's choice:** V-HACD decomposition

### Question 3: Separate visual mesh from collision mesh?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate visual + collision | Visual = decimated OBJ, Collision = V-HACD | ✓ |
| Single decomposed mesh | Both use V-HACD output | |

**User's choice:** Separate visual + collision

### Question 4: Should instrument URDFs be single-link or multi-link?

| Option | Description | Selected |
|--------|-------------|----------|
| Single-link | One rigid body per instrument | |
| Multi-link articulated | Shaft + jaws for forceps, etc. | ✓ |

**User's choice:** Multi-link articulated

### Question 5: Where do multi-link URDF definitions come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Type-based templates | Code-generated per InstrumentType | ✓ |
| User-supplied URDFs | External URDF files | |

**User's choice:** Type-based templates

---

## Organ OBJ to tetgen path

### Question 1: How does an organ OBJ enter the tetgen pipeline?

| Option | Description | Selected |
|--------|-------------|----------|
| trimesh → tetgen | Direct surface mesh → tetgen | |
| trimesh → STL → tetgen | STL intermediate format | ✓ |
| trimesh → VTK (skip tetgen) | VTK format, bypasses tetgen | |

**User's choice:** trimesh → STL → tetgen

### Question 2: What surface quality validation/repair before tetgen?

| Option | Description | Selected |
|--------|-------------|----------|
| Validate + reject broken | Check watertightness, error if broken | |
| Auto-repair with trimesh | Fill holes, remove degenerates | ✓ |
| Pass through to tetgen | Let tetgen handle it | |

**User's choice:** Auto-repair with trimesh

---

## Fallback behavior & granularity

### Question 1: What shape replaces a missing mesh?

| Option | Description | Selected |
|--------|-------------|----------|
| Existing primitive field | Use InstrumentConfig.primitive | |
| Type-based procedural (trimesh) | Capsule/ellipsoid per type | ✓ |

**User's choice:** Type-based procedural via trimesh

---

## OpenCode's Discretion

- Exact trimesh procedural primitive geometry for each instrument type
- V-HACD resolution/quality parameters
- STL export resolution and tetgen quality hints
- trimesh auto-repair pipeline details
- Download URL configuration
- Warning message wording for fallback cases
- URDF template implementation details
