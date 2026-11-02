"""GSettings access with a graceful fallback when the schema is not installed.

Running from source without compiling ``data/net.tecktron.md_viewer.gschema.xml``
must not crash the app, so :func:`get_settings` returns ``None`` in that case and
callers skip persistence.
"""

from __future__ import annotations

import logging

from gi.repository import Gio

from . import APP_ID

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
