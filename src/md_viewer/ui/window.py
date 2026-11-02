"""Viewer window (ViewerWindow): menu bar plus a WebKit view of the rendered document.

Uses plain Gtk.ApplicationWindow so Xfwm4 draws the titlebar and the user's
GTK theme applies. No libadwaita.
"""

from __future__ import annotations

import html

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, Gtk, WebKit

from .. import APP_ID, APP_NAME
from ..settings import get_settings

_PLACEHOLDER_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; display: flex; align-items: center; justify-content: center;
         height: 90vh; color: #888; }}
</style></head>
<body><p>{message}</p></body></html>
"""


class ViewerWindow(Gtk.ApplicationWindow):
    """One window per open document."""

    __gtype_name__ = "MdViewerWindow"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(title=APP_NAME, default_width=900, default_height=700, **kwargs)
        self.set_icon_name(APP_ID)
        self._file: Gio.File | None = None

        self._restore_size()
        self._build_ui()
        self.connect("close-request", self._on_close_request)
        self._show_message("Open a Markdown file with File → Open (Ctrl+O)")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        menu_bar = Gtk.PopoverMenuBar.new_from_model(self._build_menu_model())
        box.append(menu_bar)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._webview = WebKit.WebView(vexpand=True, hexpand=True)
        box.append(self._webview)
        self.set_child(box)

    @staticmethod
    def _build_menu_model() -> Gio.Menu:
        menu = Gio.Menu()

        file_menu = Gio.Menu()
        file_menu.append("_Open…", "app.open")
        file_menu.append("_Close", "win.close")
        file_menu.append("_Quit", "app.quit")
        menu.append_submenu("_File", file_menu)

        help_menu = Gio.Menu()
        help_menu.append(f"_About {APP_NAME}", "app.about")
        menu.append_submenu("_Help", help_menu)
        return menu

    # ------------------------------------------------------------------
    # Document
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """True when no document has been loaded into this window."""
        return self._file is None

    def load_file(self, file: Gio.File) -> None:
        """Load *file* into this window. Rendering arrives in a later milestone."""
        self._file = file
        name = file.get_basename() or file.get_uri()
        self.set_title(f"{name} — {APP_NAME}")
        self._show_message(f"Loaded {html.escape(file.get_parse_name())}")

    def _show_message(self, message: str) -> None:
        self._webview.load_html(_PLACEHOLDER_HTML.format(message=message), None)

    # ------------------------------------------------------------------
    # Window size persistence
    # ------------------------------------------------------------------

    def _restore_size(self) -> None:
        settings = get_settings()
        if settings is None:
            return
        self.set_default_size(settings.get_int("window-width"), settings.get_int("window-height"))
        if settings.get_boolean("window-maximized"):
            self.maximize()

    def _on_close_request(self, _win: Gtk.Window) -> bool:
        settings = get_settings()
        if settings is not None:
            settings.set_boolean("window-maximized", self.is_maximized())
            if not self.is_maximized():
                width, height = self.get_default_size()
                settings.set_int("window-width", width)
                settings.set_int("window-height", height)
        return False  # allow the close to proceed
