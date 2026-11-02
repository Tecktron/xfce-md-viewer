"""Viewer window (ViewerWindow): menu bar, find bar and a WebKit view of the rendered document.

Uses plain Gtk.ApplicationWindow so Xfwm4 draws the titlebar and the user's
GTK theme applies. No libadwaita.

Loading pipeline (never blocks the UI):
  load_contents_async → render in a daemon thread → GLib.idle_add → load_html.
Every load bumps ``self._generation``; stale results are dropped.
"""

from __future__ import annotations

import html
import logging
import threading

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit

from .. import APP_ID, APP_NAME
from ..document import render_document
from ..flavors import DEFAULT_FLAVOR, FLAVORS, FlavorUnavailableError, RenderError
from ..history import History
from ..links import LinkAction, classify_link, strip_fragment
from ..settings import get_settings
from ..styles import DEFAULT_STYLE, Style, resolve_style
from .menus import context_menu_entries

_log = logging.getLogger(__name__)

RELOAD_DEBOUNCE_MS = 200
ZOOM_STEP = 1.1
ZOOM_MIN, ZOOM_MAX = 0.3, 5.0
FIND_MAX_MATCHES = 10_000
# Scripts we run ourselves execute in this isolated world, out of the document's reach.
SCRIPT_WORLD = "md-viewer"

_FIND_OPTIONS = WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND
_CONTEXT_ACTIONS = {
    "copy": WebKit.ContextMenuAction.COPY,
    "copy-link": WebKit.ContextMenuAction.COPY_LINK_TO_CLIPBOARD,
    "copy-image": WebKit.ContextMenuAction.COPY_IMAGE_TO_CLIPBOARD,
    "copy-image-address": WebKit.ContextMenuAction.COPY_IMAGE_URL_TO_CLIPBOARD,
    "select-all": WebKit.ContextMenuAction.SELECT_ALL,
}
_MONITOR_IGNORED_EVENTS = frozenset(
    {
        Gio.FileMonitorEvent.ATTRIBUTE_CHANGED,
        Gio.FileMonitorEvent.PRE_UNMOUNT,
        Gio.FileMonitorEvent.UNMOUNTED,
    }
)

_MESSAGE_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<meta name="color-scheme" content="light dark">
<style>
  body {{ font-family: sans-serif; display: flex; align-items: center; justify-content: center;
         height: 90vh; margin: 0; opacity: .6; text-align: center; padding: 0 2em; }}
