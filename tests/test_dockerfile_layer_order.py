"""Guard: Dockerfiles must copy src/ + README.md BEFORE `pip install -e .`.

Regression guard for the CI docker-ci job failure (run 28492071094, job
84450697466): Dockerfile.cuda/.rocm/.jetson/.ros2 ran `pip install -e ".[...]"`
BEFORE `src/` was copied into the image, so pip failed with
`error in 'egg_base' option: 'src' does not exist or is not a directory`.

pyproject.toml declares `readme = "README.md"` and
`[tool.setuptools.packages.find] where = ["src"]`, so BOTH `src/` and
`README.md` must exist in the image at editable-build time. The CPU Dockerfile
already follows this order; this test pins the invariant for every Dockerfile
that performs an editable install, so a future Dockerfile cannot regress the
layer ordering without failing this test in the regular matrix (no Docker
daemon required -- it parses the Dockerfiles statically).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILES = sorted(REPO_ROOT.glob("Dockerfile*"))

# A `pip install -e .` (editable) step. Matches `-e ".[extra]"` / `-e '.'` /
# `-e .` -- the editable target is `.` optionally wrapped in quotes and followed
# by an `[extra]` bracket. The dot must be the install target, not a flag value,
# so we anchor on `-e` + optional quote + literal dot. Non-editable `pip install .`
# installs are NOT pinned here (they build a sdist from the source tree, which
# still needs src/ -- but the historical bug was specifically the editable `-e`
# form, and a non-editable install with no source would fail differently).
_EDITABLE_INSTALL_RE = re.compile(r"pip install\b.*\s-e\s+['\"]?\.")


def _dockerfiles_with_editable_install() -> list[Path]:
    """Dockerfiles that contain a `pip install -e .` step (the ones at risk)."""
    out: list[Path] = []
    for df in DOCKERFILES:
        text = df.read_text()
        if _EDITABLE_INSTALL_RE.search(text):
            out.append(df)
    return out


def _line_no(text: str, pattern: re.Pattern[str]) -> int | None:
    """1-based line number of the first non-comment line matching `pattern`.

    Dockerfile comment lines (`# ...`) are skipped so that explanatory comments
    mentioning `pip install -e .` (used in the layer-order rationale comments) are
    not mistaken for the actual command. Only real Dockerfile instructions are
    considered.
    """
    for idx, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        if pattern.search(line):
            return idx
    return None


@pytest.fixture(scope="module")
def editable_dockerfiles() -> list[Path]:
    files = _dockerfiles_with_editable_install()
    assert files, "No Dockerfile with `pip install -e .` found -- guard is stale"
    return files


def test_editable_dockerfiles_copy_src_before_pip_install(editable_dockerfiles):
    """src/ must be COPYed before the editable `pip install -e .` step."""
    src_copy_re = re.compile(r"^\s*COPY\s+src/?\s+")
    failures: list[str] = []
    for df in editable_dockerfiles:
        text = df.read_text()
        pip_line = _line_no(text, _EDITABLE_INSTALL_RE)
        src_line = _line_no(text, src_copy_re)
        assert pip_line is not None, f"{df.name}: editable install line not found"
        if src_line is None:
            failures.append(f"{df.name}: no `COPY src/` found at all")
        elif src_line > pip_line:
            failures.append(
                f"{df.name}: `COPY src/` (line {src_line}) is AFTER "
                f"`pip install -e .` (line {pip_line}) -- pip cannot build "
                f"the editable wheel before src/ exists"
            )
    assert not failures, "Dockerfile layer-order regressions:\n  " + "\n  ".join(failures)


def test_editable_dockerfiles_copy_readme_before_pip_install(editable_dockerfiles):
    """README.md must be COPYed before the editable install (pyproject reads it for metadata)."""
    readme_copy_re = re.compile(r"^\s*COPY\s+README\.md\b")
    failures: list[str] = []
    for df in editable_dockerfiles:
        text = df.read_text()
        pip_line = _line_no(text, _EDITABLE_INSTALL_RE)
        readme_line = _line_no(text, readme_copy_re)
        assert pip_line is not None, f"{df.name}: editable install line not found"
        if readme_line is None:
            failures.append(f"{df.name}: no `COPY README.md` found at all")
        elif readme_line > pip_line:
            failures.append(
                f"{df.name}: `COPY README.md` (line {readme_line}) is AFTER "
                f"`pip install -e .` (line {pip_line}) -- pyproject declares "
                f'`readme = "README.md"`, so the file must exist at build time'
            )
    assert not failures, "Dockerfile README layer-order regressions:\n  " + "\n  ".join(failures)


def test_cpu_dockerfile_is_the_reference_ordering():
    """The CPU Dockerfile is the known-good reference: src/ + README before pip install."""
    cpu = REPO_ROOT / "Dockerfile"
    if not cpu.exists() or not _EDITABLE_INSTALL_RE.search(cpu.read_text()):
        pytest.skip("CPU Dockerfile missing or has no editable install")
    text = cpu.read_text()
    pip_line = _line_no(text, _EDITABLE_INSTALL_RE)
    src_line = _line_no(text, re.compile(r"^\s*COPY\s+src/?\s+"))
    readme_line = _line_no(text, re.compile(r"^\s*COPY\s+README\.md\b"))
    assert src_line is not None and src_line < pip_line
    assert readme_line is not None and readme_line < pip_line
