"""Full-page assembly."""

from md_viewer.document import CONTENT_SECURITY_POLICY, build_page, render_document


def test_page_structure():
    page = build_page("<p>hi</p>", "body{color:red}", "Doc")
    assert page.startswith("<!doctype html>")
    assert '<article class="markdown-body">\n<p>hi</p>' in page
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
    page = render_document("# Hi\n\n```python\nx = 1\n```\n", "gfm", "", "t")
    assert "Hi</h1>" in page
    assert 'class="highlight"' in page
