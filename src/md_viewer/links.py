"""Decide what a clicked link should do. Pure (no GTK) so the rules are unit-tested.

The document is loaded with ``WebView.load_html(page, base_uri=<file uri>)``,
so relative links resolve against the Markdown file's location.
"""

from __future__ import annotations

import enum
from pathlib import PurePosixPath
from urllib.parse import urlsplit, urlunsplit

MARKDOWN_EXTENSIONS = frozenset({".md", ".markdown", ".mdown", ".mkd", ".mkdn", ".mdwn", ".rmd"})


class LinkAction(enum.Enum):
    ALLOW = "allow"  # let WebKit handle it (in-page #anchor)
    OPEN_DOCUMENT = "open-document"  # open in the viewer
    OPEN_EXTERNAL = "open-external"  # hand to the desktop's default handler
    BLOCK = "block"  # ignore


def strip_fragment(uri: str) -> str:
    parts = urlsplit(uri)
    return urlunsplit(parts._replace(fragment=""))


def is_markdown_uri(uri: str) -> bool:
    parts = urlsplit(uri)
    return PurePosixPath(parts.path).suffix.lower() in MARKDOWN_EXTENSIONS


def classify_link(target_uri: str, document_uri: str | None) -> LinkAction:
    """What to do when the user activates a link to *target_uri* from *document_uri*."""
    parts = urlsplit(target_uri)
    scheme = parts.scheme.lower()

    if document_uri is not None and parts.fragment and strip_fragment(target_uri) == strip_fragment(document_uri):
        return LinkAction.ALLOW
    if scheme == "file":
        return LinkAction.OPEN_DOCUMENT if is_markdown_uri(target_uri) else LinkAction.OPEN_EXTERNAL
    if scheme in {"http", "https", "mailto", "ftp", "sftp", "irc", "ircs", "xmpp", "tel"}:
        return LinkAction.OPEN_EXTERNAL
    # about:, data:, javascript:, custom schemes — never act on them.
    return LinkAction.BLOCK