</style></head>
<body><p>{message}</p></body></html>
"""


def _render_page(
    text: str, title: str, flavor_id: str, style: Style | None, allow_remote_images: bool
) -> tuple[str | None, str | None]:
    """Worker-thread body: returns (page, None) or (None, error message). No GTK here."""
    try:
        style_css = style.read_css() if style is not None else ""
        scheme = style.scheme if style is not None else "auto"
        page = render_document(text, flavor_id, style_css, title, scheme, allow_remote_images=allow_remote_images)
    except FlavorUnavailableError as exc:
        return None, f"{exc}. Choose another flavor in View → Flavor, or install pandoc."
    except (RenderError, OSError) as exc:
        return None, str(exc)
    return page, None


class ViewerWindow(Gtk.ApplicationWindow):
    """One window per open document."""

    __gtype_name__ = "MdViewerWindow"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(title=APP_NAME, default_width=900, default_height=700, **kwargs)
        self.set_icon_name(APP_ID)

        self._file: Gio.File | None = None
        self._generation = 0
        self._history = History()
        self._monitor: Gio.FileMonitor | None = None
        self._reload_source = 0
        self._deleted = False
        self._expected_load_uri: str | None = None
        self._restore_scroll: float | None = None
        # Set when the user picks a flavor/style from the View menu; None = follow the defaults.
        self._flavor_override: str | None = None
        self._style_override: str | None = None

        self._build_ui()
        self._configure_webview()
        self._add_actions()
        self._restore_settings()
        self.connect("close-request", self._on_close_request)
        self._show_message("Open a Markdown file with File → Open (Ctrl+O), or drop one here.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        app = self.get_application()
        menu_bar = Gtk.PopoverMenuBar.new_from_model(app.menu_model if app is not None else None)
        box.append(menu_bar)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._search_entry = Gtk.SearchEntry(hexpand=True, placeholder_text="Find in document")
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("activate", lambda *_: self._find_step(forward=True))
        self._search_entry.connect("next-match", lambda *_: self._find_step(forward=True))
        self._search_entry.connect("previous-match", lambda *_: self._find_step(forward=False))
        self._search_entry.connect("stop-search", lambda *_: self._search_bar.set_search_mode(False))
        shift_enter = Gtk.EventControllerKey()
        shift_enter.connect("key-pressed", self._on_search_key)
        self._search_entry.add_controller(shift_enter)

        prev_btn = Gtk.Button(icon_name="go-up-symbolic", tooltip_text="Previous match (Shift+Enter)")
        prev_btn.connect("clicked", lambda *_: self._find_step(forward=False))
        next_btn = Gtk.Button(icon_name="go-down-symbolic", tooltip_text="Next match (Enter)")
        next_btn.connect("clicked", lambda *_: self._find_step(forward=True))
        self._match_label = Gtk.Label(width_chars=12, xalign=0)
        self._match_label.add_css_class("dim-label")

        search_box = Gtk.Box(spacing=6)
        search_box.append(self._search_entry)
        search_box.append(prev_btn)
        search_box.append(next_btn)
        search_box.append(self._match_label)
        self._search_bar = Gtk.SearchBar(child=search_box, show_close_button=True)
        self._search_bar.connect_entry(self._search_entry)
        self._search_bar.connect("notify::search-mode-enabled", self._on_search_mode_changed)
        box.append(self._search_bar)

        self._webview = WebKit.WebView(vexpand=True, hexpand=True)
        box.append(self._webview)
        self.set_child(box)

    def _configure_webview(self) -> None:
        settings = self._webview.get_settings()
        settings.set_enable_developer_extras(False)
        settings.set_javascript_can_open_windows_automatically(False)
        settings.set_enable_back_forward_navigation_gestures(False)

        self._webview.connect("decide-policy", self._on_decide_policy)
        self._webview.connect("load-changed", self._on_load_changed)
        self._webview.connect("context-menu", self._on_context_menu)
        # Backs the greyed-out Copy item shown when nothing is selected.
        self._copy_unavailable = Gio.SimpleAction.new("copy-unavailable", None)
        self._copy_unavailable.set_enabled(False)

        find = self._webview.get_find_controller()
        find.connect("counted-matches", self._on_counted_matches)
        find.connect("failed-to-find-text", self._on_failed_to_find)

        # Ctrl+wheel zoom: capture phase so WebKit doesn't scroll as well.
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        scroll.connect("scroll", self._on_scroll)
        self._webview.add_controller(scroll)

        # Capture phase so WebKit doesn't treat the drop as a navigation.
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        drop.connect("drop", self._on_drop)
        self._webview.add_controller(drop)

    def _add_actions(self) -> None:
        for name, callback in (
            ("close", lambda *_: self.close()),
            ("reload", lambda *_: self.reload()),
            ("print", lambda *_: self._print()),
            ("copy", lambda *_: self._webview.execute_editing_command(WebKit.EDITING_COMMAND_COPY)),
            ("select-all", lambda *_: self._webview.execute_editing_command(WebKit.EDITING_COMMAND_SELECT_ALL)),
            ("find", lambda *_: self._open_find()),
            ("find-next", lambda *_: self._find_step(forward=True)),
            ("find-previous", lambda *_: self._find_step(forward=False)),
            ("zoom-in", lambda *_: self._set_zoom(self._webview.get_zoom_level() * ZOOM_STEP)),
            ("zoom-out", lambda *_: self._set_zoom(self._webview.get_zoom_level() / ZOOM_STEP)),
            ("zoom-reset", lambda *_: self._set_zoom(1.0)),
            ("back", lambda *_: self._go_history(self._history.back())),
            ("forward", lambda *_: self._go_history(self._history.forward())),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        for name, initial, handler in (
            ("flavor", self._effective_flavor(), self._on_flavor_chosen),
            ("style", self._effective_style_id(), self._on_style_chosen),
        ):
            stateful = Gio.SimpleAction.new_stateful(name, GLib.VariantType.new("s"), GLib.Variant.new_string(initial))
            stateful.connect("change-state", handler)
            self.add_action(stateful)
        self._update_actions()

    def _update_actions(self) -> None:
        has_doc = self._file is not None
        for name in ("reload", "print", "find", "find-next", "find-previous"):
            self.lookup_action(name).set_enabled(has_doc)
        self.lookup_action("back").set_enabled(self._history.can_go_back())
        self.lookup_action("forward").set_enabled(self._history.can_go_forward())

    # ------------------------------------------------------------------
    # Flavor and style
    # ------------------------------------------------------------------

    def _styles(self) -> dict[str, Style]:
        app = self.get_application()
        return getattr(app, "styles", {})

    def _effective_flavor(self) -> str:
        settings = get_settings()
        flavor = self._flavor_override or (settings.get_string("default-flavor") if settings else DEFAULT_FLAVOR)
        return flavor if flavor in FLAVORS else DEFAULT_FLAVOR

    def _effective_style(self) -> Style | None:
        """This window's choice if it still exists, else the user's default, else the built-in default."""
        styles = self._styles()
        if self._style_override in styles:
            return styles[self._style_override]
        settings = get_settings()
        return resolve_style(styles, settings.get_string("default-style") if settings else DEFAULT_STYLE)

    def _effective_style_id(self) -> str:
        style = self._effective_style()
        return style.id if style is not None else DEFAULT_STYLE

    def _sync_choice_actions(self) -> None:
        """Make the View menu's radio items show what this window actually uses."""
        self.lookup_action("flavor").set_state(GLib.Variant.new_string(self._effective_flavor()))
        self.lookup_action("style").set_state(GLib.Variant.new_string(self._effective_style_id()))

    def _on_flavor_chosen(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        self._flavor_override = value.get_string()
        action.set_state(value)
        self.reload()

    def _on_style_chosen(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        self._style_override = value.get_string()
        action.set_state(value)
        self.reload()

    def on_defaults_changed(self) -> None:
        """Called by the app when a default changes in Preferences."""
        self._sync_choice_actions()
        self.reload()

    def on_styles_changed(self) -> None:
        """Called by the app after the user styles folder changed (added/edited/removed CSS)."""
        self._sync_choice_actions()
        self.reload()

    # ------------------------------------------------------------------
    # Document loading
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """True when no document has been loaded into this window."""
        return self._file is None

    def load_file(self, file: Gio.File) -> None:
        """Show *file* in this window (adds it to back/forward history)."""
        self._history.visit(file.get_uri())
        self._show_file(file)

    def reload(self) -> None:
        """Re-read and re-render the current file, keeping the scroll position."""
        if self._file is None:
            return
        generation = self._next_generation()

        def on_scroll(webview: WebKit.WebView, result: Gio.AsyncResult) -> None:
            try:
                scroll_y = webview.evaluate_javascript_finish(result).to_double()
            except GLib.Error:
                _log.debug("Could not read scroll position", exc_info=True)
                scroll_y = None
            if generation == self._generation and self._file is not None:
                self._read_file(self._file, generation, scroll_y, is_reload=True)

        self._webview.evaluate_javascript("window.scrollY", -1, SCRIPT_WORLD, None, None, on_scroll)

    def _show_file(self, file: Gio.File) -> None:
        if self._file is None or not self._file.equal(file):
            self._file = file
            self._watch(file)
        self._deleted = False
        self._update_title()
        self._update_actions()
        Gtk.RecentManager.get_default().add_item(file.get_uri())
        self._read_file(file, self._next_generation(), None, is_reload=False)

    def _next_generation(self) -> int:
        self._generation += 1
        return self._generation

    def _read_file(self, file: Gio.File, generation: int, scroll_y: float | None, *, is_reload: bool) -> None:
        file.load_contents_async(None, self._on_contents_loaded, (generation, scroll_y, is_reload))

    def _on_contents_loaded(
        self, file: Gio.File, result: Gio.AsyncResult, data: tuple[int, float | None, bool]
    ) -> None:
        generation, scroll_y, is_reload = data
        if generation != self._generation:
            return
        try:
            _ok, contents, _etag = file.load_contents_finish(result)
        except GLib.Error as exc:
            if is_reload:
                # A reload failed (e.g. mid-save): keep showing the last good render.
                _log.debug("Reload of %s failed: %s", file.get_parse_name(), exc.message)
            else:
                self._show_message(f"Cannot open {html.escape(file.get_parse_name())}: {html.escape(exc.message)}")
            return
        text = contents.decode("utf-8", errors="replace")
        title = file.get_basename() or file.get_uri()
        flavor_id, style = self._effective_flavor(), self._effective_style()
        settings = get_settings()
        allow_remote = settings.get_boolean("allow-remote-images") if settings else False

        def work() -> None:
            page, error = _render_page(text, title, flavor_id, style, allow_remote)
            GLib.idle_add(self._on_rendered, generation, file, page, error, scroll_y)

        threading.Thread(target=work, daemon=True).start()

    def _on_rendered(
        self, generation: int, file: Gio.File, page: str | None, error: str | None, scroll_y: float | None
    ) -> bool:
        if generation != self._generation:
            return GLib.SOURCE_REMOVE
        if page is None:
            name = html.escape(file.get_basename() or file.get_uri())
            self._show_message(f"Cannot render {name}: {html.escape(error or 'unknown error')}")
            return GLib.SOURCE_REMOVE
        self._restore_scroll = scroll_y
        self._expected_load_uri = file.get_uri()
        # Base URI = the file itself, so relative images and links resolve next to it.
        self._webview.load_html(page, file.get_uri())
        return GLib.SOURCE_REMOVE

    def _show_message(self, message: str) -> None:
        self._expected_load_uri = "about:blank"
        self._webview.load_html(_MESSAGE_HTML.format(message=message), "about:blank")

    def _on_load_changed(self, webview: WebKit.WebView, event: WebKit.LoadEvent) -> None:
        if event != WebKit.LoadEvent.FINISHED:
            return
        if self._restore_scroll is not None:
            webview.evaluate_javascript(
                f"window.scrollTo(0, {float(self._restore_scroll)})", -1, SCRIPT_WORLD, None, None, None
            )
            self._restore_scroll = None
        if self._search_bar.get_search_mode() and self._search_entry.get_text():
            self._on_search_changed(self._search_entry)

    def _update_title(self) -> None:
        if self._file is None:
            self.set_title(APP_NAME)
            return
        name = self._file.get_basename() or self._file.get_uri()
        suffix = " (deleted)" if self._deleted else ""
        self.set_title(f"{name}{suffix} — {APP_NAME}")

    def _go_history(self, uri: str | None) -> None:
        if uri is not None:
            self._show_file(Gio.File.new_for_uri(uri))

    # ------------------------------------------------------------------
    # File watching
    # ------------------------------------------------------------------

    def _watch(self, file: Gio.File) -> None:
        self._unwatch()
        try:
            self._monitor = file.monitor_file(Gio.FileMonitorFlags.WATCH_MOVES, None)
        except GLib.Error:
            _log.debug("Cannot watch %s", file.get_parse_name(), exc_info=True)
            return
        self._monitor.connect("changed", self._on_file_changed)

    def _unwatch(self) -> None:
        if self._monitor is not None:
            self._monitor.cancel()
            self._monitor = None
        if self._reload_source:
            GLib.source_remove(self._reload_source)
            self._reload_source = 0

    def _on_file_changed(
        self, _monitor: Gio.FileMonitor, _file: Gio.File, _other: Gio.File | None, event: Gio.FileMonitorEvent
    ) -> None:
        if event in _MONITOR_IGNORED_EVENTS:
            return
        # Editors save in bursts (truncate+write, or write-temp+rename): settle first.
        if self._reload_source:
            GLib.source_remove(self._reload_source)
        self._reload_source = GLib.timeout_add(RELOAD_DEBOUNCE_MS, self._on_reload_timeout)

    def _on_reload_timeout(self) -> bool:
        self._reload_source = 0
        if self._file is None:
            return GLib.SOURCE_REMOVE
        exists = self._file.query_exists(None)
        if exists:
            self._deleted = False
            self.reload()
        else:
            self._deleted = True
        self._update_title()
        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------
    # Navigation policy
    # ------------------------------------------------------------------

    def _on_decide_policy(
        self, _webview: WebKit.WebView, decision: WebKit.PolicyDecision, decision_type: WebKit.PolicyDecisionType
    ) -> bool:
        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            return False  # default handling
        if not isinstance(decision, WebKit.NavigationPolicyDecision):
            decision.ignore()
            return True

        action = decision.get_navigation_action()
        uri = action.get_request().get_uri()
        nav_type = action.get_navigation_type()

        if nav_type != WebKit.NavigationType.LINK_CLICKED:
            # Only the load we started ourselves is allowed (blocks meta refresh, form posts, …).
            if decision_type == WebKit.PolicyDecisionType.NAVIGATION_ACTION and uri == self._expected_load_uri:
                decision.use()
            else:
                decision.ignore()
            return True

        current = self._file.get_uri() if self._file is not None else None
        link_action = classify_link(uri, current)
        if link_action is LinkAction.ALLOW and decision_type == WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            decision.use()
            return True

        decision.ignore()
        if link_action is LinkAction.OPEN_DOCUMENT:
            target = Gio.File.new_for_uri(strip_fragment(uri))
            new_window = bool(action.get_modifiers() & Gdk.ModifierType.CONTROL_MASK) or action.get_mouse_button() == 2
            if new_window or decision_type == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION:
                self.get_application().new_window(target)
            else:
                self.load_file(target)
        elif link_action is LinkAction.OPEN_EXTERNAL:
            try:
                Gio.AppInfo.launch_default_for_uri(uri, None)
            except GLib.Error:
                _log.warning("No application to open %s", uri, exc_info=True)
        return True

    def _on_context_menu(self, _webview: WebKit.WebView, menu: WebKit.ContextMenu, hit: WebKit.HitTestResult) -> bool:
        menu.remove_all()
        for entry in context_menu_entries(
            selection=hit.context_is_selection(), link=hit.context_is_link(), image=hit.context_is_image()
        ):
            if not entry:
                menu.append(WebKit.ContextMenuItem.new_separator())
            elif entry == "copy-unavailable":
                menu.append(WebKit.ContextMenuItem.new_from_gaction(self._copy_unavailable, "_Copy", None))
            else:
                menu.append(WebKit.ContextMenuItem.new_from_stock_action(_CONTEXT_ACTIONS[entry]))
        return False  # show the menu

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def _on_drop(self, _target: Gtk.DropTarget, value: Gdk.FileList, _x: float, _y: float) -> bool:
        files = value.get_files()
        if not files:
            return False
        self.load_file(files[0])
        for extra in files[1:]:
            self.get_application().new_window(extra)
        return True

    # ------------------------------------------------------------------
    # Find
    # ------------------------------------------------------------------

    def _open_find(self) -> None:
        self._search_bar.set_search_mode(True)
        self._search_entry.grab_focus()
        self._search_entry.select_region(0, -1)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        text = entry.get_text()
        find = self._webview.get_find_controller()
        entry.remove_css_class("error")
        if not text:
            find.search_finish()
            self._match_label.set_text("")
            return
        find.count_matches(text, _FIND_OPTIONS, FIND_MAX_MATCHES)
        find.search(text, _FIND_OPTIONS, FIND_MAX_MATCHES)

    def _find_step(self, forward: bool) -> None:
        if not self._search_bar.get_search_mode() or not self._search_entry.get_text():
            self._open_find()
            return
        find = self._webview.get_find_controller()
        if forward:
            find.search_next()
        else:
            find.search_previous()

    def _on_search_key(self, _ctl: Gtk.EventControllerKey, keyval: int, _code: int, state: Gdk.ModifierType) -> bool:
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and state & Gdk.ModifierType.SHIFT_MASK:
            self._find_step(forward=False)
            return True
        return False

    def _on_search_mode_changed(self, bar: Gtk.SearchBar, _pspec: object) -> None:
        if not bar.get_search_mode():
            self._webview.get_find_controller().search_finish()
            self._match_label.set_text("")
            self._webview.grab_focus()

    def _on_counted_matches(self, _find: WebKit.FindController, count: int) -> None:
        self._match_label.set_text("1 match" if count == 1 else f"{count} matches")

    def _on_failed_to_find(self, _find: WebKit.FindController) -> None:
        self._match_label.set_text("No matches")
        self._search_entry.add_css_class("error")

    # ------------------------------------------------------------------
    # Zoom and print
    # ------------------------------------------------------------------

    def _set_zoom(self, level: float) -> None:
        level = min(max(level, ZOOM_MIN), ZOOM_MAX)
        if abs(level - 1.0) < 0.02:
            level = 1.0
        self._webview.set_zoom_level(level)
        settings = get_settings()
        if settings is not None:
            settings.set_double("zoom-level", level)

    def _on_scroll(self, controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        if not controller.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK:
            return False
        if dy:
            factor = ZOOM_STEP if dy < 0 else 1 / ZOOM_STEP
            self._set_zoom(self._webview.get_zoom_level() * factor)
        return True

    def _print(self) -> None:
        if self._file is not None:
            WebKit.PrintOperation.new(self._webview).run_dialog(self)

    # ------------------------------------------------------------------
    # Settings persistence and teardown
    # ------------------------------------------------------------------

    def _restore_settings(self) -> None:
        settings = get_settings()
        if settings is None:
            return
        self.set_default_size(settings.get_int("window-width"), settings.get_int("window-height"))
        if settings.get_boolean("window-maximized"):
            self.maximize()
        self._webview.set_zoom_level(settings.get_double("zoom-level"))

    def _on_close_request(self, _win: Gtk.Window) -> bool:
        self._generation += 1  # drop any in-flight render
        self._unwatch()
        settings = get_settings()
        if settings is not None:
            settings.set_boolean("window-maximized", self.is_maximized())
            if not self.is_maximized():
                width, height = self.get_default_size()
                settings.set_int("window-width", width)
                settings.set_int("window-height", height)
        return False  # allow the close to proceed
