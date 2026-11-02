"""Flavor-independent HTML post-processing."""

import pytest

from md_viewer.flavors import FLAVORS, pandoc_available, render_body
from md_viewer.postprocess import Heading, postprocess, slugify

requires_pandoc = pytest.mark.skipif(not pandoc_available(), reason="pandoc not installed")


@pytest.mark.parametrize(
    ("text", "slug"),
    [("Hello World", "hello-world"), ("What's new?", "whats-new"), ("C++ & Rust", "c--rust"), ("Ünïcode", "ünïcode")],
)
def test_slugify(text, slug):
    assert slugify(text) == slug


def test_ids_added_and_headings_collected():
    result = postprocess("<h1>Title</h1><p>x</p><h2>Sub <em>part</em> &amp; more</h2>")
    assert '<h1 id="title">Title</h1>' in result.body
    assert result.headings == [Heading(1, "title", "Title"), Heading(2, "sub-part--more", "Sub part & more")]


def test_existing_ids_kept_and_avoided():
    result = postprocess('<h2 id="intro">Intro</h2><h2>Intro</h2><h2>Intro</h2>')
    assert [h.id for h in result.headings] == ["intro", "intro-1", "intro-2"]
    assert result.body.count('id="intro"') == 1


def test_heading_with_attributes_and_empty_text():
    result = postprocess('<h3 class="x"></h3>')
    assert result.headings == [Heading(3, "section", "")]
    assert '<h3 id="section" class="x">' in result.body


def test_pandoc_mermaid_normalised():
    result = postprocess('<pre class="mermaid"><code>graph TD; A--&gt;B</code></pre>')
    assert result.body == '<pre><code class="language-mermaid">graph TD; A--&gt;B</code></pre>'
    assert result.has_mermaid


def test_math_fence_becomes_block():
    result = postprocess('<pre><code class="language-math">a &lt; b\n</code></pre>')
    assert result.body == '<div class="math block">a &lt; b\n</div>'
    assert result.has_math


def test_plain_document_needs_no_scripts():
    result = postprocess("<p>just text with $5</p>")
    assert not result.has_math
    assert not result.has_mermaid


def test_gfm_math_end_to_end():
    result = postprocess(render_body("Inline $x^2$.\n\n$$\na+b\n$$\n\nPrice $5 or $10.\n", "gfm"))
    assert '<span class="math inline">x^2</span>' in result.body
    assert '<div class="math block">' in result.body
    assert "Price $5 or $10." in result.body
    assert result.has_math


def test_gfm_math_fence_end_to_end():
    assert postprocess(render_body("```math\n\\sqrt{2}\n```\n", "gfm")).has_math


def test_gfm_mermaid_end_to_end():
    assert postprocess(render_body("```mermaid\ngraph TD; A-->B\n```\n", "gfm")).has_mermaid


@pytest.mark.parametrize("flavor_id", ["commonmark", "original", "extra"])
def test_flavors_without_math_syntax_leave_dollars(flavor_id):
    assert not postprocess(render_body("Inline $x^2$.\n", flavor_id)).has_math


@pytest.mark.parametrize("flavor_id", list(FLAVORS))
def test_every_flavor_gets_heading_ids(flavor_id):
    if FLAVORS[flavor_id].requires_pandoc and not pandoc_available():
        pytest.skip("pandoc not installed")
    result = postprocess(render_body("# Top\n\n## Next Part\n", flavor_id))
    assert [(h.level, h.text) for h in result.headings] == [(1, "Top"), (2, "Next Part")]
    assert all(h.id for h in result.headings)


@requires_pandoc
def test_pandoc_math_and_mermaid():
    result = postprocess(render_body("Inline $x^2$.\n\n```mermaid\ngraph TD; A-->B\n```\n", "pandoc"))
    assert result.has_math
    assert result.has_mermaid
