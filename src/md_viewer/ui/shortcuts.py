"""Keyboard Shortcuts window, generated from menus.SHORTCUT_HELP / ACCELS.

Plain Gtk.Window (Gtk.ShortcutsWindow is deprecated since GTK 4.18 and is
libadwaita-styled); follows the user's GTK theme like the rest of the app.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .menus import SHORTCUT_HELP, shortcut_keys

COLUMNS = 2
_Group = tuple[str, list[tuple[str, str]]]


def _key_label(accelerator: str) -> str:
    ok, keyval, mods = Gtk.accelerator_parse(accelerator)
    return Gtk.accelerator_get_label(keyval, mods) if ok else accelerator


def _balanced_columns(groups: list[_Group], count: int) -> list[list[_Group]]:
    """Split groups (kept whole, in order) into *count* columns of similar height."""
    total = sum(len(rows) + 1 for _, rows in groups)  # +1 for each heading
    columns: list[list[_Group]] = [[]]
    height = 0
    for group in groups:
        if columns[-1] and len(columns) < count and height >= total * len(columns) / count:
            columns.append([])
        columns[-1].append(group)
        height += len(group[1]) + 1
    return columns


class ShortcutsWindow(Gtk.Window):
    __gtype_name__ = "MdViewerShortcutsWindow"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(title="Keyboard Shortcuts", resizable=False, **kwargs)

        outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )
        columns = Gtk.Box(spacing=36, homogeneous=True)
        for groups in _balanced_columns(SHORTCUT_HELP, COLUMNS):
            columns.append(self._column(groups))
        outer.append(columns)

        buttons = Gtk.Box(halign=Gtk.Align.END)
        close_btn = Gtk.Button(label="_Close", use_underline=True)
        close_btn.connect("clicked", lambda *_: self.close())
        buttons.append(close_btn)
        outer.append(buttons)
        self.set_child(outer)

        escape = Gtk.ShortcutController()
        escape.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("Escape"), Gtk.CallbackAction.new(lambda *_: self.close() or True)
            )
        )
        self.add_controller(escape)
        close_btn.grab_focus()

    @staticmethod
    def _column(groups: list[_Group]) -> Gtk.Widget:
        grid = Gtk.Grid(column_spacing=24, row_spacing=6, valign=Gtk.Align.START)
        row = 0
        for index, (title, entries) in enumerate(groups):
            heading = Gtk.Label(label=f"<b>{title}</b>", use_markup=True, xalign=0, margin_top=12 if index else 0)
            grid.attach(heading, 0, row, 2, 1)
            row += 1
            for description, entry in entries:
                grid.attach(Gtk.Label(label=description, xalign=0, hexpand=True), 0, row, 1, 1)
                keys = Gtk.Label(label="  or  ".join(_key_label(a) for a in shortcut_keys(entry)), xalign=1)
                keys.add_css_class("dim-label")
                grid.attach(keys, 1, row, 1, 1)
                row += 1
        return grid
