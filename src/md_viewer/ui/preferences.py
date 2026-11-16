"""Preferences window: General (default flavor/style, remote images, custom styles
folder) and Highlighting (syntax-highlighting themes with a live preview).

Instant-apply (changes are written to GSettings immediately; open windows that
haven't been switched by hand follow along). Plain Gtk.Window — no libadwaita.
"""

from __future__ import annotations

import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib, Gtk, Pango, WebKit

from ..document import build_theme_preview
from ..flavors import FLAVORS, Flavor
from ..highlight import DARK_THEME, LIGHT_THEME, available_themes, resolve_theme
from ..paths import user_styles_dir
from ..settings import get_settings, highlight_themes
from ..styles import DEFAULT_STYLE, Style, resolve_style

_log = logging.getLogger(__name__)


def _display_path(path: Path) -> str:
    """*path* with the home directory shown as ~."""
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)


STYLE_HEADER_EXAMPLE = "/* name: My Style\n   description: One line about it\n   scheme: auto */"
PREVIEW_HEIGHT_PX = 260
_HIGHLIGHT_KEYS = ("highlight-use-default", "highlight-light-theme", "highlight-dark-theme")


def _padded_box() -> Gtk.Box:
    """Vertical box with the window's spacing and margins (the window itself and each tab)."""
    return Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=18,
        margin_top=18,
        margin_bottom=18,
        margin_start=18,
        margin_end=18,
    )


