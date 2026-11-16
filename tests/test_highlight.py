"""Shared syntax highlighting step."""

from md_viewer.highlight import (
    DARK_THEME,
    LIGHT_THEME,
    Themes,
    available_themes,
    highlight_code_blocks,
    highlight_css,
    highlight_source,
    preview_css,
    resolve_theme,
    source_css,
    theme_colours,
)


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


# ----------------------------------------------------------------------
# Themes and the source view
# ----------------------------------------------------------------------


def test_default_themes_are_installed():
    assert {LIGHT_THEME, DARK_THEME} <= set(available_themes())


def test_resolve_theme_falls_back_when_not_installed():
    assert resolve_theme("monokai", LIGHT_THEME) == "monokai"
    assert resolve_theme("no-such-theme", LIGHT_THEME) == LIGHT_THEME


def test_chosen_themes_replace_missing_ones_with_defaults():
    themes = Themes.chosen("no-such-theme", "monokai")
    assert themes == Themes(LIGHT_THEME, "monokai", custom=True)


def test_default_themes_keep_the_styles_code_background():
    assert "pre.highlight" not in highlight_css("auto")


def test_chosen_themes_paint_the_code_background():
    css = highlight_css("light", Themes("monokai", DARK_THEME, custom=True))
    background, text = theme_colours("monokai")
    assert f".markdown-body pre.highlight {{ background: {background}; color: {text}; }}" in css


def test_chosen_themes_follow_the_scheme():
    css = highlight_css("auto", Themes("monokai", "solarized-dark", custom=True))
    light, dark = css.split("prefers-color-scheme: dark")
    assert theme_colours("monokai")[0] in light
    assert theme_colours("solarized-dark")[0] in dark


def test_dark_theme_gets_light_text():
    background, text = theme_colours(DARK_THEME)
    red, green, blue = (int(text[i : i + 2], 16) for i in (1, 3, 5))
    assert red + green + blue > 3 * 128


def test_source_css_colours_the_page():
    background, _ = theme_colours(LIGHT_THEME)
    assert f"body {{ background: {background};" in source_css("light")


def test_preview_css_has_both_panes():
    css = preview_css(Themes("monokai", "fruity", custom=True))
    assert ".light .highlight" in css
    assert ".dark .highlight" in css
    assert theme_colours("fruity")[0] in css


def test_highlight_source_is_escaped_and_exact():
    out = highlight_source("\n\n# Title\n<script>alert(1)</script>\n")
    assert out.startswith("\n\n")  # leading blank lines kept: copying from the source view is exact
    assert '<span class="gh"># Title</span>' in out
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_highlight_source_colours_fenced_code_by_language():
    assert '<span class="k">def</span>' in highlight_source("```python\ndef f(): pass\n```\n")
