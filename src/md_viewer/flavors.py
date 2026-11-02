"""Markdown flavors: which parser turns Markdown text into an HTML body fragment.

Three backends:

* ``markdown-it`` (python3-markdown-it + python3-mdit-py-plugins) — CommonMark, GFM
* ``python-markdown`` (python3-markdown) — original Markdown.pl, PHP Markdown Extra
* ``pandoc`` (optional) — Pandoc Markdown, MultiMarkdown, R Markdown, CommonMark+extensions

Minimum supported library versions are Ubuntu 24.04's: markdown-it-py 3.0.0,
mdit-py-plugins 0.4.0, pandoc 3.1.3. Do not use APIs newer than those.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

import markdown
from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

DEFAULT_FLAVOR = "gfm"
PANDOC_TIMEOUT_SECONDS = 30


class FlavorUnavailableError(RuntimeError):
    """The requested flavor's backend (e.g. pandoc) is not installed."""


class RenderError(RuntimeError):
    """The backend failed to convert the document."""


@dataclass(frozen=True)
class Flavor:
    id: str
    name: str
    description: str
    backend: str  # "markdown-it" | "python-markdown" | "pandoc"
    pandoc_format: str | None = None

    @property
    def requires_pandoc(self) -> bool:
        return self.backend == "pandoc"


FLAVORS: dict[str, Flavor] = {
    f.id: f
    for f in (
        Flavor("gfm", "GitHub Flavored", "CommonMark plus tables, task lists, strikethrough, footnotes", "markdown-it"),
        Flavor("commonmark", "CommonMark", "The strict CommonMark specification", "markdown-it"),
        Flavor("original", "Original (Markdown.pl)", "John Gruber's original Markdown syntax", "python-markdown"),
        Flavor("extra", "PHP Markdown Extra", "Tables, footnotes, definition lists, abbreviations", "python-markdown"),
        Flavor("pandoc", "Pandoc Markdown", "Pandoc's extended Markdown", "pandoc", "markdown"),
        Flavor(
            "commonmark_x",
            "CommonMark + Extensions",
            "Pandoc's CommonMark with common extensions",
            "pandoc",
            "commonmark_x",
        ),
        Flavor("mmd", "MultiMarkdown", "MultiMarkdown syntax", "pandoc", "markdown_mmd"),
        Flavor("rmd", "R Markdown", "R Markdown (code chunks shown, not executed)", "pandoc", "markdown"),
    )
}


def pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def is_available(flavor_id: str) -> bool:
    flavor = FLAVORS.get(flavor_id)
    return flavor is not None and (not flavor.requires_pandoc or pandoc_available())


# ----------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------


def _markdown_it_gfm() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    md.use(tasklists_plugin).use(footnote_plugin).use(anchors_plugin, max_level=6)
    # GitHub-style $math$: the $ must hug the formula and not touch digits ("$5 or $10" stays text).
    md.use(dollarmath_plugin, allow_space=False, allow_digits=False)
    return md


_MARKDOWN_IT: dict[str, Callable[[], MarkdownIt]] = {
    "gfm": _markdown_it_gfm,
    "commonmark": lambda: MarkdownIt("commonmark", {"html": True}),
}

_PYTHON_MARKDOWN_EXTENSIONS: dict[str, list[str]] = {
    "original": [],
    "extra": ["extra"],
}


def _render_pandoc(text: str, pandoc_format: str) -> str:
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise FlavorUnavailableError("pandoc is not installed")
    try:
        result = subprocess.run(
            [pandoc, "--from", pandoc_format, "--to", "html5", "--no-highlight", "--katex"],
            input=text,
            capture_output=True,
            text=True,
            timeout=PANDOC_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"pandoc timed out after {PANDOC_TIMEOUT_SECONDS}s") from exc
    if result.returncode != 0:
        raise RenderError(result.stderr.strip() or f"pandoc exited with status {result.returncode}")
    return result.stdout


def render_body(text: str, flavor_id: str) -> str:
    """Convert Markdown *text* to an HTML body fragment using *flavor_id*.

    Raises KeyError for an unknown flavor, FlavorUnavailableError when its
    backend is missing, RenderError when the backend fails.
    """
    flavor = FLAVORS[flavor_id]
    if flavor.backend == "markdown-it":
        return _MARKDOWN_IT[flavor.id]().render(text)
    if flavor.backend == "python-markdown":
        return markdown.markdown(text, extensions=_PYTHON_MARKDOWN_EXTENSIONS[flavor.id], output_format="html")
    assert flavor.pandoc_format is not None
    return _render_pandoc(text, flavor.pandoc_format)
