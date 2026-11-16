"""Assemble a complete, self-contained HTML document from Markdown text.

Pure (no GTK) so the whole pipeline is unit-testable:
Markdown → flavor backend → post-processing → syntax highlighting → page with CSS + CSP.

The page never runs scripts of its own (the CSP has no script-src). Math and
diagrams are rendered by the viewer's own scripts in an isolated world; see
``Rendered.has_math`` / ``has_mermaid`` and ui/window.py.

Also builds the source view page (View → Show Source) and the Preferences theme preview.
"""

from __future__ import annotations

import functools
import html
from dataclasses import dataclass, field

from .flavors import render_body
from .highlight import (
    DEFAULT_THEMES,
    Themes,
    highlight_code_blocks,
    highlight_css,
    highlight_source,
    preview_css,
    source_css,
)
from .paths import vendor_dir
from .postprocess import Heading, postprocess

# Markdown can embed raw HTML, including <script>. Block all scripts and any
# network access; allow inline styles, local fonts (KaTeX) and local / data: images.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'unsafe-inline'; font-src file:; img-src file: data:; media-src file: data:"
)
# Opt-in (Preferences → "Load remote images"): images and media may also come
# from the web. Scripts stay blocked either way.
REMOTE_IMAGES_POLICY = (
    "default-src 'none'; style-src 'unsafe-inline'; font-src file:; "
    "img-src file: data: https: http:; media-src file: data: https: http:"
)


@dataclass(frozen=True)
class Rendered:
    page: str
    headings: list[Heading] = field(default_factory=list)
    has_math: bool = False
    has_mermaid: bool = False


def content_security_policy(allow_remote_images: bool) -> str:
    return REMOTE_IMAGES_POLICY if allow_remote_images else CONTENT_SECURITY_POLICY


# Structural defaults that every style (built-in or user) gets first and may override.
# The wrapper is a <div>, not <article>: classless stylesheets such as Simple.css
# draw every <article> as a bordered card.
BASE_CSS = """.markdown-body .task-list-item { list-style-type: none; }
.markdown-body .task-list-item input[type="checkbox"] { margin: 0 .35em .25em -1.4em; vertical-align: middle; }"""

_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<style>
{base_css}
</style>
<style>
{highlight_css}
</style>
<style>
{extra_css}
</style>
<style>
{style_css}
</style>
</head>
<body>
<div class="markdown-body">
{body}
</div>
</body>
</html>
"""


# View → Show Source: the file itself, highlighted. Long lines wrap; no style CSS.
_SOURCE_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<meta name="color-scheme" content="{color_scheme}">
<title>{title}</title>
<style>
html, body {{ margin: 0; }}
pre.source {{ margin: 0; padding: 16px 24px; background: transparent; font-family: monospace;
             font-size: 0.9rem; line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; tab-size: 4; }}
</style>
<style>
{highlight_css}
</style>
</head>
<body>
<pre class="highlight source"><code>{body}</code></pre>
</body>
</html>
"""

_COLOR_SCHEMES = {"light": "light", "dark": "dark"}  # anything else ("auto") → "light dark"

# Preferences → Highlighting: the same sample in the light and the dark theme.
PREVIEW_SAMPLE = """# Heading

Some *emphasis*, **bold**,
`code` and a [link](url).

- List item
> A quote

```python
def greet(name):
    # Say hello
    return f"Hi {name}!"
```
"""

_PREVIEW_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<style>
html, body {{ margin: 0; height: 100%; }}
body {{ display: flex; }}
.pane {{ flex: 1; min-width: 0; padding: 8px 12px; overflow: hidden; }}
.caption {{ font: 600 11px sans-serif; opacity: .6; margin-bottom: 6px; }}
pre {{ margin: 0; font-family: monospace; font-size: 12px; line-height: 1.4; white-space: pre-wrap; }}
</style>
<style>
{highlight_css}
</style>
</head>
<body>
<div class="pane light"><div class="caption">Light</div><pre class="highlight"><code>{body}</code></pre></div>
<div class="pane dark"><div class="caption">Dark</div><pre class="highlight"><code>{body}</code></pre></div>
</body>
</html>
"""


@functools.cache
def katex_css() -> str:
    """Bundled KaTeX stylesheet with its font URLs pointing at the bundled fonts."""
    katex = vendor_dir() / "katex"
    css = (katex / "katex.min.css").read_text(encoding="utf-8")
    return css.replace("url(fonts/", f"url({(katex / 'fonts').as_uri()}/")


def build_page(
    body_html: str,
    style_css: str,
    title: str,
    scheme: str = "auto",
    *,
    themes: Themes = DEFAULT_THEMES,
    allow_remote_images: bool = False,
    include_katex_css: bool = False,
) -> str:
    """Wrap an already-rendered body fragment in a full HTML page."""
    return _TEMPLATE.format(
        csp=content_security_policy(allow_remote_images),
        title=html.escape(title),
        base_css=BASE_CSS,
        highlight_css=highlight_css(scheme, themes),
        extra_css=katex_css() if include_katex_css else "",
        # A user style containing "</style" must not be able to close the element early.
        style_css=style_css.replace("</", "<\\/"),
        body=body_html,
    )


def render_document(
    text: str,
    flavor_id: str,
    style_css: str,
    title: str,
    scheme: str = "auto",
    *,
    themes: Themes = DEFAULT_THEMES,
    allow_remote_images: bool = False,
) -> Rendered:
    """Render Markdown *text* with *flavor_id* into a full page styled by *style_css*."""
    processed = postprocess(render_body(text, flavor_id))
    page = build_page(
        highlight_code_blocks(processed.body),
        style_css,
        title,
        scheme,
        themes=themes,
        allow_remote_images=allow_remote_images,
        include_katex_css=processed.has_math,
    )
    return Rendered(page, processed.headings, processed.has_math, processed.has_mermaid)


def build_source_page(text: str, title: str, scheme: str = "auto", themes: Themes = DEFAULT_THEMES) -> str:
    """The Markdown *text* itself, highlighted, as a full page (View → Show Source)."""
    return _SOURCE_TEMPLATE.format(
        csp=CONTENT_SECURITY_POLICY,
        color_scheme=_COLOR_SCHEMES.get(scheme, "light dark"),
        title=html.escape(title),
        highlight_css=source_css(scheme, themes),
        body=highlight_source(text),
    )


def build_theme_preview(themes: Themes) -> str:
    """:data:`PREVIEW_SAMPLE` in the light and the dark theme, side by side."""
    return _PREVIEW_TEMPLATE.format(
        csp=CONTENT_SECURITY_POLICY,
        highlight_css=preview_css(themes),
        body=highlight_source(PREVIEW_SAMPLE),
    )
