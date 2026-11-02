# xfce-md-viewer

A lightweight GTK4 Markdown **viewer** (not an editor) for the Xfce desktop.

> **Status:** early development (0.1.0). The window and packaging are in place;
> rendering, flavors and styles are being built. See the roadmap below.

## Planned features

- Multiple Markdown flavors: GitHub Flavored (default), CommonMark, original
  Markdown.pl, PHP Markdown Extra — plus Pandoc Markdown, MultiMarkdown and
  R Markdown when `pandoc` is installed
- CSS styles, including your own: drop a `.css` file into
  `~/.local/share/md-viewer/styles/`
- Choose your default flavor and style
- Auto-reload when the file changes on disk
- Syntax-highlighted code blocks, math (KaTeX) and Mermaid diagrams
- Find, zoom, print / export to PDF
- Opens `.md` files from Thunar and other file managers

## Requirements

- Xubuntu / Ubuntu 24.04 or newer
- Python 3.12+
- GTK 4 and WebKitGTK 6.0 (installed automatically with the .deb)

## Installation

### From a .deb package

Download the latest `.deb` from the
[Releases page](https://github.com/Tecktron/xfce-md-viewer/releases), then:

```bash
sudo apt install ./xfce-md-viewer_*.deb
```

### Manual install with make

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0
sudo make install          # installs to /usr
sudo make uninstall        # removes it again
```

## Usage

```bash
md-viewer README.md        # open a file
md-viewer a.md b.md        # one window per file
```

Or right-click a `.md` file in Thunar → **Open With → Markdown Viewer**.

| Shortcut | Action |
|---|---|
| Ctrl+O | Open file |
| Ctrl+W | Close window |
| Ctrl+Q | Quit |

## Running from source (development)

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0 python3-pytest

# Dev source must come before system dist-packages, otherwise an
# installed .deb version wins.
PYTHONPATH=src:/usr/lib/python3/dist-packages python3 -m md_viewer.main README.md
```

Without the installed GSettings schema, settings (window size) are not saved;
the app logs a warning and carries on.

## Building a .deb

```bash
# Build tools (once)
sudo apt install debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools

dpkg-buildpackage -us -uc          # output lands in ../
sudo apt install ../xfce-md-viewer_*.deb
```

Publishing a GitHub release builds the .deb automatically and attaches it to
the release (`.github/workflows/build-deb.yml`).

## Testing

```bash
python3 -m pytest tests/ -q
ruff check src/ tests/
ruff format --check src/ tests/
```

## Project layout

```
bin/md-viewer          launcher script (used by make install)
src/md_viewer/
  main.py              MdViewerApplication — single instance, opens files
  settings.py          GSettings with fallback when schema is missing
  ui/window.py         ViewerWindow — menu bar + WebKit view
data/                  .desktop, GSettings schema, AppStream metainfo, icons
debian/                Debian packaging
tests/                 pure unit tests (no GTK display needed)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
