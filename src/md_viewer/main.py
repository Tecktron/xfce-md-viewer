"""Application entry point and MdViewerApplication (Gtk.Application) class."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from . import APP_ID, APP_NAME, __version__
from .links import MARKDOWN_EXTENSIONS, is_markdown_uri
from .ui.menus import ACCELS, build_menu_model
from .ui.window import ViewerWindow

MAX_RECENT = 10


class MdViewerApplication(Gtk.Application):
    """Single-instance application.

    A second ``md-viewer`` launch hands its files to the running process,
    which opens one window per file instead of starting a new process.
    """

    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self._recent_menu = Gio.Menu()
        self.menu_model = build_menu_model(self._recent_menu)
        self._recent_manager = Gtk.RecentManager.get_default()
        self._recent_manager.connect("changed", lambda *_: self._refresh_recent_menu())

        self.connect("activate", self._on_activate)
        self.connect("open", self._on_open)
        self._add_actions()
        self._refresh_recent_menu()

    def _add_actions(self) -> None:
        for name, callback in (
            ("open", self._on_open_action),
            ("about", self._on_about),
            ("quit", lambda *_: self.quit()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        open_recent = Gio.SimpleAction.new("open-recent", GLib.VariantType.new("s"))
        open_recent.connect("activate", self._on_open_recent)
        self.add_action(open_recent)

        for action_name, accels in ACCELS.items():
            self.set_accels_for_action(action_name, accels)

    # ------------------------------------------------------------------
    # Windows and files
    # ------------------------------------------------------------------

    def new_window(self, file: Gio.File | None = None) -> ViewerWindow:
        win = ViewerWindow(application=self)
        if file is not None:
            win.load_file(file)
        win.present()
        return win

    def open_file(self, file: Gio.File, parent: Gtk.Window | None = None) -> None:
        """Open *file* in *parent* if that window is still empty, otherwise in a new window."""
        if isinstance(parent, ViewerWindow) and parent.is_empty():
            parent.load_file(file)
        else:
            self.new_window(file)

    def _on_activate(self, _app: Gtk.Application) -> None:
        self.new_window()

    def _on_open(self, _app: Gtk.Application, files: list[Gio.File], _n_files: int, _hint: str) -> None:
        for file in files:
            self.new_window(file)

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.remove_all()
        items = [
            info
            for info in self._recent_manager.get_items()
            if is_markdown_uri(info.get_uri()) and info.is_local() and info.exists()
        ]
        items.sort(key=lambda info: info.get_modified().to_unix(), reverse=True)
        for info in items[:MAX_RECENT]:
            path = Path(GLib.filename_from_uri(info.get_uri())[0])
            label = f"{path.name}  —  {path.parent}".replace("_", "__")  # "_" is a mnemonic marker
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value("app.open-recent", GLib.Variant.new_string(info.get_uri()))
            self._recent_menu.append_item(item)
        if not items:
            placeholder = Gio.MenuItem.new("No recent documents", "app.no-recent")  # no such action → greyed out
            self._recent_menu.append_item(placeholder)

    def _on_open_recent(self, _action: Gio.SimpleAction, uri: GLib.Variant) -> None:
        self.open_file(Gio.File.new_for_uri(uri.get_string()), self.get_active_window())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_open_action(self, *_args: object) -> None:
        md_filter = Gtk.FileFilter(name="Markdown files")
        md_filter.add_mime_type("text/markdown")
        for ext in sorted(MARKDOWN_EXTENSIONS):
            md_filter.add_suffix(ext.removeprefix("."))
        all_filter = Gtk.FileFilter(name="All files")
        all_filter.add_pattern("*")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(md_filter)
        filters.append(all_filter)

        dialog = Gtk.FileDialog(title="Open Markdown File", filters=filters, default_filter=md_filter)
        dialog.open_multiple(self.get_active_window(), None, self._on_open_finish)

    def _on_open_finish(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return  # user cancelled
        parent = self.get_active_window()
        for index in range(files.get_n_items()):
            self.open_file(files.get_item(index), parent)

    def _on_about(self, *_args: object) -> None:
        about = Gtk.AboutDialog(
            transient_for=self.get_active_window(),
            modal=True,
            program_name=APP_NAME,
            logo_icon_name=APP_ID,
            version=__version__,
            comments="A Markdown viewer for Xfce with multiple flavors and CSS styles.",
            website="https://github.com/Tecktron/xfce-md-viewer",
            license_type=Gtk.License.GPL_3_0,
            copyright="© 2026 Tecktron Studios",
        )
        about.present()


def main() -> None:
    parser = argparse.ArgumentParser(prog="md-viewer", description="View Markdown files.")
    parser.add_argument("--version", action="version", version=f"md-viewer {__version__}")
    parser.add_argument("files", nargs="*", metavar="FILE", help="Markdown file(s) to open")
    # Unknown args (e.g. --display) are passed through to GTK.
    args, remaining = parser.parse_known_args()
    app = MdViewerApplication()
    sys.exit(app.run([sys.argv[0], *remaining, *args.files]))


if __name__ == "__main__":
    main()
