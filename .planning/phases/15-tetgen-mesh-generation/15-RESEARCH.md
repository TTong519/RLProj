# Phase 15: Tetgen Mesh Generation — Research

**Researched:** 2026-05-04
**Domain:** Tetrahedral mesh generation, TetGen C++ library Python wrappers
**Confidence:** HIGH

## Summary

This phase replaces VTK/PyVista-based tetrahedral mesh generation with tetgen — a battle-tested C++ library wrapped for Python. The dominant (and only meaningfully maintained) Python package is `tetgen` 0.8.4 from the PyVista project. It provides CFFI bindings to TetGen 1.6.0 and ships precompiled wheels for macOS arm64/x86_64 and Linux amd64/aarch64.

The critical discovery: **the NumPy array constructor path works without PyVista installed**. You pass `(n, 3)` vertex array and `(m, 3)` face array to `tetgen.TetGen()`, call `.tetrahedralize()`, and get back `(nodes_Nx3_float64, elems_Mx4_int32)` — exactly the format the project's existing `vtk_io.py` and `mesh_generation.py` already use. This means we can remove PyVista as a required dependency entirely.

File I/O (OBJ/STL) for the "luxury" path needs a lightweight parser. A minimal OBJ triangulated-mesh parser is ~15 lines of Python. For STL binary/ASCII, the `numpy-stl` package exists but adds another dep. The pragmatic path: parse OBJ in code (the project already generates OBJs itself), and document that STL/PLY/GLTF loading can use PyVista as an optional [meshing-io] extra.

**Primary recommendation:** Swap `pyvista.delaunay_3d()` for `tetgen.TetGen().tetrahedralize()` in `mesh_generation.py`'s `_try_external_tetrahedralization()`. Remove `pyvista` from `[meshing]` extras, add `tetgen>=0.8.4`. Preserve `vtk_io.py` API unchanged — tetgen outputs the same NumPy format that VTK already uses.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TETG-01 | Integrate `tetgen` Python package as primary tetrahedral mesh generator | ✅ `tetgen` 0.8.4 is the only maintained package; CFFI bindings, wheels for all target platforms, NumPy-native API |
| TETG-02 | Generate tetrahedral meshes from surface OBJ/STL inputs | ✅ Raw NumPy arrays from any parser work; lightweight OBJ parser is ~15 lines; STL needs numpy-stl or PyVista |
| TETG-03 | Remove VTK dependency from `[meshing]` extras; tetgen is platform-agnostic | ✅ `tetgen` only requires numpy; PyVista/VTK is completely optional |
| TETG-04 | Preserve existing `vtk_io.py` public API but redirect internals to tetgen | ✅ `vtk_io.py` already works on (vertices Nx3, tetrahedra Mx4) NumPy arrays — tetgen outputs exactly this format |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Mesh generation (tetrahedralization) | API / Backend | — | TetGen C++ library runs in-process; output is NumPy arrays consumed by simulators |
| Surface mesh I/O (OBJ/STL parsing) | API / Backend | CDN / Static | Input comes from generated assets or user-provided files; parsing happens pre-simulation |
| VTK file I/O (write/read) | API / Backend | — | Existing `vtk_io.py` is pure Python; persists generated meshes for caching/reuse |
| Mesh quality assessment | API / Backend | — | TetGen's `tetrahedralize()` returns quality metrics; no runtime tier involved |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `tetgen` | 0.8.4 | Tetrahedral mesh generation via TetGen 1.6.0 C++ | Only maintained Python wrapper; PyVista project; CFFI bindings; wheels for macos-arm64, macos-x86_64, linux-amd64, linux-aarch64 |
| `numpy` | ≥1.24.0 | Array contract between tetgen and project code | Already in project deps; tetgen's only hard dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `numpy-stl` | ≥3.0 | Parse binary/ASCII STL files to vertex/face arrays | When users provide STL input without PyVista present |
| `pyvista` | ≥0.43 | Full mesh I/O (OBJ/STL/PLY/GLTF) and visualization | Keep as optional [meshing-io] extra for power users; NOT in [meshing] |
| `pymeshfix` | ≥0.18.0 | Repair non-manifold surfaces before tetrahedralization | When input meshes have holes, non-manifold edges, or self-intersections |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `tetgen` (PyVista) | `pytetgen` v0.2.2 (standalone) | Last released 2021; no macos-arm64 wheels; unmaintained. Do not use. |
| `tetgen` (PyVista) | `tetgenpy` v0.1.0 | Last released 2021; single-version; no wheels; unmaintained. Do not use. |
| `tetgen` (CFFI) | Subprocess CLI | No standalone `tetgen` CLI typically installed; CFFI is faster and simpler |
| `numpy-stl` for STL | Hand-roll STL parser | Binary STL parsing has endianness, padding traps; numpy-stl is battle-tested |
| PyVista for OBJ | Hand-roll OBJ parser | Our OBJ parser is 15 lines for triangulated meshes; PyVista is massive overkill |

