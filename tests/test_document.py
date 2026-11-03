"""Full-page assembly."""

from md_viewer.document import CONTENT_SECURITY_POLICY, REMOTE_IMAGES_POLICY, build_page, render_document


def test_page_structure():
    page = build_page("<p>hi</p>", "body{color:red}", "Doc")
    assert page.startswith("<!doctype html>")
    assert '<div class="markdown-body">\n<p>hi</p>' in page
    assert "<article" not in page  # classless styles (Simple.css) draw <article> as a card
    assert "body{color:red}" in page
    assert "<title>Doc</title>" in page


def test_csp_blocks_scripts_and_network():
    page = build_page("", "", "t")
    assert CONTENT_SECURITY_POLICY in page
    assert "default-src 'none'" in CONTENT_SECURITY_POLICY
    assert "script-src" not in CONTENT_SECURITY_POLICY
    assert "http" not in CONTENT_SECURITY_POLICY


def test_title_is_escaped():
    assert "<title>a &lt;b&gt;</title>" in build_page("", "", "a <b>")


def test_style_cannot_close_style_element():
    page = build_page("", "x{}</style><script>alert(1)</script>", "t")
    assert "</style><script>" not in page


def test_style_braces_survive_formatting():
    assert "a { b: c; }" in build_page("", "a { b: c; }", "t")


def test_scheme_selects_highlight_css():
    assert "prefers-color-scheme: dark" in build_page("", "", "t", "auto")
    assert "prefers-color-scheme: dark" not in build_page("", "", "t", "light")


def test_render_document_end_to_end():
    rendered = render_document("# Hi\n\n```python\nx = 1\n```\n", "gfm", "", "t")
    assert "Hi</h1>" in rendered.page
    assert 'class="highlight"' in rendered.page
    assert [h.id for h in rendered.headings] == ["hi"]
    assert not rendered.has_math
    assert not rendered.has_mermaid


def test_katex_css_only_when_math():
    plain = render_document("no math", "gfm", "", "t")
    math = render_document("Euler $e^{i\\pi}+1=0$", "gfm", "", "t")
    assert ".katex" not in plain.page
    assert math.has_math
    assert ".katex" in math.page
    assert "url(file://" in math.page  # fonts resolved to the bundled copies
    assert "url(fonts/" not in math.page


def test_csp_allows_local_fonts_only():
    assert "font-src file:;" in CONTENT_SECURITY_POLICY
    assert "font-src file:;" in REMOTE_IMAGES_POLICY


def test_mermaid_flag():
    assert render_document("```mermaid\ngraph TD; A-->B\n```\n", "gfm", "", "t").has_mermaid


def test_remote_images_opt_in():
    assert CONTENT_SECURITY_POLICY in build_page("", "", "t")
    page = build_page("", "", "t", allow_remote_images=True)
    assert REMOTE_IMAGES_POLICY in page
    assert "img-src file: data: https: http:" in REMOTE_IMAGES_POLICY


def test_remote_policy_still_blocks_scripts():
    assert "default-src 'none'" in REMOTE_IMAGES_POLICY
    assert "script-src" not in REMOTE_IMAGES_POLICY


def test_base_css_comes_before_style_css():
    page = build_page("", "MY-STYLE{}", "t")
    assert "task-list-item" in page
    assert page.index("task-list-item") < page.index("MY-STYLE")
