"""Procedural mesh generators for surgical instruments and organs.

Provides type-appropriate trimesh procedural shapes as fallbacks when
real OBJ meshes are not available. All generators call through the
TRIMESH lazy guard -- shapes are only generated when trimesh is installed.
"""

from collections.abc import Callable
from typing import Any

from surg_rl.assets import TRIMESH
from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

_procedural_map: dict[str, Callable[..., Any]] = {}


def _register(instrument_type: str) -> Callable:
    """Decorator to register a procedural generator for an instrument type."""

    def decorator(fn: Callable) -> Callable:
        _procedural_map[instrument_type] = fn
        return fn

    return decorator


@_register("scalpel")
def _scalpel(target_face_count: int | None = None) -> Any:
    """Flat blade + cylindrical handle."""
    TRIMESH  # Lazy import guard -- will raise ImportError with pip hint if missing
    import trimesh

    blade = trimesh.creation.box(extents=[0.003, 0.015, 0.08])
    handle = trimesh.creation.cylinder(radius=0.005, height=0.10, sections=16)
    handle.apply_translation([0, 0, -0.09])
    mesh = trimesh.util.concatenate([blade, handle])
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register("forceps")
def _forceps(target_face_count: int | None = None) -> Any:
    """Shaft + two jaw capsules."""
    TRIMESH
    import trimesh

    shaft = trimesh.creation.cylinder(radius=0.004, height=0.15, sections=16)
    shaft.apply_translation([0, 0, -0.075])
    jaw_l = trimesh.creation.capsule(radius=0.003, height=0.04)
    jaw_l.apply_translation([0.004, 0, -0.165])
    jaw_r = trimesh.creation.capsule(radius=0.003, height=0.04)
    jaw_r.apply_translation([-0.004, 0, -0.165])
    mesh = trimesh.util.concatenate([shaft, jaw_l, jaw_r])
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register("needle_driver")
def _needle_driver(target_face_count: int | None = None) -> Any:
    """Shaft + angled jaw with grip pads."""
    TRIMESH
    import trimesh

    shaft = trimesh.creation.cylinder(radius=0.004, height=0.14, sections=16)
    shaft.apply_translation([0, 0, -0.07])
    jaw = trimesh.creation.box(extents=[0.006, 0.015, 0.03])
    jaw.apply_translation([0, 0, -0.155])
    mesh = trimesh.util.concatenate([shaft, jaw])
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register("scissors")
def _scissors(target_face_count: int | None = None) -> Any:
    """Two intersecting flat blades + ring handles."""
    TRIMESH
    import trimesh

    blade = trimesh.creation.box(extents=[0.004, 0.012, 0.07])
    handle = trimesh.creation.cylinder(radius=0.005, height=0.08, sections=16)
    handle.apply_translation([0, 0, -0.075])
    mesh = trimesh.util.concatenate([blade, handle])
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register("clamp")
def _clamp(target_face_count: int | None = None) -> Any:
    """Bulldog-style clamp: shaft + wide jaw box."""
    TRIMESH
    import trimesh

    shaft = trimesh.creation.cylinder(radius=0.005, height=0.13, sections=16)
    shaft.apply_translation([0, 0, -0.065])
    jaw = trimesh.creation.box(extents=[0.008, 0.02, 0.025])
    jaw.apply_translation([0, 0, -0.14])
    mesh = trimesh.util.concatenate([shaft, jaw])
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register("suction")
def _suction(target_face_count: int | None = None) -> Any:
    """Hollow tube tip with angled opening."""
    TRIMESH
    import trimesh

    tube = trimesh.creation.cylinder(radius=0.006, height=0.15, sections=20)
    tube.apply_translation([0, 0, -0.075])
    if target_face_count:
        tube = tube.simplify_quadric_decimation(target_face_count)
    return tube


@_register("cautery")
def _cautery(target_face_count: int | None = None) -> Any:
    """Pen-style shaft + flat tip."""
    TRIMESH
    import trimesh

    shaft = trimesh.creation.cylinder(radius=0.004, height=0.14, sections=16)
    shaft.apply_translation([0, 0, -0.07])
    tip = trimesh.creation.box(extents=[0.004, 0.008, 0.02])
    tip.apply_translation([0, 0, -0.15])
    mesh = trimesh.util.concatenate([shaft, tip])
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register("camera")
def _camera(target_face_count: int | None = None) -> Any:
    """Endoscope-style: narrow cylinder + wider lens tip."""
    TRIMESH
    import trimesh

    shaft = trimesh.creation.cylinder(radius=0.005, height=0.14, sections=16)
    shaft.apply_translation([0, 0, -0.07])
    lens = trimesh.creation.cylinder(radius=0.008, height=0.015, sections=20)
    lens.apply_translation([0, 0, -0.147])
    mesh = trimesh.util.concatenate([shaft, lens])
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register("retractor")
def _retractor(target_face_count: int | None = None) -> Any:
    """Curved retractor blade."""
    TRIMESH
    import trimesh

    blade = trimesh.creation.box(extents=[0.015, 0.003, 0.12])
    if target_face_count:
        blade = blade.simplify_quadric_decimation(target_face_count)
    return blade


