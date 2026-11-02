"""Flavor-independent clean-up of the HTML body, run before syntax highlighting.

Different backends emit math, diagrams and headings differently; this pass
normalises them so the page scripts and the table of contents see one shape:

* Mermaid:  ``<pre><code class="language-mermaid">…</code></pre>``
* Math:     ``<span class="math inline">…</span>`` and ``<div class="math block">…</div>``
            (pandoc's ``<span class="math display">`` is also accepted by the page script)
* Headings: every ``<hN>`` gets a unique ``id`` (existing ids are kept)

Pure (no GTK) and unit-tested.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Heading:
    level: int
    id: str
    text: str


@dataclass(frozen=True)
class Processed:
    body: str
    headings: list[Heading] = field(default_factory=list)
    has_math: bool = False
    has_mermaid: bool = False


_PANDOC_MERMAID_RE = re.compile(r'<pre class="mermaid"><code>(.*?)</code></pre>', re.DOTALL)
_MATH_FENCE_RE = re.compile(r'<pre><code class="language-math">(.*?)</code></pre>', re.DOTALL)
_HEADING_RE = re.compile(r"<h([1-6])(\s[^>]*)?>(.*?)</h\1>", re.DOTALL | re.IGNORECASE)
_ID_RE = re.compile(r'\bid="([^"]*)"')
_TAG_RE = re.compile(r"<[^>]+>")
_MATH_RE = re.compile(r'class="math (?:inline|block|display)"')
_SLUG_DROP_RE = re.compile(r"[^\w\- ]")


def slugify(text: str) -> str:
    """GitHub-style heading slug: lower case, punctuation dropped, spaces to hyphens."""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return _SLUG_DROP_RE.sub("", text).replace(" ", "-")


def _heading_text(inner_html: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub("", inner_html)).split())


def _add_heading_ids(body: str) -> tuple[str, list[Heading]]:
    matches = list(_HEADING_RE.finditer(body))
    used = {m.group(1) for match in matches if (m := _ID_RE.search(match.group(2) or ""))}
    headings: list[Heading] = []

    def unique(base: str) -> str:
        base = base or "section"
        candidate, n = base, 0
        while candidate in used:
            n += 1
            candidate = f"{base}-{n}"
        used.add(candidate)
        return candidate

    def replace(match: re.Match[str]) -> str:
        level, attrs, inner = int(match.group(1)), match.group(2) or "", match.group(3)
        text = _heading_text(inner)
        existing = _ID_RE.search(attrs)
        if existing:
            headings.append(Heading(level, existing.group(1), text))
            return match.group(0)
        heading_id = unique(slugify(text))
        headings.append(Heading(level, heading_id, text))
        return f'<h{level} id="{html.escape(heading_id)}"{attrs}>{inner}</h{level}>'

    return _HEADING_RE.sub(replace, body), headings


def postprocess(body: str) -> Processed:
    body = _PANDOC_MERMAID_RE.sub(r'<pre><code class="language-mermaid">\1</code></pre>', body)
    body = _MATH_FENCE_RE.sub(r'<div class="math block">\1</div>', body)
    body, headings = _add_heading_ids(body)
    return Processed(
        body=body,
        headings=headings,
        has_math=bool(_MATH_RE.search(body)),
        has_mermaid='class="language-mermaid"' in body,
    )
