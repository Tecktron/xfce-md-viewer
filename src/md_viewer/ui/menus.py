"""The menu bar model shared by every window, and the app's keyboard shortcuts."""

from __future__ import annotations

from gi.repository import Gio, GLib

from .. import APP_NAME
from ..flavors import FLAVORS
from ..styles import Style

# action name -> accelerators. Registered once on the application.
ACCELS: dict[str, list[str]] = {
    "app.open": ["<Control>o"],
    "app.preferences": ["<Control>comma"],
    "app.shortcuts": ["<Control>question"],
    "app.quit": ["<Control>q"],  # always works; the menu's Quit item uses app.quit-all
    "win.close": ["<Control>w"],
    "win.reload": ["F5", "<Control>r"],
    "win.print": ["<Control>p"],
    "win.find": ["<Control>f"],
    "win.find-next": ["F3", "<Control>g"],
    "win.find-previous": ["<Shift>F3", "<Control><Shift>g"],
    "win.zoom-in": ["<Control>plus", "<Control>equal", "<Control>KP_Add"],
    "win.zoom-out": ["<Control>minus", "<Control>KP_Subtract"],
    "win.zoom-reset": ["<Control>0", "<Control>KP_0"],
    "win.toc": ["F9"],
    "win.back": ["<Alt>Left"],
    "win.forward": ["<Alt>Right"],
}


# Keyboard Shortcuts window contents: (group, [(description, action or literal accelerator)]).
# Entries starting with "app." / "win." take their keys from ACCELS; anything else is
# a key handled natively by WebKit / GTK and is shown as written.
SHORTCUT_HELP: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Files and windows",
        [
            ("Open a file", "app.open"),
            ("Reload", "win.reload"),
            ("Print or export to PDF", "win.print"),
            ("Close window", "win.close"),
            ("Close all windows", "app.quit"),
        ],
    ),
    (
        "Reading",
        [
            ("Copy", "<Control>c"),
            ("Select all", "<Control>a"),
            ("Find", "win.find"),
            ("Next match", "win.find-next"),
            ("Previous match", "win.find-previous"),
        ],
    ),
    (
        "View",
        [
            ("Table of contents", "win.toc"),
            ("Zoom in", "win.zoom-in"),
            ("Zoom out", "win.zoom-out"),
            ("Normal size", "win.zoom-reset"),
        ],
    ),
    (
        "Navigation",
        [
            ("Back", "win.back"),
            ("Forward", "win.forward"),
        ],
    ),
    (
        "Application",
        [
            ("Preferences", "app.preferences"),
            ("Keyboard shortcuts", "app.shortcuts"),
        ],
    ),
]


def shortcut_keys(entry: str) -> list[str]:
    """Accelerators to display for a SHORTCUT_HELP entry (keypad duplicates omitted)."""
    if entry.startswith(("app.", "win.")):
        return [accel for accel in ACCELS[entry] if "KP_" not in accel]
    return [entry]


def context_menu_entries(*, selection: bool, link: bool, image: bool) -> list[str]:
    """Right-click menu entries for what was clicked; "" marks a separator.

    Built from scratch rather than filtering WebKit's menu: WebKit only offers
    Select All for editable content, and its default entries (Reload, Back,
    Open Link…) would bypass the viewer's own navigation handling.

    Copy is always present ("copy-unavailable" = shown greyed out) and Select All
    sits below a separator, so the menu never has a single item — GTK 4 gives
    one-item popover menus a 46 px minimum height, leaving a visible gap.
    """
    entries = ["copy" if selection else "copy-unavailable"]
    if link:
        entries.append("copy-link")
    if image:
        entries += ["copy-image", "copy-image-address"]
    return [*entries, "", "select-all"]


def _item(label: str, action: str, display_accel: str | None = None) -> Gio.MenuItem:
    """Menu item; *display_accel* shows a shortcut that is handled natively (not registered)."""
    item = Gio.MenuItem.new(label, action)
    if display_accel:
        item.set_attribute_value("accel", GLib.Variant.new_string(display_accel))
    return item


def fill_flavor_menu(menu: Gio.Menu, pandoc_available: bool) -> None:
    """Radio items for every flavor (action ``win.flavor``). Pandoc flavors are listed
    in their own section and greyed out (no such action) when pandoc is missing."""
    menu.remove_all()
    builtin, pandoc = Gio.Menu(), Gio.Menu()
    for flavor in FLAVORS.values():
        section = pandoc if flavor.requires_pandoc else builtin
        if flavor.requires_pandoc and not pandoc_available:
            item = Gio.MenuItem.new(f"{flavor.name} (needs pandoc)", None)
            item.set_action_and_target_value("win.flavor-unavailable", GLib.Variant.new_string(flavor.id))
        else:
            item = Gio.MenuItem.new(flavor.name, None)
            item.set_action_and_target_value("win.flavor", GLib.Variant.new_string(flavor.id))
        section.append_item(item)
    menu.append_section(None, builtin)
    menu.append_section(None, pandoc)


