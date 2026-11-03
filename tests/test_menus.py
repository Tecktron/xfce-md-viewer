"""Right-click menu contents."""

from pathlib import Path

import pytest
from gi.repository import Gio

from md_viewer.flavors import FLAVORS
from md_viewer.styles import Style
from md_viewer.ui.menus import (
    ACCELS,
    SHORTCUT_HELP,
    build_menu_model,
    context_menu_entries,
    fill_flavor_menu,
    fill_style_menu,
    shortcut_keys,
)


def _items(menu: Gio.Menu) -> list[tuple[str, str, str]]:
    """Flatten sections into (label, action, target) tuples."""
    out = []
    for i in range(menu.get_n_items()):
        section = menu.get_item_link(i, Gio.MENU_LINK_SECTION)
        if section is not None:
            out += _items(section)
            continue
        label = menu.get_item_attribute_value(i, "label").get_string()
        action = menu.get_item_attribute_value(i, "action").get_string()
        target = menu.get_item_attribute_value(i, "target")
        out.append((label, action, target.get_string() if target else ""))
    return out


def test_plain_text_shows_greyed_copy_then_select_all():
    assert context_menu_entries(selection=False, link=False, image=False) == ["copy-unavailable", "", "select-all"]


def test_selection_enables_copy():
    assert context_menu_entries(selection=True, link=False, image=False) == ["copy", "", "select-all"]


def test_link_without_selection():
    assert context_menu_entries(selection=False, link=True, image=False) == [
        "copy-unavailable",
        "copy-link",
        "",
        "select-all",
    ]


def test_selected_link():
    assert context_menu_entries(selection=True, link=True, image=False) == ["copy", "copy-link", "", "select-all"]


def test_image():
    assert context_menu_entries(selection=False, link=False, image=True) == [
        "copy-unavailable",
        "copy-image",
        "copy-image-address",
        "",
        "select-all",
    ]


@pytest.mark.parametrize("selection", [True, False])
@pytest.mark.parametrize("link", [True, False])
@pytest.mark.parametrize("image", [True, False])
def test_shape_invariants(selection, link, image):
    entries = context_menu_entries(selection=selection, link=link, image=image)
    assert entries[-2:] == ["", "select-all"]  # separator, then Select All last
    assert entries[0] in {"copy", "copy-unavailable"}  # Copy always first
    assert len([e for e in entries if e]) >= 2  # never a one-item menu


def test_flavor_menu_with_pandoc():
    menu = Gio.Menu()
    fill_flavor_menu(menu, pandoc_available=True)
    items = _items(menu)
    assert [t for _, _, t in items] == list(FLAVORS)
    assert all(action == "win.flavor" for _, action, _ in items)


def test_flavor_menu_without_pandoc_greys_out_pandoc_flavors():
    menu = Gio.Menu()
    fill_flavor_menu(menu, pandoc_available=False)
    for label, action, target in _items(menu):
        if FLAVORS[target].requires_pandoc:
            assert action == "win.flavor-unavailable"
            assert label.endswith("(needs pandoc)")
        else:
            assert action == "win.flavor"


def test_fill_is_idempotent():
    menu = Gio.Menu()
    fill_flavor_menu(menu, pandoc_available=True)
    fill_flavor_menu(menu, pandoc_available=True)
    assert len(_items(menu)) == len(FLAVORS)


def _style(sid, name, builtin):
    return Style(sid, name, "", "auto", Path(f"/x/{sid}.css"), builtin)


def test_style_menu_sections_and_mnemonic_escaping():
    menu = Gio.Menu()
    fill_style_menu(menu, {"github": _style("github", "GitHub", True), "mine": _style("mine", "My_Style", False)})
    assert menu.get_n_items() == 2  # built-in section + user section
    assert _items(menu) == [("GitHub", "win.style", "github"), ("My__Style", "win.style", "mine")]


def test_style_menu_without_user_styles_has_one_section():
    menu = Gio.Menu()
    fill_style_menu(menu, {"github": _style("github", "GitHub", True)})
    assert menu.get_n_items() == 1


def test_menu_model_builds():
    model = build_menu_model(Gio.Menu(), Gio.Menu(), Gio.Menu())
    labels = [model.get_item_attribute_value(i, "label").get_string() for i in range(model.get_n_items())]
    assert labels == ["_File", "_Edit", "_View", "_Help"]


def test_file_menu_close_then_hideable_quit_section():
    model = build_menu_model(Gio.Menu(), Gio.Menu(), Gio.Menu())
    file_menu = model.get_item_link(0, Gio.MENU_LINK_SUBMENU)
    last = file_menu.get_item_link(file_menu.get_n_items() - 1, Gio.MENU_LINK_SECTION)
    before = file_menu.get_item_link(file_menu.get_n_items() - 2, Gio.MENU_LINK_SECTION)
    assert _items(before) == [("_Close", "win.close", "")]
    assert _items(last) == [("Close _All", "app.quit-all", "")]
    assert last.get_item_attribute_value(0, "hidden-when").get_string() == "action-disabled"


def test_view_menu_has_show_and_hide_toc_hidden_when_disabled():
    model = build_menu_model(Gio.Menu(), Gio.Menu(), Gio.Menu())
    view_menu = model.get_item_link(2, Gio.MENU_LINK_SUBMENU)
    panes = view_menu.get_item_link(0, Gio.MENU_LINK_SECTION)
    assert [(label, action) for label, action, _ in _items(panes)] == [
        ("Show Table of _Contents", "win.toc-show"),
        ("Hide Table of _Contents", "win.toc-hide"),
    ]
    for i in range(panes.get_n_items()):
        assert panes.get_item_attribute_value(i, "hidden-when").get_string() == "action-disabled"


def test_help_menu_items_then_about():
    model = build_menu_model(Gio.Menu(), Gio.Menu(), Gio.Menu())
    help_menu = model.get_item_link(3, Gio.MENU_LINK_SUBMENU)
    first = help_menu.get_item_link(0, Gio.MENU_LINK_SECTION)
    second = help_menu.get_item_link(1, Gio.MENU_LINK_SECTION)
    assert [a for _, a, _ in _items(first)] == ["app.shortcuts", "app.report-problem"]
    assert [a for _, a, _ in _items(second)] == ["app.about"]


def test_shortcuts_window_lists_every_registered_shortcut():
    listed = {entry for _, rows in SHORTCUT_HELP for _, entry in rows}
    assert set(ACCELS) <= listed, set(ACCELS) - listed


def test_shortcuts_window_only_references_registered_actions():
    for _, rows in SHORTCUT_HELP:
        for _, entry in rows:
            if entry.startswith(("app.", "win.")):
                assert entry in ACCELS, entry


def test_shortcut_keys_drops_keypad_variants():
    assert shortcut_keys("win.zoom-in") == ["<Control>plus", "<Control>equal"]
    assert shortcut_keys("<Control>c") == ["<Control>c"]
