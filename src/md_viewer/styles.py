"""CSS styles applied to rendered documents.

A style is a ``.css`` file. Its id is the file stem; its display name comes from
a ``name:`` line in the file's leading comment, e.g.::

    /* name: GitHub
       description: GitHub's look, follows light/dark mode
       scheme: auto */

``scheme`` is ``light``, ``dark`` or ``auto`` (default: follow the system
setting); it picks the matching syntax-highlighting colours.

User styles (``~/.local/share/md-viewer/styles/``) override built-ins with the same id.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .paths import builtin_styles_dir, user_styles_dir

_log = logging.getLogger(__name__)

DEFAULT_STYLE = "github"
SCHEMES = ("auto", "light", "dark")

_HEADER_RE = re.compile(r"\A\s*/\*(.*?)\*/", re.DOTALL)
_FIELD_RE = re.compile(r"^\s*(name|description|scheme)\s*:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Style:
    id: str
    name: str
    description: str
    scheme: str  # one of SCHEMES
    path: Path
    builtin: bool

    def read_css(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")


def _parse_header(css: str) -> dict[str, str]:
    header = _HEADER_RE.match(css)
    if not header:
        return {}
    return dict(_FIELD_RE.findall(header.group(1)))


def _load_dir(directory: Path, builtin: bool) -> dict[str, Style]:
    styles: dict[str, Style] = {}
    if not directory.is_dir():
        return styles
    for path in sorted(directory.glob("*.css")):
        try:
            fields = _parse_header(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            _log.warning("Cannot read style %s", path, exc_info=True)
            continue
        styles[path.stem] = Style(
            id=path.stem,
            name=fields.get("name") or path.stem.replace("-", " ").replace("_", " ").title(),
            description=fields.get("description", ""),
            scheme=fields["scheme"] if fields.get("scheme") in SCHEMES else "auto",
            path=path,
            builtin=builtin,
        )
    return styles


def discover_styles(builtin_dir: Path | None = None, user_dir: Path | None = None) -> dict[str, Style]:
    """All available styles keyed by id, sorted by display name. User styles win on id clashes."""
    styles = _load_dir(builtin_dir or builtin_styles_dir(), builtin=True)
    styles.update(_load_dir(user_dir or user_styles_dir(), builtin=False))
    return dict(sorted(styles.items(), key=lambda item: item[1].name.casefold()))


def resolve_style(styles: dict[str, Style], style_id: str | None) -> Style | None:
    """*style_id* if it exists, else the default style, else any style, else None."""
    for candidate in (style_id, DEFAULT_STYLE):
        if candidate is not None and candidate in styles:
            return styles[candidate]
    return next(iter(styles.values()), None)
