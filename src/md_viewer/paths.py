"""Filesystem locations: bundled data (dev checkout or installed) and per-user dirs."""

from __future__ import annotations

import os
from pathlib import Path

_INSTALLED_DATA_DIR = Path("/usr/share/xfce-md-viewer")
_DEV_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

USER_DIR_NAME = "md-viewer"


def data_dir() -> Path:
    """Bundled data directory: the repo's ``data/`` when running from source, else /usr/share."""
    if (_DEV_DATA_DIR / "styles").is_dir():
        return _DEV_DATA_DIR
    return _INSTALLED_DATA_DIR


def builtin_styles_dir() -> Path:
    return data_dir() / "styles"


def vendor_dir() -> Path:
    """Bundled third-party assets (KaTeX, Mermaid)."""
    return data_dir() / "vendor"


def scripts_dir() -> Path:
    """The viewer's own page scripts (run in the isolated script world)."""
    return data_dir() / "js"


def user_styles_dir() -> Path:
    """Per-user style directory, honouring $XDG_DATA_HOME (default ~/.local/share)."""
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / USER_DIR_NAME / "styles"
