"""Application entry point and MdViewerApplication (Gtk.Application) class."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from . import APP_ID, APP_NAME, __version__
from .flavors import pandoc_available
from .links import MARKDOWN_EXTENSIONS, is_markdown_uri
from .paths import user_styles_dir
from .settings import get_settings
from .styles import Style, discover_styles
from .ui.menus import ACCELS, build_menu_model, fill_flavor_menu, fill_style_menu
from .ui.preferences import PreferencesWindow
from .ui.shortcuts import ShortcutsWindow
from .ui.window import ViewerWindow

_log = logging.getLogger(__name__)

ISSUES_URL = "https://github.com/Tecktron/xfce-md-viewer/issues"
MAX_RECENT = 10
STYLES_RESCAN_DELAY_MS = 300
_DEFAULT_KEYS = ("default-flavor", "default-style", "allow-remote-images")


class MdViewerApplication(Gtk.Application):
    """Single-instance application.

    A second ``md-viewer`` launch hands its files to the running process,
    which opens one window per file instead of starting a new process.
    """

    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self._recent_menu = Gio.Menu()
        self._flavor_menu = Gio.Menu()
        self._style_menu = Gio.Menu()
        self.menu_model = build_menu_model(self._recent_menu, self._flavor_menu, self._style_menu)
        self._recent_manager = Gtk.RecentManager.get_default()
        self._recent_manager.connect("changed", lambda *_: self._refresh_recent_menu())

        self.pandoc_available = pandoc_available()
        self.styles: dict[str, Style] = {}
        self._styles_monitor: Gio.FileMonitor | None = None
        self._styles_rescan_source = 0
        self._preferences: PreferencesWindow | None = None
        self._shortcuts: ShortcutsWindow | None = None

        self.connect("activate", self._on_activate)
        self.connect("open", self._on_open)
        self.connect("startup", self._on_startup)
        self.connect("window-added", self._on_window_count_changed)
        self.connect("window-removed", self._on_window_count_changed)
        self._add_actions()
        self._refresh_recent_menu()
        fill_flavor_menu(self._flavor_menu, self.pandoc_available)
        self._rescan_styles()

    def _add_actions(self) -> None:
        for name, callback in (
            ("open", self._on_open_action),
            ("preferences", self._on_preferences),
            ("shortcuts", self._on_shortcuts),
            ("report-problem", self._on_report_problem),
            ("about", self._on_about),
            ("quit", lambda *_: self.quit()),
            ("quit-all", lambda *_: self.quit()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        self.lookup_action("quit-all").set_enabled(False)

        open_recent = Gio.SimpleAction.new("open-recent", GLib.VariantType.new("s"))
        open_recent.connect("activate", self._on_open_recent)
        self.add_action(open_recent)

        for action_name, accels in ACCELS.items():
            self.set_accels_for_action(action_name, accels)

    def _on_startup(self, _app: Gtk.Application) -> None:
        # Runs only in the primary instance (not in a second launch that forwards files).
        self._watch_user_styles()
        settings = get_settings()
        if settings is not None:
            for key in _DEFAULT_KEYS:
                settings.connect(f"changed::{key}", lambda *_: self._for_each_window(ViewerWindow.on_defaults_changed))

    def _on_window_count_changed(self, _app: Gtk.Application, _win: Gtk.Window) -> None:
        """File → Quit only makes sense (and is only shown) with more than one viewer window."""
        viewers = sum(isinstance(win, ViewerWindow) for win in self.get_windows())
        self.lookup_action("quit-all").set_enabled(viewers > 1)

    def _for_each_window(self, method: Callable[[ViewerWindow], None]) -> None:
        for win in self.get_windows():
            if isinstance(win, ViewerWindow):
                method(win)

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _watch_user_styles(self) -> None:
        directory = Gio.File.new_for_path(str(user_styles_dir()))
        try:
            # Works even if the directory doesn't exist yet; GLib notices when it is created.
            self._styles_monitor = directory.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        except GLib.Error:
            _log.debug("Cannot watch %s", directory.get_parse_name(), exc_info=True)
            return
        self._styles_monitor.connect("changed", self._on_styles_dir_changed)

    def _on_styles_dir_changed(self, *_args: object) -> None:
        if self._styles_rescan_source:
            GLib.source_remove(self._styles_rescan_source)
        self._styles_rescan_source = GLib.timeout_add(STYLES_RESCAN_DELAY_MS, self._on_styles_rescan_timeout)

    def _on_styles_rescan_timeout(self) -> bool:
        self._styles_rescan_source = 0
        self._rescan_styles()
        self._for_each_window(ViewerWindow.on_styles_changed)
        return GLib.SOURCE_REMOVE

    def _rescan_styles(self) -> None:
        self.styles = discover_styles()
        fill_style_menu(self._style_menu, self.styles)
        if self._preferences is not None:
            self._preferences.refresh_styles()

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

    def _on_preferences(self, *_args: object) -> None:
        if self._preferences is None:
            self._preferences = PreferencesWindow(application=self)
            self._preferences.connect("close-request", self._on_preferences_closed)
        parent = self.get_active_window()
        if isinstance(parent, ViewerWindow):
            self._preferences.set_transient_for(parent)
        self._preferences.present()

    def _on_preferences_closed(self, _win: Gtk.Window) -> bool:
        self._preferences = None
        return False

    def _on_shortcuts(self, *_args: object) -> None:
        if self._shortcuts is None:
            self._shortcuts = ShortcutsWindow(application=self)
            self._shortcuts.connect("close-request", self._on_shortcuts_closed)
        parent = self.get_active_window()
        if isinstance(parent, ViewerWindow):
            self._shortcuts.set_transient_for(parent)
        self._shortcuts.present()

    def _on_shortcuts_closed(self, _win: Gtk.Window) -> bool:
        self._shortcuts = None
        return False

    def _on_report_problem(self, *_args: object) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(ISSUES_URL, None)
        except GLib.Error:
            _log.warning("No application to open %s", ISSUES_URL, exc_info=True)

    def _on_about(self, *_args: object) -> None:
        about = Gtk.AboutDialog(
            transient_for=self.get_active_window(),
            modal=True,
            program_name=APP_NAME,
            logo_icon_name=APP_ID,
            version=__version__,
            comments="A Markdown viewer for Xfce with multiple flavors and CSS styles.",
            website="https://github.com/Tecktron/xfce-md-viewer",
            website_label="Source code and issues",
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