**Installation:**
```bash
pip install tetgen>=0.8.4
```

**Version verification (2026-05-04):**
```
tetgen 0.8.4         — latest release, May 4, 2026
  Wheels: cp310-cp312, macosx_arm64, macosx_x86_64, manylinux_aarch64, manylinux_x86_64, win_amd64
  Source: sdist available (requires cmake + C++ compiler)
  Dependencies: numpy (only)
  License: MIT (wrapper), AGPLv3 (underlying TetGen C++ library — see Security Domain)
```

## Architecture Patterns

### System Architecture Diagram

```
Surface Input (OBJ/STL)
    │
    ├─► OBJ Parser (built-in, ~15 lines)
    │     │
    │     └─► (vertices Nx3, faces Mx3) ──┐
    │                                      │
    ├─► numpy-stl (optional)               │
    │     │                                │
    │     └─► (vertices Nx3, faces Mx3) ──┤
    │                                      │
    └─► PyVista reader (optional)          │
          │                                │
          └─► (vertices Nx3, faces Mx3) ──┘
                                           │
                                           ▼
                              tetgen.TetGen(verts, faces)
                                           │
                                           ▼
                              .tetrahedralize(order=1, ...)
                                           │
                              ┌────────────┼────────────┐
                              ▼            ▼            ▼
                         nodes Nx3    elems Mx4    attributes
                        (float64)    (int32)      (float64)
                              │            │
                              └─────┬──────┘
                                    ▼
                          write_vtk_unstructured_grid()
                          (existing vtk_io.py — unchanged)
                                    │
                                    ▼
                              .vtk file on disk
                                    │
                          ┌─────────┼─────────┐
                          ▼                   ▼
                   MuJoCo flexcomp       PyBullet loadSoftBody
                   (Phase 16)            (Phase 16)
```

### Recommended Project Structure
```
src/surg_rl/utils/
├── vtk_io.py              # [UNCHANGED] write/read/validate legacy VTK
├── mesh_generation.py     # [MODIFIED] _try_external_tetrahedralization → tetgen
├── tetgen_wrapper.py      # [NEW] Thin wrapper: parse OBJ → tetgen → (verts, tets)
└── obj_parser.py          # [NEW] Minimal triangulated OBJ parser (~15 lines)
```

### Pattern 1: Replace PyVista `delaunay_3d()` with `tetgen.TetGen().tetrahedralize()`

**What:** Swap the optional external tetrahedralization call in `mesh_generation.py:_try_external_tetrahedralization()` from `pyvista.PolyData.delaunay_3d()` to `tetgen.TetGen().tetrahedralize()`.

**When to use:** Every call to generate a tetrahedral mesh from a surface — boxes >5000 tets, spheres, cylinders, and any user-provided surface mesh.

**Example:**
```python
# OLD (mesh_generation.py, current code):
def _try_external_tetrahedralization(vertices, faces):
    try:
        import pyvista as pv
        face_arr = np.hstack([np.full((len(faces), 1), 3), faces])
        surface = pv.PolyData(vertices, face_arr)
        tet_mesh = surface.delaunay_3d()
        tet_cells = tet_mesh.cells.reshape(-1, 5)[:, 1:]
        return tet_mesh.points, tet_cells
    except Exception:
        return None

# NEW (replacement):
def _try_external_tetrahedralization(vertices, faces):
    try:
        import tetgen
        tgen = tetgen.TetGen(vertices.astype(np.float64, copy=False),
                             faces.astype(np.int32, copy=False))
        nodes, elems = tgen.tetrahedralize(order=1, quiet=True)[:2]
        return nodes, elems
    except Exception:
        return None
```

