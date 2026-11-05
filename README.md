# xfce-md-viewer

A lightweight GTK4 Markdown **viewer** (not an editor) for the Xfce desktop.

Open a `.md` file and read it, rendered the way its author intended: in the
Markdown flavor and look of your choice, with math, diagrams and a table of
contents. Plain GTK 4, so it follows your Xfce theme.

## Features

- Multiple Markdown flavors: GitHub Flavored (default), CommonMark, original
  Markdown.pl, PHP Markdown Extra — plus Pandoc Markdown, MultiMarkdown and
  R Markdown when `pandoc` is installed
- Eight built-in CSS styles, plus your own (drop a `.css` file into
  `~/.local/share/md-viewer/styles/`):
  - **GitHub**, **GitHub Light**, **GitHub Dark** and **GitHub Dark High Contrast**
    ([github-markdown-css](https://github.com/sindresorhus/github-markdown-css))
  - **Water** ([Water.css](https://github.com/kognise/water.css)) and
    **Simple** ([Simple.css](https://github.com/kevquirk/simple.css)): clean, minimal
  - **LaTeX** ([LaTeX.css](https://github.com/vincentdoerig/latex-css)): looks like a
    LaTeX paper, with Latin Modern fonts
  - **Plain**: minimal, uses your system fonts
- Switch flavor and style per window from the **View** menu; choose your
  defaults in **Edit → Preferences**
- Auto-reload when the file changes on disk
- Syntax-highlighted code blocks, math (KaTeX) and Mermaid diagrams
- Table of contents sidebar (View → Show Table of Contents, or F9)
- Find, zoom, print / export to PDF
- Opens `.md` files from Thunar and other file managers

## Requirements

- Xubuntu / Ubuntu 24.04 or newer
- Python 3.12+
- GTK 4 and WebKitGTK 6.0, markdown-it-py, mdit-py-plugins, Python-Markdown and
  Pygments (all installed automatically with the .deb)
- Optional: `pandoc`, for the Pandoc, MultiMarkdown and R Markdown flavors

## Installation

### From the PPA (recommended)

```bash
sudo add-apt-repository ppa:tecktron-studios/xfce-md-viewer
sudo apt update
sudo apt install xfce-md-viewer
```

You get updates with the rest of your system. Supported Ubuntu releases:
Noble (24.04 LTS), Resolute (26.04 LTS) and Stonking (26.10). Install `pandoc`
too if you want the Pandoc, MultiMarkdown and R Markdown flavors (apt installs
it by default as a recommended package).

### From a .deb package

Download the latest `.deb` from the
[Releases page](https://github.com/Tecktron/xfce-md-viewer/releases), then:

```bash
sudo apt install ./xfce-md-viewer_*.deb
```

### Manual install with make

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0 \
    python3-markdown-it python3-mdit-py-plugins python3-markdown python3-pygments
sudo make install          # installs to /usr
sudo make uninstall        # removes it again
```

## Usage

```bash
md-viewer README.md        # open a file
md-viewer a.md b.md        # one window per file
```

### Flavors and styles

**View → Flavor** and **View → Style** change the current window. Your defaults
for new windows (GitHub Flavored + GitHub to start) live in
**Edit → Preferences**; windows you haven't switched by hand follow them.

### Custom styles

Put a `.css` file in `~/.local/share/md-viewer/styles/` (Preferences has an
**Open Styles Folder** button). It shows up in View → Style immediately, and
edits re-render open documents live. Start it with a header:

```css
/* name: My Style
   description: One line about it
   scheme: auto */
```

`scheme` is `light`, `dark` or `auto` (follow the system) and picks matching
code-highlighting colours. Rendered Markdown sits inside
`<div class="markdown-body">` (a `<div>`, so classless stylesheets that style
`<article>` as a card don't); code blocks are
`<pre class="highlight"><code class="language-…">`. A user style with the same
file name as a built-in one replaces it.

### Math and diagrams

In GitHub Flavored Markdown, write inline math as `$x^2$` (no space inside the
dollars, so prices like "$5 or $10" stay text) and display math as `$$ … $$` on
its own lines or in a ` ```math ` block. Pandoc flavors use pandoc's math
syntax. CommonMark, original Markdown and Markdown Extra have no math syntax.

` ```mermaid ` blocks become diagrams. A diagram with an error stays visible as
source text. Math and diagrams are rendered by the viewer itself with bundled
copies of KaTeX and Mermaid, and work offline.

### Remote content

Documents can't run scripts or reach the network. To show images hosted on
the web, enable **Load remote images** in Preferences.

### Other

You can also drag files onto a window. The view reloads automatically when
the file changes on disk, keeping your scroll position. Links to other
Markdown files open in the same window (Ctrl+click: new window); web links
open in your browser.

Or right-click a `.md` file in Thunar → **Open With → Markdown Viewer**.

| Shortcut | Action |
|---|---|
| Ctrl+O | Open file |
| Ctrl+, | Preferences |
| Ctrl+? | Keyboard shortcuts (also Help → Keyboard Shortcuts) |
| F5 / Ctrl+R | Reload |
| Ctrl+P | Print / export to PDF |
| Ctrl+F | Find |
| F3 / Shift+F3 | Next / previous match |
| Ctrl+= / Ctrl+− / Ctrl+0 | Zoom in / out / reset (or Ctrl+mouse wheel) |
| Alt+← / Alt+→ | Back / forward |
| F9 | Table of contents |
| Ctrl+W | Close window |
| Ctrl+Q | Close all windows |

## Running from source (development)

Runtime libraries come from apt (they are the .deb's dependencies); dev tools
(pytest, ruff) live in a local venv that can see the system packages:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0 \
    python3-markdown-it python3-mdit-py-plugins python3-markdown python3-pygments
python3 -m venv --system-site-packages venv
venv/bin/pip install pytest ruff

# Dev source must come before system dist-packages, otherwise an
# installed .deb version wins.
PYTHONPATH=src:/usr/lib/python3/dist-packages /usr/bin/python3 -m md_viewer.main README.md
```

Without the installed GSettings schema, settings (window size) are not saved;
the app logs a warning and carries on.

## Building a .deb

```bash
# Build tools (once)
sudo apt install debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools

dpkg-buildpackage -us -uc          # output lands in ../
sudo apt install ../xfce-md-viewer_*_all.deb
```

Publishing a GitHub release builds the .deb automatically and attaches it to
the release (`.github/workflows/build-deb.yml`).

## Testing

```bash
venv/bin/pytest -q
venv/bin/ruff check src/ tests/
venv/bin/ruff format --check src/ tests/
```

CI runs the tests on Ubuntu 24.04 with the apt-packaged libraries, which are
the oldest versions the app supports.

## Project layout

```
bin/md-viewer          launcher script (used by make install)
src/md_viewer/
  main.py              MdViewerApplication — single instance, opens files, recent menu
  flavors.py           Markdown flavors and their parser backends
  highlight.py         pygments syntax highlighting for code blocks
  postprocess.py       heading ids, table of contents, math/diagram detection
  styles.py            CSS style discovery (built-in + user)
  document.py          assembles the final HTML page
  links.py             what a clicked link does (open here / externally / block)
  history.py           back/forward history
  paths.py             data and user directories
  settings.py          GSettings with fallback when schema is missing
  ui/window.py         ViewerWindow — WebKit view, reload, find, zoom, print
  ui/menus.py          menu bar model, flavor/style submenus, keyboard shortcuts
  ui/preferences.py    Preferences window
  ui/shortcuts.py      Keyboard Shortcuts window (generated from ui/menus.py)
data/                  .desktop, GSettings schema, AppStream metainfo, icons
data/styles/           built-in CSS styles (github*.css are generated — see tools/)
data/icons/src/        icon source SVGs (small sizes / large sizes + scalable)
tools/                 update_vendored.py: refresh vendored styles, KaTeX, Mermaid from npm
                       render_icons.py: regenerate the PNG icons from data/icons/src/
data/js/               the viewer's own page script (math/diagram rendering)
data/vendor/           bundled KaTeX, Mermaid and the LaTeX style's fonts
debian/                Debian packaging
tests/                 pure unit tests (no GTK display needed)
```

## Reporting problems

Use **Help → Report a Problem**, or open an issue at
<https://github.com/Tecktron/xfce-md-viewer/issues>. Include your Ubuntu
release, the app version (Help → About) and, for rendering problems, the
Markdown file plus the flavor and style you were using.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
