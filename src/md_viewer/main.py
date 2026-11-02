"""Application entry point and MdViewerApplication (Gtk.Application) class."""

from __future__ import annotations

import argparse
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from . import APP_ID, APP_NAME, __version__
from .ui.window import ViewerWindow


class MdViewerApplication(Gtk.Application):
    """Single-instance application.

    A second ``md-viewer`` launch hands its files to the running process,
    which opens one window per file instead of starting a new process.
    """

    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.connect("activate", self._on_activate)
        self.connect("open", self._on_open)
        self._add_actions()

    def _add_actions(self) -> None:
        for name, callback, accels in (
            ("open", self._on_open_action, ["<Control>o"]),
            ("about", self._on_about, []),
            ("quit", lambda *_: self.quit(), ["<Control>q"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)
        self.set_accels_for_action("win.close", ["<Control>w"])

    # ------------------------------------------------------------------
    # Window creation
    # ------------------------------------------------------------------

    def _new_window(self, file: Gio.File | None = None) -> ViewerWindow:
        win = ViewerWindow(application=self)
        if file is not None:
            win.load_file(file)
        win.present()
        return win

    def _on_activate(self, _app: Gtk.Application) -> None:
        self._new_window()

    def _on_open(self, _app: Gtk.Application, files: list[Gio.File], _n_files: int, _hint: str) -> None:
        for file in files:
            self._new_window(file)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_open_action(self, *_args: object) -> None:
        parent = self.get_active_window()
        md_filter = Gtk.FileFilter(name="Markdown files")
        md_filter.add_mime_type("text/markdown")
        for pattern in ("*.md", "*.markdown", "*.mdown", "*.mkd", "*.Rmd"):
            md_filter.add_pattern(pattern)
        all_filter = Gtk.FileFilter(name="All files")
        all_filter.add_pattern("*")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(md_filter)
        filters.append(all_filter)

        dialog = Gtk.FileDialog(title="Open Markdown File", filters=filters, default_filter=md_filter)
        dialog.open(parent, None, self._on_open_finish)

    def _on_open_finish(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return  # user cancelled
        parent = self.get_active_window()
        if isinstance(parent, ViewerWindow) and parent.is_empty():
            parent.load_file(file)
        else:
            self._new_window(file)

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