### Pattern 2: OBJ → TetGen pipeline (new capability)

**What:** Parse an OBJ file, validate it's triangulated, feed vertex/face arrays to tetgen, return tetrahedral mesh as NumPy arrays.

**When to use:** When users provide mesh files or the project needs to mesh arbitrary surface geometry.

**Example:**
```python
# Source: Verified working on 2026-05-04 with tetgen 0.8.4
import numpy as np
import tetgen

def mesh_from_obj(obj_path: str, min_dihedral: float = 5.0,
                  min_ratio: float = 1.5, max_volume: float = -1.0
                  ) -> tuple[np.ndarray, np.ndarray]:
    """Generate tetrahedral mesh from a triangulated OBJ file.
    
    Returns (nodes_Nx3_float64, elems_Mx4_int32).
    """
    verts, faces = _parse_obj_triangles(obj_path)
    tgen = tetgen.TetGen(verts, faces)
    nodes, elems = tgen.tetrahedralize(
        order=1, mindihedral=min_dihedral, minratio=min_ratio,
        maxvolume=max_volume, quiet=True
    )[:2]
    return nodes, elems


def _parse_obj_triangles(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Parse a triangulated Wavefront OBJ file.
    
    Returns (vertices_Nx3_float64, faces_Mx3_int32).
    """
    verts, faces = [], []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if not parts or parts[0].startswith('#'):
                continue
            if parts[0] == 'v':
                verts.append([float(p) for p in parts[1:4]])
            elif parts[0] == 'f':
                idxs = [int(p.split('/')[0]) - 1 for p in parts[1:]]
                if len(idxs) == 3:
                    faces.append(idxs)
                elif len(idxs) == 4:
                    faces.append([idxs[0], idxs[1], idxs[2]])
                    faces.append([idxs[0], idxs[2], idxs[3]])
                else:
                    raise ValueError(f"N-gon ({len(idxs)} vertices) not supported")
    return (np.array(verts, dtype=np.float64),
            np.array(faces, dtype=np.int32))
```

### Anti-Patterns to Avoid

- **Importing PyVista in mesh generation hot path:** PyVista pulls in VTK (~200MB) — keep it optional. tetgen is <1MB and only needs numpy.
- **Subprocess calls to tetgen CLI:** The CLI may not be installed. CFFI bindings are faster, more reliable, and tested on all platforms.
- **Assuming all OBJ files are triangulated:** Many modeling tools export quads. Parse must handle both tri and quad faces, converting quads to 2 triangles.
- **Hand-rolling Delaunay tetrahedralization:** TetGen handles boundary preservation, quality optimization, and Steiner point insertion. These are hard problems.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Delaunay tetrahedralization | Bowyer-Watson or incremental flip algorithm | `tetgen.TetGen().tetrahedralize()` | Boundary preservation, Steiner point insertion, quality optimization, degenerate case handling — decades of research in TetGen |
| OBJ/STL mesh parsing | Full Wavefront OBJ parser with materials/textures | Built-in minimal parser + optional `numpy-stl` | Our meshes are triangulated procedural output; we don't need materials, normals, or texture coords |
| Non-manifold surface repair | Custom hole-filling / edge-stitching | `pymeshfix` (optional) + `tetgen.make_manifold()` | Mesh repair is a deep research problem; pymeshfix wraps the same library TetGen's author recommends |
| VTK file I/O | Rewriting from scratch | Keep existing `vtk_io.py` — it works and is tested | Pure Python, 186 lines, tested. TetGen outputs same NumPy format. Zero reason to change. |
| Mesh quality computation | Custom Jacobian / dihedral calculators | TetGen's internal quality metrics | TetGen reports quality during generation; if post-hoc needed, use `tetgen.elem` with existing VTK quality libraries |

**Key insight:** The surgical simulation community uses TetGen because mesh generation is deceptively hard. What looks like "just connect the dots" involves constrained Delaunay triangulation, boundary conformity, sliver elimination, and quality optimization — all with pathological edge cases. TetGen has been the standard for 25+ years in computational geometry and surgical simulation.

