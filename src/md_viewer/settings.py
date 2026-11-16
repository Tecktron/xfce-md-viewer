"""GSettings access with a graceful fallback when the schema is not installed.

Running from source without compiling ``data/net.tecktron.md_viewer.gschema.xml``
must not crash the app, so :func:`get_settings` returns ``None`` in that case and
callers skip persistence.
"""

from __future__ import annotations

import logging

from gi.repository import Gio

from . import APP_ID
from .highlight import Themes

_log = logging.getLogger(__name__)
_settings: Gio.Settings | None = None
_looked_up = False


def get_settings() -> Gio.Settings | None:
    """Return the shared Gio.Settings for the app, or None if the schema is missing."""
    global _settings, _looked_up
    if not _looked_up:
        _looked_up = True
        source = Gio.SettingsSchemaSource.get_default()
        if source is not None and source.lookup(APP_ID, True) is not None:
            _settings = Gio.Settings.new(APP_ID)
        else:
            _log.warning("GSettings schema %s not installed; settings will not be saved", APP_ID)
    return _settings


def highlight_themes() -> Themes:
    """The syntax-highlighting themes to use: the defaults unless the user picked their own."""
    settings = get_settings()
    if settings is None or settings.get_boolean("highlight-use-default"):
        return Themes()
    return Themes.chosen(settings.get_string("highlight-light-theme"), settings.get_string("highlight-dark-theme"))
