"""Download real surgical instrument and organ OBJ meshes from public datasets.

Downloads are explicit and require user consent. No automatic downloads.
"""

from pathlib import Path
from typing import Any

from surg_rl.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MESH_URLS: dict[str, str] = {
    "forceps": "https://example.com/surgical-meshes/forceps.obj",
    "scalpel": "https://example.com/surgical-meshes/scalpel.obj",
    "needle_driver": "https://example.com/surgical-meshes/needle_driver.obj",
    "scissors": "https://example.com/surgical-meshes/scissors.obj",
    "clamp": "https://example.com/surgical-meshes/clamp.obj",
    "suction": "https://example.com/surgical-meshes/suction.obj",
    "cautery": "https://example.com/surgical-meshes/cautery.obj",
    "camera": "https://example.com/surgical-meshes/camera.obj",
    "retractor": "https://example.com/surgical-meshes/retractor.obj",
    "liver": "https://example.com/surgical-meshes/liver.obj",
    "kidney": "https://example.com/surgical-meshes/kidney.obj",
    "stomach": "https://example.com/surgical-meshes/stomach.obj",
    "gallbladder": "https://example.com/surgical-meshes/gallbladder.obj",
}

ALL_INSTRUMENT_NAMES = [
    "forceps", "scalpel", "needle_driver", "scissors",
    "clamp", "suction", "cautery", "camera", "retractor",
]

ALL_ORGAN_NAMES = ["liver", "kidney", "stomach", "gallbladder"]


def _get_http_client() -> Any:
    """Return an HTTP client (requests or httpx), or raise ImportError."""
    try:
        import requests
        return requests
    except ImportError:
        pass
    try:
        import httpx
        return httpx
    except ImportError:
        pass
    raise ImportError(
        "No HTTP client available. Install with: pip install requests"
    )


def download_meshes(
    names: list[str],
    output_dir: str = "assets/meshes",
) -> list[str]:
    """Download OBJ mesh files for the given instrument/organ names.

    Returns a list of successfully downloaded file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    http = _get_http_client()
    downloaded: list[str] = []

    for name in names:
        url = DEFAULT_MESH_URLS.get(name)
        if url is None:
            logger.warning(f"No download URL configured for '{name}'")
            continue

        dest = out / f"{name}.obj"
        try:
            if hasattr(http, "get"):
                resp = http.get(url, timeout=30)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
            else:
                resp = http.request("GET", url)
                resp.raise_for_status()
                dest.write_bytes(resp.read())
            downloaded.append(str(dest))
            logger.info(f"Downloaded: {name}.obj → {dest}")
        except Exception as e:
            logger.warning(f"Failed to download {name}: {e}")

    return downloaded


def list_local_meshes(meshes_dir: str = "assets/meshes") -> dict[str, bool]:
    """List which meshes are present locally and which are available for download.

    Returns a dict of mesh_name → is_present (bool).
    """
    d = Path(meshes_dir)
    result: dict[str, bool] = {}

    for name, url in DEFAULT_MESH_URLS.items():
        local_path = d / f"{name}.obj"
        result[name] = local_path.exists()

    return result


def check_mesh_available(name: str, meshes_dir: str = "assets/meshes") -> bool:
    """Check if a specific mesh file exists locally."""
    return (Path(meshes_dir) / f"{name}.obj").exists()


__all__ = [
    "ALL_INSTRUMENT_NAMES",
    "ALL_ORGAN_NAMES",
    "DEFAULT_MESH_URLS",
    "check_mesh_available",
    "download_meshes",
    "list_local_meshes",
]
