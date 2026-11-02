"""Link classification rules."""

import pytest

from md_viewer.links import LinkAction, classify_link, is_markdown_uri, strip_fragment

DOC = "file:///home/u/docs/README.md"


def test_same_document_anchor_allowed():
    assert classify_link(f"{DOC}#install", DOC) is LinkAction.ALLOW


def test_anchor_into_other_markdown_opens_document():
    assert classify_link("file:///home/u/docs/OTHER.md#x", DOC) is LinkAction.OPEN_DOCUMENT


def test_same_document_without_fragment_is_a_document_open():
    # e.g. a link back to the file itself: treat as (re)opening it.
    assert classify_link(DOC, DOC) is LinkAction.OPEN_DOCUMENT


@pytest.mark.parametrize("name", ["a.md", "a.MD", "a.markdown", "a.Rmd", "a.mkd"])
def test_local_markdown_opens_in_viewer(name):
    assert classify_link(f"file:///home/u/docs/{name}", DOC) is LinkAction.OPEN_DOCUMENT


@pytest.mark.parametrize("uri", ["file:///home/u/docs/report.pdf", "file:///home/u/docs/img.png"])
def test_local_non_markdown_opens_externally(uri):
    assert classify_link(uri, DOC) is LinkAction.OPEN_EXTERNAL


@pytest.mark.parametrize(
    "uri",
    ["https://example.com", "http://example.com/a.md", "mailto:a@b.c", "HTTPS://EXAMPLE.COM"],
)
def test_web_and_mail_open_externally(uri):
    # Remote .md links go to the browser too — the viewer only opens local files.
    assert classify_link(uri, DOC) is LinkAction.OPEN_EXTERNAL


@pytest.mark.parametrize("uri", ["javascript:alert(1)", "data:text/html,hi", "about:blank", "weird:thing"])
def test_dangerous_or_unknown_schemes_blocked(uri):
    assert classify_link(uri, DOC) is LinkAction.BLOCK


def test_no_current_document():
    assert classify_link("file:///x.md#a", None) is LinkAction.OPEN_DOCUMENT


def test_helpers():
    assert strip_fragment("file:///a.md#b") == "file:///a.md"
    assert is_markdown_uri("file:///a/b.markdown?x=1")
    assert not is_markdown_uri("file:///a/b.txt")
