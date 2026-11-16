"""Syntax highlighting for fenced code blocks, applied after any flavor's backend.

All backends emit code blocks in one of two shapes:

* ``<pre><code class="language-python">…</code></pre>`` (markdown-it, python-markdown)
* ``<pre class="python"><code>…</code></pre>`` (pandoc with --no-highlight)

:func:`highlight_code_blocks` rewrites both to pygments-highlighted
``<pre class="highlight"><code class="language-…">`` so styles only need to
target one structure.

:func:`highlight_source` colours a whole Markdown file for View → Show Source.

Colours come from two Pygments themes (:class:`Themes`), one for light pages and
one for dark pages: the built-in defaults, or the user's choice in Preferences.
"""

from __future__ import annotations

import functools
import html
import re
from dataclasses import dataclass

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import MarkdownLexer, get_lexer_by_name
from pygments.styles import get_all_styles, get_style_by_name
from pygments.token import Text
from pygments.util import ClassNotFound

LIGHT_THEME = "default"
DARK_THEME = "github-dark"
# Text colour for themes that don't set one, picked by the theme's background.
_TEXT_ON_LIGHT = "#1f2328"
_TEXT_ON_DARK = "#e6edf3"

# Languages handled client-side in a later stage (diagrams, math) — never highlighted.
_SKIP_LANGUAGES = frozenset({"mermaid", "math"})

_CODE_BLOCK_RE = re.compile(
    r"<pre(?P<pre_attrs>[^>]*)><code(?P<code_attrs>[^>]*)>(?P<body>.*?)</code></pre>",
    re.DOTALL,
)
_CLASS_RE = re.compile(r'class="([^"]*)"')
_FORMATTER = HtmlFormatter(nowrap=True)
# stripnl=False: keep leading/trailing blank lines, so copying from the source view is exact.
_MARKDOWN_LEXER = MarkdownLexer(stripnl=False)


@functools.cache
def available_themes() -> list[str]:
    """Names of the installed Pygments themes (the set differs between Pygments versions)."""
    return sorted(get_all_styles())


def resolve_theme(name: str, fallback: str) -> str:
    """*name* if that theme is installed, else *fallback*."""
    return name if name in available_themes() else fallback


@dataclass(frozen=True)
class Themes:
    """Pygments themes for light and dark pages.

    ``custom`` = chosen in Preferences. A chosen theme also paints the code block
    background and base text colour in rendered documents, so e.g. a dark theme's
    light text never lands on a style's light code background. The defaults leave
    each style's own code background alone.
    """

    light: str = LIGHT_THEME
    dark: str = DARK_THEME
    custom: bool = False

    @classmethod
    def chosen(cls, light: str, dark: str) -> Themes:
        """The user's choice, with themes that aren't installed replaced by the defaults."""
        return cls(resolve_theme(light, LIGHT_THEME), resolve_theme(dark, DARK_THEME), custom=True)


DEFAULT_THEMES = Themes()


def _language(pre_attrs: str, code_attrs: str) -> str | None:
    for attrs in (code_attrs, pre_attrs):
        match = _CLASS_RE.search(attrs)
        if not match:
            continue
        classes = match.group(1).split()
        for cls in classes:
            if cls.startswith("language-"):
                return cls.removeprefix("language-")
        # pandoc: <pre class="python"> or <pre class="sourceCode python">
        candidates = [c for c in classes if c != "sourceCode"]
        if candidates:
            return candidates[0]
    return None


def _highlight_match(match: re.Match[str]) -> str:
    lang = _language(match.group("pre_attrs"), match.group("code_attrs"))
    if lang is None or lang.lower() in _SKIP_LANGUAGES:
        return match.group(0)
    try:
        lexer = get_lexer_by_name(lang.lower())
    except ClassNotFound:
        return match.group(0)
    code = html.unescape(match.group("body"))
    highlighted = highlight(code, lexer, _FORMATTER)
    return f'<pre class="highlight"><code class="language-{html.escape(lang)}">{highlighted}</code></pre>'


def highlight_code_blocks(body_html: str) -> str:
    """Return *body_html* with every recognised fenced code block syntax-highlighted."""
    return _CODE_BLOCK_RE.sub(_highlight_match, body_html)


def highlight_source(text: str) -> str:
    """Markdown *text* as highlighted, HTML-escaped markup for a ``<pre>`` (fenced code is
    coloured by its language)."""
    return highlight(text, _MARKDOWN_LEXER, _FORMATTER)


@functools.cache
def theme_css(theme: str, selector: str = ".highlight") -> str:
    """Token colours of Pygments *theme* for elements under *selector*."""
    return HtmlFormatter(style=theme).get_style_defs(selector)


def _is_light(colour: str) -> bool:
    digits = colour.lstrip("#")
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    try:
        red, green, blue = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return True
    return 0.299 * red + 0.587 * green + 0.114 * blue > 128


@functools.cache
def theme_colours(theme: str) -> tuple[str, str]:
    """(background, text colour) of Pygments *theme*."""
    style = get_style_by_name(theme)
    background = style.background_color or "#ffffff"
    text = style.style_for_token(Text).get("color")
    if text:
        return background, f"#{text}"
    return background, _TEXT_ON_LIGHT if _is_light(background) else _TEXT_ON_DARK


def _for_scheme(scheme: str, light: str, dark: str) -> str:
    """*light* or *dark* CSS for a fixed scheme; for "auto", both with dark under a media query."""
    if scheme == "light":
        return light
    if scheme == "dark":
        return dark
    return f"{light}\n@media (prefers-color-scheme: dark) {{\n{dark}\n}}\n"


def highlight_css(scheme: str = "auto", themes: Themes = DEFAULT_THEMES) -> str:
    """Code block colours for a rendered document whose style has colour *scheme*
    ("light", "dark" or "auto")."""

    def css(theme: str) -> str:
        if not themes.custom:
            return theme_css(theme)
        background, text = theme_colours(theme)
        return (
            f"{theme_css(theme)}\n"
            f".markdown-body pre.highlight {{ background: {background}; color: {text}; }}\n"
            ".markdown-body pre.highlight > code { background: transparent; color: inherit; }"
        )

    return _for_scheme(scheme, css(themes.light), css(themes.dark))


def source_css(scheme: str = "auto", themes: Themes = DEFAULT_THEMES) -> str:
    """Colours for the source view: the whole page takes the theme's background."""

    def css(theme: str) -> str:
        background, text = theme_colours(theme)
        return f"{theme_css(theme)}\nbody {{ background: {background}; color: {text}; }}"

    return _for_scheme(scheme, css(themes.light), css(themes.dark))


def preview_css(themes: Themes) -> str:
    """Colours for the Preferences preview: ``.light`` and ``.dark`` panes side by side."""
    parts = []
    for pane, theme in (("light", themes.light), ("dark", themes.dark)):
        background, text = theme_colours(theme)
        parts.append(theme_css(theme, f".{pane} .highlight"))
        parts.append(f".{pane} {{ background: {background}; color: {text}; }}")
    return "\n".join(parts)
