"""Syntax highlighting for fenced code blocks, applied after any flavor's backend.

All backends emit code blocks in one of two shapes:

* ``<pre><code class="language-python">…</code></pre>`` (markdown-it, python-markdown)
* ``<pre class="python"><code>…</code></pre>`` (pandoc with --no-highlight)

:func:`highlight_code_blocks` rewrites both to pygments-highlighted
``<pre class="highlight"><code class="language-…">`` so styles only need to
target one structure.
"""

from __future__ import annotations

import html
import re

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

LIGHT_THEME = "default"
DARK_THEME = "github-dark"

# Languages handled client-side in a later stage (diagrams, math) — never highlighted.
_SKIP_LANGUAGES = frozenset({"mermaid", "math"})

_CODE_BLOCK_RE = re.compile(
    r"<pre(?P<pre_attrs>[^>]*)><code(?P<code_attrs>[^>]*)>(?P<body>.*?)</code></pre>",
    re.DOTALL,
)
_CLASS_RE = re.compile(r'class="([^"]*)"')
_FORMATTER = HtmlFormatter(nowrap=True)


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


def highlight_css(scheme: str = "auto") -> str:
    """Pygments token colours for a style's colour *scheme* ("light", "dark" or "auto").

    "auto" emits light colours plus dark ones under ``prefers-color-scheme: dark``.
    """
    light = HtmlFormatter(style=LIGHT_THEME).get_style_defs(".highlight")
    dark = HtmlFormatter(style=DARK_THEME).get_style_defs(".highlight")
    if scheme == "light":
        return light
    if scheme == "dark":
        return dark
    return f"{light}\n@media (prefers-color-scheme: dark) {{\n{dark}\n}}\n"
