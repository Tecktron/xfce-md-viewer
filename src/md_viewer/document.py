"""Assemble a complete, self-contained HTML document from Markdown text.

Pure (no GTK) so the whole pipeline is unit-testable:
Markdown → flavor backend → syntax highlighting → page with style CSS + CSP.
"""

from __future__ import annotations

import html

from .flavors import render_body
from .highlight import highlight_code_blocks, highlight_css

# Markdown can embed raw HTML, including <script>. Block all scripts and any
# network access; allow inline styles and local / data: images only.
CONTENT_SECURITY_POLICY = "default-src 'none'; style-src 'unsafe-inline'; img-src file: data:; media-src file: data:"

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


def build_page(body_html: str, style_css: str, title: str, scheme: str = "auto") -> str:
    """Wrap an already-rendered body fragment in a full HTML page."""
    return _TEMPLATE.format(
        csp=CONTENT_SECURITY_POLICY,
        title=html.escape(title),
        highlight_css=highlight_css(scheme),
        # A user style containing "</style" must not be able to close the element early.
        style_css=style_css.replace("</", "<\\/"),
        body=body_html,
    )


def render_document(text: str, flavor_id: str, style_css: str, title: str, scheme: str = "auto") -> str:
    """Render Markdown *text* with *flavor_id* into a full page styled by *style_css*."""
    body = highlight_code_blocks(render_body(text, flavor_id))
    return build_page(body, style_css, title, scheme)
