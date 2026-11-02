"""Package metadata sanity checks (no GTK, no display)."""

import re
from pathlib import Path

import md_viewer

ROOT = Path(__file__).resolve().parent.parent


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", md_viewer.__version__)


def test_changelog_matches_version():
    first_line = (ROOT / "debian" / "changelog").read_text().splitlines()[0]
    assert f"({md_viewer.__version__}-" in first_line


def test_metainfo_lists_current_version():
    metainfo = (ROOT / "data" / f"{md_viewer.APP_ID}.metainfo.xml").read_text()
    assert f'<release version="{md_viewer.__version__}"' in metainfo