class PreferencesWindow(Gtk.Window):
    __gtype_name__ = "MdViewerPreferencesWindow"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(title="Preferences", resizable=False, **kwargs)
        self._settings = get_settings()
        self._flavors: list[Flavor] = []
        self._style_ids: list[str] = []
        self._themes = available_themes()
        self._updating = False  # suppress dropdown handlers while repopulating
        self._settings_handlers: list[int] = []

        self._build_ui()
        self.refresh_flavors()
        self.refresh_styles()
        self._sync_highlighting()

        escape = Gtk.ShortcutController()
        escape.add_shortcut(
            Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string("Escape"), Gtk.CallbackAction.new(self._close))
        )
        self.add_controller(escape)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = _padded_box()
        notebook = Gtk.Notebook()
        notebook.append_page(self._build_general_page(), Gtk.Label(label="_General", use_underline=True))
        notebook.append_page(self._build_highlighting_page(), Gtk.Label(label="_Highlighting", use_underline=True))
        outer.append(notebook)

        buttons = Gtk.Box(halign=Gtk.Align.END)
        close_btn = Gtk.Button(label="_Close", use_underline=True)
        close_btn.connect("clicked", lambda *_: self.close())
        buttons.append(close_btn)
        outer.append(buttons)

        if self._settings is None:
            for widget in (
                self._flavor_dropdown,
                self._style_dropdown,
                self._remote_check,
                self._default_colours_check,
            ):
                widget.set_sensitive(False)
            missing = Gtk.Label(
                label="Settings can't be saved: the GSettings schema is not installed.", wrap=True, xalign=0
            )
            missing.add_css_class("error")
            outer.prepend(missing)
        else:
            self._settings.bind("allow-remote-images", self._remote_check, "active", Gio.SettingsBindFlags.DEFAULT)
            self._settings.bind(
                "highlight-use-default", self._default_colours_check, "active", Gio.SettingsBindFlags.DEFAULT
            )
            # Only re-select on external changes; rebuilding the model from inside the
            # dropdown's own notify::selected handler would re-enter it.
            self._settings_handlers = [
                self._settings.connect("changed::default-flavor", lambda *_: self._sync_selection()),
                self._settings.connect("changed::default-style", lambda *_: self._sync_selection()),
            ] + [
                self._settings.connect(f"changed::{key}", lambda *_: self._sync_highlighting())
                for key in _HIGHLIGHT_KEYS
            ]
            self.connect("close-request", self._on_close_request)

        self.set_child(outer)
        close_btn.grab_focus()

    def _build_general_page(self) -> Gtk.Widget:
        outer = _padded_box()

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        self._flavor_dropdown = Gtk.DropDown(hexpand=True)
        self._flavor_dropdown.connect("notify::selected", self._on_flavor_selected)
        self._style_dropdown = Gtk.DropDown(hexpand=True)
        self._style_dropdown.connect("notify::selected", self._on_style_selected)
        self._remote_check = Gtk.CheckButton(label="Load _remote images", use_underline=True)

        self._pandoc_note = Gtk.Label(
            label="Install pandoc for Pandoc Markdown, MultiMarkdown, R Markdown and CommonMark + Extensions.",
            wrap=True,
            xalign=0,
            max_width_chars=50,
        )
        self._pandoc_note.add_css_class("dim-label")

        rows: list[tuple[str, Gtk.Widget]] = [
            ("Default _flavor:", self._flavor_dropdown),
            ("", self._pandoc_note),
            ("Default _style:", self._style_dropdown),
        ]
        for row, (text, widget) in enumerate(rows):
            if text:
                label = Gtk.Label(label=text, use_underline=True, xalign=1, mnemonic_widget=widget)
                grid.attach(label, 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
        outer.append(grid)

        outer.append(self._remote_check)
        remote_hint = Gtk.Label(
            label="Off by default: documents can't contact the network. Scripts are always blocked.",
            wrap=True,
            xalign=0,
            max_width_chars=60,
        )
        remote_hint.add_css_class("dim-label")
        outer.append(remote_hint)

        outer.append(Gtk.Separator())

        styles_title = Gtk.Label(label="<b>Custom styles</b>", use_markup=True, xalign=0)
        outer.append(styles_title)
        styles_text = Gtk.Label(
            label=(
                "Add your own look by putting a .css file in the styles folder. It appears in "
                "View → Style straight away, and edits show up live. Start the file with:"
            ),
            wrap=True,
            xalign=0,
            max_width_chars=60,
        )
        outer.append(styles_text)
        example = Gtk.Label(label=STYLE_HEADER_EXAMPLE, selectable=True, xalign=0)
        example.add_css_class("monospace")
        outer.append(example)
        folder_row = Gtk.Box(spacing=12)
        folder = user_styles_dir()
        folder_label = Gtk.Label(
            label=_display_path(folder),
            tooltip_text=str(folder),
            selectable=True,
            xalign=0,
            hexpand=True,
            ellipsize=Pango.EllipsizeMode.MIDDLE,
            max_width_chars=40,  # ellipsized labels still request their full natural width otherwise
        )
        folder_label.add_css_class("dim-label")
        open_btn = Gtk.Button(label="_Open Styles Folder", use_underline=True)
        open_btn.connect("clicked", self._on_open_styles_folder)
        folder_row.append(folder_label)
        folder_row.append(open_btn)
        outer.append(folder_row)
        return outer

    def _build_highlighting_page(self) -> Gtk.Widget:
        outer = _padded_box()

        self._default_colours_check = Gtk.CheckButton(label="_Use default colours", use_underline=True)
        outer.append(self._default_colours_check)
        hint = Gtk.Label(
            label=(
                "Colours for code blocks and View → Show Source. A style's colour scheme picks the light or "
                "dark theme; styles that follow the system use the one matching your desktop. Themes chosen "
                "here also set the code block background."
            ),
            wrap=True,
            xalign=0,
            max_width_chars=60,
        )
        hint.add_css_class("dim-label")
        outer.append(hint)

        self._theme_grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        self._light_dropdown = self._theme_dropdown("highlight-light-theme")
        self._dark_dropdown = self._theme_dropdown("highlight-dark-theme")
        for row, (text, widget) in enumerate(
            (("_Light theme:", self._light_dropdown), ("_Dark theme:", self._dark_dropdown))
        ):
            label = Gtk.Label(label=text, use_underline=True, xalign=1, mnemonic_widget=widget)
            self._theme_grid.attach(label, 0, row, 1, 1)
            self._theme_grid.attach(widget, 1, row, 1, 1)
        outer.append(self._theme_grid)

        # Display only: not clickable or focusable, so no navigation, drops or context menu.
        self._preview = WebKit.WebView(can_target=False, focusable=False, height_request=PREVIEW_HEIGHT_PX)
        self._preview.get_settings().set_enable_javascript(False)
        outer.append(Gtk.Frame(child=self._preview))
        return outer

    def _theme_dropdown(self, key: str) -> Gtk.DropDown:
        dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(self._themes),
            enable_search=True,
            expression=Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"),
            hexpand=True,
        )
        dropdown.connect("notify::selected", self._on_theme_selected, key)
        return dropdown

    def _close(self, *_args: object) -> bool:
        self.close()
        return True

    def _on_close_request(self, _win: Gtk.Window) -> bool:
        if self._settings is not None:
            for handler in self._settings_handlers:
                self._settings.disconnect(handler)
            self._settings.unbind(self._remote_check, "active")
            self._settings.unbind(self._default_colours_check, "active")
        self._settings_handlers = []
        return False

    # ------------------------------------------------------------------
    # Dropdown contents
    # ------------------------------------------------------------------

    def _app_styles(self) -> dict[str, Style]:
        return getattr(self.get_application(), "styles", {})

    def refresh_flavors(self) -> None:
        pandoc = getattr(self.get_application(), "pandoc_available", False)
        current = self._settings.get_string("default-flavor") if self._settings else "gfm"
        self._flavors = [f for f in FLAVORS.values() if pandoc or not f.requires_pandoc or f.id == current]
        self._pandoc_note.set_visible(not pandoc)
        self._fill(self._flavor_dropdown, [f.name for f in self._flavors], [f.id for f in self._flavors], current)

    def refresh_styles(self) -> None:
        """Repopulate the style list (also called by the app when the styles folder changes)."""
        styles = self._app_styles()
        wanted = self._settings.get_string("default-style") if self._settings else DEFAULT_STYLE
        resolved = resolve_style(styles, wanted)
        self._style_ids = list(styles)
        self._fill(
            self._style_dropdown,
            [s.name for s in styles.values()],
            self._style_ids,
            resolved.id if resolved else None,
        )

    def _fill(self, dropdown: Gtk.DropDown, names: list[str], ids: list[str], selected_id: str | None) -> None:
        self._updating = True
        try:
            dropdown.set_model(Gtk.StringList.new(names))
            self._select(dropdown, ids, selected_id)
        finally:
            self._updating = False

    def _select(self, dropdown: Gtk.DropDown, ids: list[str], selected_id: str | None) -> None:
        if selected_id in ids and dropdown.get_selected() != ids.index(selected_id):
            dropdown.set_selected(ids.index(selected_id))

    def _sync_selection(self) -> None:
        """Reflect the current settings in both dropdowns without rebuilding them."""
        if self._settings is None:
            return
        flavor_ids = [f.id for f in self._flavors]
        resolved = resolve_style(self._app_styles(), self._settings.get_string("default-style"))
        self._updating = True
        try:
            self._select(self._flavor_dropdown, flavor_ids, self._settings.get_string("default-flavor"))
            self._select(self._style_dropdown, self._style_ids, resolved.id if resolved else None)
        finally:
            self._updating = False

    def _on_flavor_selected(self, dropdown: Gtk.DropDown, _pspec: object) -> None:
        index = dropdown.get_selected()
        if self._updating or self._settings is None or index >= len(self._flavors):
            return
        flavor_id = self._flavors[index].id
        if self._settings.get_string("default-flavor") != flavor_id:
            self._settings.set_string("default-flavor", flavor_id)

    def _on_style_selected(self, dropdown: Gtk.DropDown, _pspec: object) -> None:
        index = dropdown.get_selected()
        if self._updating or self._settings is None or index >= len(self._style_ids):
            return
        style_id = self._style_ids[index]
        if self._settings.get_string("default-style") != style_id:
            self._settings.set_string("default-style", style_id)

    # ------------------------------------------------------------------
    # Highlighting
    # ------------------------------------------------------------------

    def _sync_highlighting(self) -> None:
        """Reflect the highlighting settings in the dropdowns, their sensitivity and the preview."""
        settings = self._settings
        use_default = settings is None or settings.get_boolean("highlight-use-default")
        if settings is None:
            self._default_colours_check.set_active(True)
        self._theme_grid.set_sensitive(not use_default)
        light = resolve_theme(settings.get_string("highlight-light-theme"), LIGHT_THEME) if settings else LIGHT_THEME
        dark = resolve_theme(settings.get_string("highlight-dark-theme"), DARK_THEME) if settings else DARK_THEME
        self._updating = True
        try:
            self._select(self._light_dropdown, self._themes, light)
            self._select(self._dark_dropdown, self._themes, dark)
        finally:
            self._updating = False
        # What documents actually use: the defaults while "Use default colours" is ticked.
        self._preview.load_html(build_theme_preview(highlight_themes()), None)

    def _on_theme_selected(self, dropdown: Gtk.DropDown, _pspec: object, key: str) -> None:
        index = dropdown.get_selected()
        if self._updating or self._settings is None or index >= len(self._themes):
            return
        if self._settings.get_string(key) != self._themes[index]:
            self._settings.set_string(key, self._themes[index])

    # ------------------------------------------------------------------
    # Styles folder
    # ------------------------------------------------------------------

    def _on_open_styles_folder(self, _btn: Gtk.Button) -> None:
        folder = user_styles_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            _log.warning("Cannot create %s", folder, exc_info=True)
            return
        try:
            Gio.AppInfo.launch_default_for_uri(folder.as_uri(), None)
        except GLib.Error:
            _log.warning("No application to open %s", folder, exc_info=True)
