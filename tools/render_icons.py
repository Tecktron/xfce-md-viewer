#!/usr/bin/python3
"""Render the hicolor PNG icons from the two source SVGs in data/icons/src/.

    net.tecktron.md_viewer-small.svg  smooth "MD"  -> 16, 22, 24, 32, 48 px
    net.tecktron.md_viewer.svg        pixel "MD"   -> 64, 128, 256 px and the scalable icon

Edit the SVGs, then run:  /usr/bin/python3 tools/render_icons.py
Needs python3-gi with GdkPixbuf's SVG loader (librsvg), present on Ubuntu desktops.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

APP_ID = "net.tecktron.md_viewer"
ICONS = Path(__file__).resolve().parent.parent / "data" / "icons"
SMALL_SIZES = (16, 22, 24, 32, 48)
LARGE_SIZES = (64, 128, 256)


def main() -> None:
    small_svg = ICONS / "src" / f"{APP_ID}-small.svg"
    large_svg = ICONS / "src" / f"{APP_ID}.svg"
    for sizes, svg in ((SMALL_SIZES, small_svg), (LARGE_SIZES, large_svg)):
        for size in sizes:
            target = ICONS / "hicolor" / f"{size}x{size}" / "apps" / f"{APP_ID}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            GdkPixbuf.Pixbuf.new_from_file_at_size(str(svg), size, size).savev(str(target), "png", [], [])
            print(target.relative_to(ICONS.parent.parent))
    scalable = ICONS / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"
    scalable.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(large_svg, scalable)
    print(scalable.relative_to(ICONS.parent.parent))


if __name__ == "__main__":
    main()