## Runtime State Inventory

> Phase 15 is a greenfield/refactor phase. It replaces the mesh generation backend but does NOT rename or migrate existing files. The `vtk_io.py` file retains its name and API — only the internals of `mesh_generation.py` change.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — mesh files on disk (.vtk, .obj) are regenerated on each run via temp_dir | Code edit only (generation logic) |
| Live service config | None | — |
| OS-registered state | None | — |
| Secrets/env vars | None | — |
| Build artifacts | None — tetgen wheel is precompiled; no build step needed | — |

## Common Pitfalls

### Pitfall 1: Non-Manifold Input Surfaces
**What goes wrong:** `tetrahedralize()` raises `RuntimeError: "Failed to tetrahedralize. You may need to repair surface by making it manifold"` when the input surface has holes, non-manifold edges, duplicate vertices, or self-intersections.

**Why it happens:** TetGen requires a watertight, manifold triangular surface as input. Our procedural generators (box, sphere, cylinder) produce correct meshes, but user-provided OBJ/STL files from modeling tools frequently have topology issues.

**How to avoid:** 
1. Call `tgen.make_manifold()` before `tetrahedralize()` — this requires `pymeshfix >= 0.18.0` as an optional dependency.
2. Check `tgen._tetgen.n_faces > 0` after construction to verify faces loaded.
3. The simpler fallback: catch the RuntimeError and fall back to the existing pure-Python grid decomposition (which is already the fallback path in `mesh_generation.py`).