def fill_style_menu(menu: Gio.Menu, styles: dict[str, Style]) -> None:
    """Radio items for every style (action ``win.style``): built-ins, then the user's own."""
    menu.remove_all()
    builtin, user = Gio.Menu(), Gio.Menu()
    for style in styles.values():
        item = Gio.MenuItem.new(style.name.replace("_", "__"), None)
        item.set_action_and_target_value("win.style", GLib.Variant.new_string(style.id))
        (builtin if style.builtin else user).append_item(item)
    menu.append_section(None, builtin)
    if user.get_n_items():
        menu.append_section(None, user)


def build_menu_model(recent_menu: Gio.Menu, flavor_menu: Gio.Menu, style_menu: Gio.Menu) -> Gio.Menu:
    menu = Gio.Menu()

    file_menu = Gio.Menu()
    open_section = Gio.Menu()
    open_section.append("_Open…", "app.open")
    open_section.append_submenu("Open _Recent", recent_menu)
    open_section.append("_Reload", "win.reload")
    file_menu.append_section(None, open_section)
    print_section = Gio.Menu()
    print_section.append("_Print…", "win.print")
    file_menu.append_section(None, print_section)
    close_section = Gio.Menu()
    close_section.append("_Close", "win.close")
    file_menu.append_section(None, close_section)
    # Only shown while several windows are open (app enables app.quit-all then);
    # with one window Close already does the same thing.
    quit_section = Gio.Menu()
    quit_item = _item("Close _All", "app.quit-all", "<Control>q")
    quit_item.set_attribute_value("hidden-when", GLib.Variant.new_string("action-disabled"))
    quit_section.append_item(quit_item)
    file_menu.append_section(None, quit_section)
    menu.append_submenu("_File", file_menu)

    edit_menu = Gio.Menu()
    clipboard = Gio.Menu()
    # Copy / Select All are handled by the web view itself; show their keys only.
    clipboard.append_item(_item("_Copy", "win.copy", "<Control>c"))
    clipboard.append_item(_item("Select _All", "win.select-all", "<Control>a"))
    edit_menu.append_section(None, clipboard)
    find_section = Gio.Menu()
    find_section.append("_Find…", "win.find")
    find_section.append("Find _Next", "win.find-next")
    find_section.append("Find Pre_vious", "win.find-previous")
    edit_menu.append_section(None, find_section)
    prefs_section = Gio.Menu()
    prefs_section.append("Pr_eferences", "app.preferences")
    edit_menu.append_section(None, prefs_section)
    menu.append_submenu("_Edit", edit_menu)

    view_menu = Gio.Menu()
    panes = Gio.Menu()
    for label, action in (("Show Table of _Contents", "win.toc-show"), ("Hide Table of _Contents", "win.toc-hide")):
        item = _item(label, action, "F9")
        item.set_attribute_value("hidden-when", GLib.Variant.new_string("action-disabled"))
        panes.append_item(item)
    view_menu.append_section(None, panes)
    rendering = Gio.Menu()
    rendering.append_submenu("_Flavor", flavor_menu)
    rendering.append_submenu("_Style", style_menu)
    view_menu.append_section(None, rendering)
    zoom = Gio.Menu()
    zoom.append("Zoom _In", "win.zoom-in")
    zoom.append("Zoom _Out", "win.zoom-out")
    zoom.append("_Normal Size", "win.zoom-reset")
    view_menu.append_section(None, zoom)
    nav = Gio.Menu()
    nav.append("_Back", "win.back")
    nav.append("_Forward", "win.forward")
    view_menu.append_section(None, nav)
    menu.append_submenu("_View", view_menu)

    help_menu = Gio.Menu()
    help_items = Gio.Menu()
    help_items.append("_Keyboard Shortcuts", "app.shortcuts")
    help_items.append("_Report a Problem", "app.report-problem")
    help_menu.append_section(None, help_items)
    about_section = Gio.Menu()
    about_section.append(f"_About {APP_NAME}", "app.about")
    help_menu.append_section(None, about_section)
    menu.append_submenu("_Help", help_menu)
    return menu