@_register("needle")
def _needle(target_face_count: int | None = None) -> Any:
    """Curved surgical needle — thin torus arc.

    Used as a fallback when no real needle mesh is available (e.g. for
    ``scenes/suturing_demo.json``'s ``curved_suturing_needle`` instrument,
    which the schema classifies as ``type="needle"`` but the mesh file
    ``assets/instruments/suturing_needle.obj`` is missing).
    """
    TRIMESH
    import trimesh

    # A thin torus approximates a curved surgical needle well enough
    # for primitive fallback. Major radius 0.008 m, minor radius 0.0006 m
    # (1.2 mm wire — typical for a curved suturing needle).
    needle = trimesh.creation.torus(
        major_radius=0.008, minor_radius=0.0006, major_sections=32, minor_sections=8
    )
    if target_face_count:
        needle = needle.simplify_quadric_decimation(target_face_count)
    return needle


@_register("knot_tier")
def _knot_tier(target_face_count: int | None = None) -> Any:
    """Generic knot-tying tool — slender shaft + spherical tip.

    The schema lists this type but no scene currently uses it; the
    generator exists so that loading such a scene doesn't crash with
    a KeyError before the user can fix the asset reference.
    """
    TRIMESH
    import trimesh

    shaft = trimesh.creation.cylinder(radius=0.003, height=0.13, sections=16)
    tip = trimesh.creation.icosphere(subdivisions=2, radius=0.005)
    tip.apply_translation([0, 0, 0.07])
    mesh = trimesh.util.concatenate([shaft, tip])
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register("custom")
def _custom(target_face_count: int | None = None) -> Any:
    """Generic fallback for any instrument type not in the registry.

    Returns a simple elongated box (a "generic tool" shape) suitable as
    a placeholder when the user picks ``type="custom"`` in a scene file
    or when a future schema addition isn't yet mapped to a procedural
    generator. Without this fallback, scenes using ``type="custom"``
    (e.g. ``scenes/suturing_demo.json``'s ``curved_suturing_needle``)
    crash at scene load with a KeyError.
    """
    TRIMESH
    import trimesh

    tool = trimesh.creation.box(extents=[0.006, 0.006, 0.05])
    if target_face_count:
        tool = tool.simplify_quadric_decimation(target_face_count)
    return tool


# Organ procedural generators
_organ_map: dict[str, Callable[..., Any]] = {}


def _register_organ(organ_type: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        _organ_map[organ_type] = fn
        return fn

    return decorator


@_register_organ("liver")
def _liver(target_face_count: int | None = None) -> Any:
    """Flattened ellipsoid approximating liver shape."""
    TRIMESH
    import trimesh

    mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.08)
    mesh.vertices[:, 1] *= 0.6  # flatten Y axis
    mesh.vertices[:, 0] *= 1.2  # widen X axis
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register_organ("kidney")
def _kidney(target_face_count: int | None = None) -> Any:
    """Bean-shaped ellipsoid."""
    TRIMESH
    import trimesh

    mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.05)
    mesh.vertices[:, 1] *= 0.5
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register_organ("stomach")
def _stomach(target_face_count: int | None = None) -> Any:
    """J-shaped elongated ellipsoid."""
    TRIMESH
    import trimesh

    mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.07)
    mesh.vertices[:, 1] *= 1.4
    mesh.vertices[:, 0] *= 0.7
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


@_register_organ("gallbladder")
def _gallbladder(target_face_count: int | None = None) -> Any:
    """Pear-shaped small ellipsoid."""
    TRIMESH
    import trimesh

    mesh = trimesh.creation.icosphere(subdivisions=2, radius=0.035)
    mesh.vertices[:, 1] *= 1.5
    if target_face_count:
        mesh = mesh.simplify_quadric_decimation(target_face_count)
    return mesh


def generate_procedural_instrument(
    instrument_type: str, target_face_count: int | None = None
) -> Any:
    """Generate a procedural trimesh mesh for an instrument type.

    Args:
        instrument_type: One of the InstrumentType enum values (e.g. "forceps").
        target_face_count: If set, decimates to this approximate face count.

    Returns:
        trimesh.Trimesh object.

    Raises:
        ImportError: If trimesh is not installed (with pip install hint).
        KeyError: If instrument_type is not in the procedural map AND no
            "custom" fallback is registered (defensive — should not happen
            since ``@_register("custom")`` always provides a fallback).

    Note:
        Unknown / unregistered instrument types are logged and routed to
        the ``custom`` generator instead of raising. The previous behavior
        of raising ``KeyError`` for ``"custom"`` and other schema-allowed
        types not yet mapped (e.g. ``"knot_tier"``, ``"needle"``) crashed
        scene loading with no graceful recovery.
    """
    generator = _procedural_map.get(instrument_type)
    if generator is None:
        logger.warning(
            "No procedural generator for instrument type %r; "
            "falling back to 'custom' generic tool shape. "
            "Available: %s",
            instrument_type,
            sorted(_procedural_map.keys()),
        )
        generator = _procedural_map.get("custom")
        if generator is None:
            raise KeyError(
                f"No procedural generator for instrument type '{instrument_type}'. "
                f"Available: {list(_procedural_map.keys())}"
            )
    return generator(target_face_count=target_face_count)


def generate_procedural_organ(organ_type: str, target_face_count: int | None = None) -> Any:
    """Generate a procedural trimesh mesh for an organ type.

    Args:
        organ_type: One of the organ names (e.g. "liver", "kidney").
        target_face_count: If set, decimates to this approximate face count.

    Returns:
        trimesh.Trimesh object.
    """
    generator = _organ_map.get(organ_type)
    if generator is None:
        raise KeyError(
            f"No procedural generator for organ type '{organ_type}'. "
            f"Available: {list(_organ_map.keys())}"
        )
    return generator(target_face_count=target_face_count)


__all__ = [
    "generate_procedural_instrument",
    "generate_procedural_organ",
]
