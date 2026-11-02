"""Style discovery: built-in + user dirs, header parsing, overrides."""

from md_viewer import styles
from md_viewer.paths import builtin_styles_dir
from md_viewer.styles import discover_styles, resolve_style


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_header_name_and_description(tmp_path):
    _write(tmp_path / "b" / "fancy.css", "/* name: Fancy Style\n   description: Very fancy */\nbody{}")
    found = discover_styles(tmp_path / "b", tmp_path / "u")
    assert found["fancy"].name == "Fancy Style"
    assert found["fancy"].description == "Very fancy"
    assert found["fancy"].builtin


def test_scheme_parsed(tmp_path):
    _write(tmp_path / "b" / "d.css", "/* name: D\n   scheme: dark */")
    assert discover_styles(tmp_path / "b", tmp_path / "u")["d"].scheme == "dark"


def test_scheme_defaults_to_auto_and_rejects_junk(tmp_path):
    _write(tmp_path / "b" / "none.css", "/* name: None */")
    _write(tmp_path / "b" / "junk.css", "/* name: Junk\n   scheme: purple */")
    found = discover_styles(tmp_path / "b", tmp_path / "u")
    assert found["none"].scheme == "auto"
    assert found["junk"].scheme == "auto"


def test_name_falls_back_to_filename(tmp_path):
    _write(tmp_path / "u" / "my-dark_theme.css", "body{}")
    found = discover_styles(tmp_path / "b", tmp_path / "u")
    assert found["my-dark_theme"].name == "My Dark Theme"
    assert not found["my-dark_theme"].builtin


def test_user_style_overrides_builtin(tmp_path):
    _write(tmp_path / "b" / "github.css", "/* name: GitHub */")
    _write(tmp_path / "u" / "github.css", "/* name: My GitHub */")
    found = discover_styles(tmp_path / "b", tmp_path / "u")
    assert found["github"].name == "My GitHub"
    assert not found["github"].builtin


def test_missing_dirs_are_fine(tmp_path):
    assert discover_styles(tmp_path / "nope", tmp_path / "nada") == {}


def test_non_css_files_ignored(tmp_path):
    _write(tmp_path / "b" / "readme.txt", "x")
    assert discover_styles(tmp_path / "b", tmp_path / "u") == {}


def test_sorted_by_display_name(tmp_path):
    _write(tmp_path / "b" / "a.css", "/* name: Zebra */")
    _write(tmp_path / "b" / "z.css", "/* name: apple */")
    assert list(discover_styles(tmp_path / "b", tmp_path / "u")) == ["z", "a"]


def test_read_css(tmp_path):
    _write(tmp_path / "b" / "x.css", "body { color: red; }")
    assert "color: red" in discover_styles(tmp_path / "b", tmp_path / "u")["x"].read_css()


def test_bundled_styles_include_default(tmp_path):
    found = discover_styles(builtin_styles_dir(), tmp_path / "u")
    assert styles.DEFAULT_STYLE in found
    assert "plain" in found


def test_bundled_github_variants(tmp_path):
    found = discover_styles(builtin_styles_dir(), tmp_path / "u")
    assert (found["github"].scheme, found["github-light"].scheme, found["github-dark"].scheme) == (
        "auto",
        "light",
        "dark",
    )
    for stem in ("github", "github-light", "github-dark"):
        css = found[stem].read_css()
        assert "upstream: github-markdown-css" in css
        assert ".markdown-body" in css


def test_resolve_style_prefers_requested(tmp_path):
    _write(tmp_path / "b" / "github.css", "/* name: GitHub */")
    _write(tmp_path / "b" / "plain.css", "/* name: Plain */")
    found = discover_styles(tmp_path / "b", tmp_path / "u")
    assert resolve_style(found, "plain").id == "plain"


def test_resolve_style_falls_back_to_default_then_any(tmp_path):
    _write(tmp_path / "b" / "github.css", "/* name: GitHub */")
    _write(tmp_path / "b" / "plain.css", "/* name: Plain */")
    found = discover_styles(tmp_path / "b", tmp_path / "u")
    assert resolve_style(found, "deleted-user-style").id == "github"
    assert resolve_style(found, None).id == "github"
    del found["github"]
    assert resolve_style(found, "nope").id == "plain"
    assert resolve_style({}, "nope") is None
