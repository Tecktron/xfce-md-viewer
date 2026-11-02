"""Right-click menu contents."""

import pytest

from md_viewer.ui.menus import context_menu_entries


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
