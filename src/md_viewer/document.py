"""Assemble a complete, self-contained HTML document from Markdown text.

Pure (no GTK) so the whole pipeline is unit-testable:
Markdown → flavor backend → post-processing → syntax highlighting → page with CSS + CSP.

The page never runs scripts of its own (the CSP has no script-src). Math and
diagrams are rendered by the viewer's own scripts in an isolated world; see
``Rendered.has_math`` / ``has_mermaid`` and ui/window.py.
"""

from __future__ import annotations

import functools
import html
from dataclasses import dataclass, field

from .flavors import render_body
from .highlight import highlight_code_blocks, highlight_css
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


_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
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
<article class="markdown-body">
{body}
</article>
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
    allow_remote_images: bool = False,
    include_katex_css: bool = False,
) -> str:
    """Wrap an already-rendered body fragment in a full HTML page."""
    return _TEMPLATE.format(
        csp=content_security_policy(allow_remote_images),
        title=html.escape(title),
        highlight_css=highlight_css(scheme),
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
    allow_remote_images: bool = False,
) -> Rendered:
    """Render Markdown *text* with *flavor_id* into a full page styled by *style_css*."""
    processed = postprocess(render_body(text, flavor_id))
    page = build_page(
        highlight_code_blocks(processed.body),
        style_css,
        title,
        scheme,
        allow_remote_images=allow_remote_images,
        include_katex_css=processed.has_math,
    )
    return Rendered(page, processed.headings, processed.has_math, processed.has_mermaid)
