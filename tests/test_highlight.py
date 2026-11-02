"""Shared syntax highlighting step."""

from md_viewer.highlight import highlight_code_blocks, highlight_css


def test_markdown_it_shape_is_highlighted():
    out = highlight_code_blocks('<pre><code class="language-python">x = 1\n</code></pre>')
    assert '<pre class="highlight"><code class="language-python">' in out
    assert "<span" in out


def test_pandoc_shape_is_highlighted():
    out = highlight_code_blocks('<pre class="python"><code>x = 1\n</code></pre>')
    assert '<code class="language-python">' in out
    assert "<span" in out


def test_pandoc_sourcecode_class_is_ignored():
    out = highlight_code_blocks('<pre class="sourceCode python"><code>x = 1\n</code></pre>')
    assert '<code class="language-python">' in out


def test_html_entities_are_not_double_escaped():
    out = highlight_code_blocks('<pre><code class="language-html">&lt;b&gt;</code></pre>')
    assert "&amp;lt;" not in out
    assert "&lt;" in out


def test_unknown_language_left_alone():
    block = '<pre><code class="language-nosuchlang">x</code></pre>'
    assert highlight_code_blocks(block) == block


def test_no_language_left_alone():
    block = "<pre><code>plain\n</code></pre>"
    assert highlight_code_blocks(block) == block


def test_mermaid_left_alone():
    block = '<pre><code class="language-mermaid">graph TD; A--&gt;B</code></pre>'
    assert highlight_code_blocks(block) == block


def test_multiple_blocks_are_independent():
    src = '<pre><code class="language-python">a</code></pre><p>mid</p><pre><code class="language-bash">b</code></pre>'
    out = highlight_code_blocks(src)
    assert out.count('class="highlight"') == 2
    assert "<p>mid</p>" in out


def test_css_auto_has_light_and_dark():
    css = highlight_css("auto")
    assert ".highlight" in css
    assert "prefers-color-scheme: dark" in css


def test_css_fixed_schemes_have_no_media_query():
    light, dark = highlight_css("light"), highlight_css("dark")
    assert "prefers-color-scheme" not in light
    assert "prefers-color-scheme" not in dark
    assert light != dark
