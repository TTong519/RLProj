"""Regression tests for user-facing documentation assets (Phase 34)."""

import re
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _gif_frame_count(path: Path) -> int:
    data = path.read_bytes()
    frames = 0
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0x2C:
            frames += 1
            i += 1
            if i + 8 >= len(data):
                break
            i += 8
            if i >= len(data):
                break
            packed = data[i]
            i += 1
            if packed & 0x80:
                table_size = 3 * (1 << ((packed & 0x07) + 1))
                i += table_size
            if i >= len(data):
                break
            i += 1
            while i < len(data):
                size = data[i]
                i += 1
                if size == 0:
                    break
                i += size
        elif b == 0x21:
            i += 2
            while i < len(data):
                size = data[i]
                i += 1
                if size == 0:
                    break
                i += size
        elif b == 0x3B:
            break
        else:
            i += 1
    return frames


class TestDemoGifs:
    """DOC-04: three ~30s demo GIFs exist and are valid."""

    @pytest.mark.parametrize(
        "task, expected_frames",
        [
            ("suturing", 300),
            ("knot_tying", 300),
            ("needle_passing", 300),
        ],
    )
    def test_gif_exists_and_valid(self, task: str, expected_frames: int) -> None:
        gif = REPO_ROOT / "docs" / "demos" / f"{task}.gif"
        assert gif.exists(), f"Missing GIF: {gif}"
        size = gif.stat().st_size
        assert 100_000 <= size <= 15_000_000, f"{task}.gif size {size} out of expected range"
        assert _gif_frame_count(gif) == expected_frames, (
            f"{task}.gif frame count mismatch"
        )


class TestGuiScreenshots:
    """DOC-05: GUI screenshots are valid PNGs copied from Phase 33."""

    @pytest.mark.parametrize("name", ["viewport", "tree_form", "llm_panel"])
    def test_screenshot_exists_and_valid(self, name: str) -> None:
        png = REPO_ROOT / "docs" / "gui" / f"{name}.png"
        assert png.exists(), f"Missing screenshot: {png}"
        assert png.stat().st_size >= 5_000, f"{name}.png too small"
        data = png.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{name}.png is not a PNG"
        pos = data.find(b"IHDR")
        assert pos != -1
        height = struct.unpack(">I", data[pos + 8 : pos + 12])[0]
        assert height >= 200, f"{name}.png height {height} < 200"

        # Source file must remain in tests/gui/screenshots/
        src = REPO_ROOT / "tests" / "gui" / "screenshots" / f"{name}.png"
        assert src.exists(), f"Source screenshot missing: {src}"


class TestReadmeStructure:
    """DOC-01: README has banner, quickstart, demos, GUI section, extras, links."""

    @pytest.fixture(scope="class")
    def readme(self) -> str:
        return (REPO_ROOT / "README.md").read_text()

    def test_banner_and_badges(self, readme: str) -> None:
        assert "# surg-rl" in readme
        assert "python-%E2%89%A53.10" in readme or "Python" in readme

    def test_sixty_second_quickstart(self, readme: str) -> None:
        assert 'pip install -e ".[dev,gui]"' in readme
        assert "surg-rl version --verbose" in readme
        assert "surg-rl-gui scenes/simple_suturing.json" in readme

    def test_demo_walkthroughs(self, readme: str) -> None:
        for task in ["suturing", "knot_tying", "needle_passing"]:
            assert f"docs/demos/{task}.gif" in readme

    def test_gui_section(self, readme: str) -> None:
        assert "pip install '.[gui]'" in readme
        assert "surg-rl-gui" in readme
        assert "docs/gui/viewport.png" in readme

    def test_extras_matrix(self, readme: str) -> None:
        assert "| `gui` |" in readme
        assert "| `marl` |" in readme

    def test_contributing_and_changelog_links(self, readme: str) -> None:
        assert "CONTRIBUTING.md" in readme
        assert "CHANGELOG.md" in readme

    def test_no_tests_asset_paths(self, readme: str) -> None:
        local_images = re.findall(r"!\[.*?\]\((?!https?://).*?\)", readme)
        for img in local_images:
            path = img.split("(")[-1].rstrip(")")
            assert not path.startswith("tests/"), f"README embeds tests/ path: {path}"


class TestChangelogRelease:
    """DOC-03: CHANGELOG contains v0.5.0 entry."""

    def test_v050_section(self) -> None:
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text()
        assert "## [0.5.0]" in changelog
        assert "### Added" in changelog
        assert "### Changed" in changelog
        assert "### Fixed" in changelog


class TestContributingRefresh:
    """DOC-02: CONTRIBUTING reflects v0.5.0 workflow."""

    def test_contributing_setup_and_workflow(self) -> None:
        contrib = (REPO_ROOT / "CONTRIBUTING.md").read_text()
        assert 'pip install -e ".[dev,gui]"' in contrib
        assert "/gsd-discuss-phase" in contrib
        assert "/gsd-plan-phase" in contrib
        assert "/gsd-execute-phase" in contrib
        assert "ruff check src/ tests/" in contrib
        assert "black --check src/ tests/" in contrib
        assert "mypy src/surg_rl" in contrib