**Warning signs:** TetGen hangs with no progress output (verbosity 1+ shows if it's stuck on a bad face).

### Pitfall 2: Overly Aggressive Quality Parameters Causing Hangs
**What goes wrong:** Setting `minratio=1.05` or `mindihedral=15` with `steinerleft=100000` (default) causes TetGen to add infinite Steiner points trying to satisfy impossible quality constraints.

**Why it happens:** Quality constraints are hard geometric limits. A ratio of 1.0 is mathematically impossible in 3D for most domains. The closer to 1.0, the more Steiner points needed.

**How to avoid:** 
- Cap `minratio` at 1.1 (documented by TetGen docs as "reasonable"). 
- Cap `mindihedral` at 10.0 degrees.
- Set `steinerleft` to a finite value (e.g., 1000 for small meshes, 10000 for large) rather than -1 (unlimited).
- Use `nobisect=True` if the input surface is already well-shaped to prevent TetGen from modifying it.

**Warning signs:** TetGen runs for >30 seconds on a mesh with <1000 input faces.

### Pitfall 3: PyVista Imports Triggering VTK Load
**What goes wrong:** Importing `tetgen` with `pyvista` installed triggers the `.tetgen` accessor registration (`_accessor.py`), which imports `pyvista`, which loads VTK — adding 500ms+ startup time even if PyVista isn't needed.

**Why it happens:** `tetgen/__init__.py` imports `_accessor.py` unconditionally, which does `import pyvista as pv`.

**How to avoid:** 
- Don't install pyvista in the base [meshing] extra.
- If users have pyvista installed for other reasons, the import cost is already paid — no additional harm.
- The `_accessor.py` module gracefully handles missing pyvista (import fails silently if not installed), so tetgen still works.

**Warning signs:** `import tetgen` takes >300ms — pyvista is loading.

### Pitfall 4: Element Indexing Offsets (0-based vs 1-based)
**What goes wrong:** TetGen's `.elem` property may return 1-based indices in some configurations (the `zeroindex=False` parameter preserves the C++ convention of 1-indexing).

**Why it happens:** Native TetGen uses 1-indexed arrays. The Python wrapper's `tetrahedralize()` defaults to `zeroindex=False` in the function signature but the underlying CFFI may auto-convert.

**How to avoid:** 
- Always pass `zeroindex=True` to `tetrahedralize()` when calling the raw API.
- Verify: `elems.min() == 0` after generation (tested: on 0.8.4 with default params, returns 0-based indices ✓).
- The `tetgen` v0.8.4 default behavior returns 0-based indices in my testing.

**Warning signs:** `IndexError` when indexing vertices with element values, or elements referencing vertex indices beyond array bounds.

### Pitfall 5: TetGen License (AGPLv3)
**What goes wrong:** The TetGen C++ library is AGPLv3 licensed. This has implications for commercial use and distribution — the AGPL requires source code disclosure for network-facing services.

**Why it happens:** Hang Si's original TetGen is AGPL. The Python wrapper is MIT, but dynamically links to AGPL code.

**How to avoid:** 
- Document the license in project `pyproject.toml` classifier or README.
- The `tetgen` package includes both MIT and AGPL license files.
- For surgical training simulators (research/non-commercial), AGPL is fine.
- For commercial medical device use, consult a lawyer — AGPL linking in Python may require full source disclosure.

**Warning signs:** Corporate legal review flags the dependency.

## Code Examples

Verified patterns from official sources and testing:

### Replace PyVista `delaunay_3d()` with tetgen
```python
# Source: Verified working 2026-05-04, tetgen 0.8.4, macOS arm64
# This replaces the current _try_external_tetrahedralization() in mesh_generation.py

import numpy as np
import tetgen

def _try_external_tetrahedralization(vertices, faces):
    """Attempt tetrahedralization using tetgen (required dependency)."""
    try:
        tgen = tetgen.TetGen(
            vertices.astype(np.float64, copy=False),
            faces.astype(np.int32, copy=False),
        )
        nodes, elems = tgen.tetrahedralize(order=1, quiet=True)[:2]
        return nodes, elems
    except RuntimeError:
        # Surface is non-manifold — caller falls back to grid decomposition
        return None
    except ImportError:
        # tetgen not installed — caller falls back to grid decomposition
        return None
```

### Mesh from OBJ file with quality control
```python
# Source: Verified working 2026-05-04, tetgen 0.8.4

def generate_tetrahedral_mesh(obj_path, min_dihedral=5.0, min_ratio=1.5):
    """Full pipeline: OBJ → tetgen tetrahedral mesh → (nodes, elems)."""
    verts, faces = _parse_obj_triangles(obj_path)  # See Pattern 2 above
    tgen = tetgen.TetGen(verts, faces)
    nodes, elems = tgen.tetrahedralize(
        order=1, mindihedral=min_dihedral, minratio=min_ratio,
        quiet=True,
    )[:2]
    return nodes, elems

# Usage:
# nodes, elems = generate_tetrahedral_mesh("organ.obj", min_dihedral=10)
# surg_rl.utils.vtk_io.write_vtk_unstructured_grid("organ.vtk", nodes, elems)
```

### Non-manifold surface handling
```python
# Source: tetgen docs, https://tetgen.pyvista.org/

import tetgen

def mesh_with_repair(obj_path):
    verts, faces = _parse_obj_triangles(obj_path)
    tgen = tetgen.TetGen(verts, faces)
    try:
        nodes, elems = tgen.tetrahedralize(quiet=True)[:2]
    except RuntimeError:
        # Surface needs repair
        tgen.make_manifold()  # Requires pymeshfix >= 0.18.0
        nodes, elems = tgen.tetrahedralize(quiet=True)[:2]
    return nodes, elems
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pyvista.PolyData.delaunay_3d()` | `tetgen.TetGen().tetrahedralize()` | 2026-05 (this phase) | Platform-agnostic (no VTK binaries); better quality control; surgical simulation standard |
| PyVista for OBJ/STL loading | Built-in minimal OBJ parser + optional numpy-stl | 2026-05 (this phase) | Eliminates 200MB VTK dependency from mesh gen; simple parsers are faster |
| Standalone `pytetgen` CLI wrapper | Integrated CFFI bindings (`tetgen` 0.8.4) | 2020 (TetGen 1.6.0 in libigl) | No subprocess overhead; memory-safe; direct NumPy interop |

**Deprecated/outdated:**
- `pytetgen` v0.2.2 (2021): Unmaintained, no macos-arm64 wheels. Do not use.
- `tetgenpy` v0.1.0 (2021): Single-version release, no wheels. Do not use.
- `pyvista.delaunay_3d()` for mesh generation: Still works, but adds VTK dependency for a capability tetgen provides directly. Deprecated in surg-rl context.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | TetGen C++ 1.6.0 (in `tetgen` 0.8.4) handles all our procedural mesh shapes (box, sphere, cylinder) without failure | Architecture Patterns | Low — tested with sphere and cube; tetrahedralization succeeded. Cylinder should also work as long as triangulated. |
| A2 | User-provided OBJ files in the surgical context are mostly triangulated (from medical imaging tools) | Common Pitfalls | Medium — if users provide quad-dominant OBJs, the parser needs quad → tri conversion (already implemented above) |
| A3 | `numpy-stl` is the right STL parser for a lightweight optional dependency | Standard Stack | Low — numpy-stl is the Python standard for STL; if it doesn't work, PyVista fallback is available |
| A4 | AGPLv3 licensing of TetGen C++ is acceptable for this research project | Common Pitfalls | Medium — if commercial use is planned, need legal review. MIT wrapper + AGPL C++ linking is a known gray area |

## Open Questions

1. **STL binary parsing without numpy-stl**
   - What we know: STL binary has a fixed 84-byte header + 50-byte-per-triangle format; parsable in pure Python
   - What's unclear: Whether the added complexity of binary STL parsing is worth the ~5KB of code vs just depending on numpy-stl
   - Recommendation: Add `numpy-stl` to [meshing] extras for STL support; document that OBJ is the preferred format

2. **Quadratic tetrahedra (order=2)**
   - What we know: TetGen supports `order=2` for quadratic (10-node) tetrahedra. Output elems shape becomes (M, 10).
   - What's unclear: Whether Phase 16 (Deformables) or Phase 17 (Cutting) benefits from quadratic tets. FEM deformables typically use linear tets for performance.
   - Recommendation: Use `order=1` (linear tets) for Phase 15. If higher-order needed later, it's a single parameter change.

3. **Background mesh / adaptive refinement**
   - What we know: TetGen supports background meshes for spatial sizing functions. This allows denser meshing near cutting planes or contact regions.
   - What's unclear: Whether the mesh sizing information exists at generation time (pre-simulation) or needs to be dynamically updated (during simulation)
   - Recommendation: Use uniform meshing for Phase 15. Adaptive refinement is a Phase 17 (Cutting) concern.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| tetgen (Python) | TETG-01 core generation | ✓ | 0.8.4 | — |
| numpy | Array contract | ✓ | 2.4.4 (installed) | — |
| pyvista | Optional file I/O, visualization | ✗ | — | Built-in OBJ parser |
| numpy-stl | Optional STL loading | ✗ | — | PyVista (if installed) |
| pymeshfix | Non-manifold repair | ✗ | — | Fall back to grid decomposition |
| meshio | Extra output formats | ✗ | — | Not needed for VTK output |
| trimesh | Advanced mesh ops | ✗ | — | Not needed |

**Missing dependencies with no fallback:**
- None — `tetgen` is the only required new dependency, and it's available with precompiled wheels.

**Missing dependencies with fallback:**
- `pyvista`: Optional; users who need full mesh I/O can install it separately.
- `numpy-stl`: Optional; STL files can be loaded via PyVista or converted to OBJ.
- `pymeshfix`: Optional; non-manifold surfaces fall back to grid decomposition.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest ≥7.0.0 |
| Config file | pytest.ini (`pythonpath = src`) |
| Quick run command | `PYTHONPATH=src pytest tests/test_mesh_generation.py tests/test_vtk_io.py -v` |
| Full suite command | `PYTHONPATH=src pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TETG-01 | tetgen produces valid (nodes, elems) from surface arrays | unit | `PYTHONPATH=src pytest tests/test_mesh_generation.py::TestTetGenIntegration::test_tetgen_generates_tetrahedral_mesh -x` | ❌ Wave 0 |
| TETG-02 | OBJ file → tetrahedral mesh via tetgen | unit | `PYTHONPATH=src pytest tests/test_mesh_generation.py::TestTetGenIntegration::test_obj_to_tetrahedral_mesh -x` | ❌ Wave 0 |
| TETG-02 | STL file → tetrahedral mesh via tetgen | unit | `PYTHONPATH=src pytest tests/test_mesh_generation.py::TestTetGenIntegration::test_stl_to_tetrahedral_mesh -x` | ❌ Wave 0 |
| TETG-03 | No PyVista import required for mesh generation | unit | `PYTHONPATH=src pytest tests/test_mesh_generation.py::TestTetGenIntegration::test_no_pyvista_import -x` | ❌ Wave 0 |
| TETG-04 | vtk_io.py public API unchanged after refactor | regression | `PYTHONPATH=src pytest tests/test_vtk_io.py -v` | ✅ existing tests |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src pytest tests/test_mesh_generation.py tests/test_vtk_io.py -v`
- **Per wave merge:** `PYTHONPATH=src pytest tests/test_mesh_generation.py tests/test_vtk_io.py -v`
- **Phase gate:** `PYTHONPATH=src pytest tests/ -m "not integration" -v` — full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tetgen_integration.py` — new file for tetgen-specific tests (TETG-01..03)
- [ ] `tests/conftest.py` — check if shared fixtures exist for tmp OBJ files (likely already present)
- [ ] `pip install tetgen` — verify tetgen is in test environment (CI matrix needs update)
- [ ] `tests/test_mesh_generation.py` — update to test new `_try_external_tetrahedralization()` path

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Validate OBJ/STL input: max vertex count, face index bounds, non-nan coordinates; tetgen itself handles degenerate geometry gracefully |
| V6 Cryptography | no | — |
| V7 Error Handling | yes | Catch RuntimeError from tetrahedralize(); don't crash simulator on bad mesh input |

### Known Threat Patterns for tetgen mesh generation

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed OBJ/STL with excessive vertices (>10M) | Denial of Service | Cap input mesh size before passing to tetgen; `max_vertices` config parameter (default: 100,000) |
| OBJ face indices out of bounds | Tampering | Validate all face indices < len(vertices) before calling tetgen |
| NaN / Inf vertex coordinates | Tampering | `np.isfinite(vertices).all()` check before tetrahedralization |
| Path traversal in mesh file paths | Information Disclosure | Resolve paths against project assets_dir only; reject `..` components |
| AGPLv3 license non-compliance | Legal / Compliance | Document AGPL implications in LICENSE file; users accept by installing the dependency |
| Integer overflow in cell counts (32-bit indices) | Denial of Service | tetgen uses int32 indices; meshes with >2B vertices aren't practical but cap at 10M |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: npm/pip registry] `tetgen` 0.8.4 — installed and tested on macOS arm64; confirmed wheels for all platforms; only dependency is numpy
- [VERIFIED: code test] `tetgen.TetGen(verts, faces).tetrahedralize()` works without PyVista imported
- [VERIFIED: code test] Return format is exactly `(nodes_Nx3_float64, elems_Mx4_int32)` — matches existing vtk_io.py contract
- [CITED: https://tetgen.pyvista.org/] Full API documentation including tetrahedralize parameters and property accessors
- [CITED: https://github.com/pyvista/tetgen] Source repository; 298 stars, 139 commits, MIT license (wrapper), AGPL (C++)

### Secondary (MEDIUM confidence)
- [CITED: https://pypi.org/project/tetgen/] Package metadata confirms version 0.8.4, Python ≥3.10, platform wheel availability
- [websearch: tetgen Python packages] Confirmed `pytetgen` and `tetgenpy` are unmaintained alternatives

### Tertiary (LOW confidence)
- [ASSUMED] User-provided OBJ files are triangulated — based on training knowledge of medical imaging pipelines; not verified with actual surgical OBJ datasets
- [ASSUMED] AGPLv3 is acceptable for research use — confirmed by reading license text; commercial implications require legal review

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — tetgen 0.8.4 is the only maintained package; verified install on target platform; tested NumPy array API
- Architecture: HIGH — drop-in replacement for existing _try_external_tetrahedralization(); preserves vtk_io.py API; minimal surface OBJ parser verified
- Pitfalls: MEDIUM — non-manifold surfaces and quality parameter hangs are well-documented; STL parsing strategy needs user confirmation
- Security: MEDIUM — AGPL licensing implications are clear for research but require legal review for commercial use

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (tetgen package is stable; new releases unlikely to change API)
