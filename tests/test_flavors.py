"""Flavor backends: each produces the HTML its syntax promises."""

import pytest

from md_viewer import flavors
from md_viewer.flavors import FLAVORS, FlavorUnavailableError, render_body

requires_pandoc = pytest.mark.skipif(not flavors.pandoc_available(), reason="pandoc not installed")

TABLE = "| a | b |\n|---|---|\n| 1 | 2 |\n"


def test_default_flavor_is_registered():
    assert flavors.DEFAULT_FLAVOR in FLAVORS


def test_every_flavor_has_a_backend():
    for flavor in FLAVORS.values():
        assert flavor.backend in {"markdown-it", "python-markdown", "pandoc"}
        assert (flavor.pandoc_format is not None) == flavor.requires_pandoc


def test_unknown_flavor_raises_key_error():
    with pytest.raises(KeyError):
        render_body("x", "nope")


def test_unknown_flavor_is_not_available():
    assert not flavors.is_available("nope")


@pytest.mark.parametrize("flavor_id", ["gfm", "commonmark", "original", "extra"])
def test_basic_markdown_in_builtin_flavors(flavor_id):
    out = render_body("Some *emphasis* and **strong**.", flavor_id)
    assert "<em>emphasis</em>" in out
    assert "<strong>strong</strong>" in out


def test_gfm_table():
    assert "<table>" in render_body(TABLE, "gfm")


def test_commonmark_has_no_tables():
    assert "<table>" not in render_body(TABLE, "commonmark")


def test_gfm_strikethrough():
    assert "<s>gone</s>" in render_body("~~gone~~", "gfm")


def test_gfm_task_list():
    out = render_body("- [x] done\n- [ ] todo\n", "gfm")
    assert 'type="checkbox"' in out
    assert "checked" in out


def test_gfm_footnote():
    out = render_body("Text[^1]\n\n[^1]: The note.\n", "gfm")
    assert "footnote" in out
    assert "The note." in out


def test_gfm_heading_anchor():
    assert 'id="hello-world"' in render_body("## Hello World\n", "gfm")


def test_gfm_allows_raw_html():
    assert "<kbd>Ctrl</kbd>" in render_body("Press <kbd>Ctrl</kbd>", "gfm")


def test_gfm_fenced_code_language_class():
    assert 'class="language-python"' in render_body("```python\nx = 1\n```\n", "gfm")


def test_extra_table_and_definition_list():
    assert "<table>" in render_body(TABLE, "extra")
    assert "<dl>" in render_body("Term\n: Definition\n", "extra")


def test_original_has_no_tables():
    assert "<table>" not in render_body(TABLE, "original")


def test_pandoc_flavor_without_pandoc_raises(monkeypatch):
    monkeypatch.setattr(flavors.shutil, "which", lambda _name: None)
    assert not flavors.is_available("pandoc")
    with pytest.raises(FlavorUnavailableError):
        render_body("# x", "pandoc")


def test_builtin_flavors_available_without_pandoc(monkeypatch):
    monkeypatch.setattr(flavors.shutil, "which", lambda _name: None)
    for flavor in FLAVORS.values():
        assert flavors.is_available(flavor.id) == (not flavor.requires_pandoc)


@requires_pandoc
@pytest.mark.parametrize("flavor_id", [f.id for f in FLAVORS.values() if f.requires_pandoc])
def test_pandoc_flavors_render(flavor_id):
    out = render_body("# Title\n\nSome *text*.\n", flavor_id)
    assert "<em>text</em>" in out
    assert "Title</h1>" in out


@requires_pandoc
def test_pandoc_table():
    assert "<table" in render_body(TABLE, "pandoc")


@requires_pandoc
def test_pandoc_bad_format_raises_render_error(monkeypatch):
    with pytest.raises(flavors.RenderError):
        flavors._render_pandoc("x", "not-a-format")
