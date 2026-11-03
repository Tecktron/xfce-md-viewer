# xfce-md-viewer — Claude working guide

GTK4 + WebKitGTK Markdown **viewer** (not an editor) for Xfce.
Packaging, CI and conventions are modelled on `~/Projects/repoman`.

---

## Decision discipline — MANDATORY

When presenting the user with a choice between options, **STOP and wait for their answer.**
Never pick an option on their behalf. Never assume silence or a topic change is consent.

## Code review passes — MANDATORY

When asked to review or do "another pass": trace every exit path in every
method (not just the happy path), and compare parallel paths (success vs
failure/shortcut) for skipped side effects. "Looks good" without tracing
every branch is not a pass.

---

**Project / Debian package:** `xfce-md-viewer`
**Command:** `md-viewer`
**Python package:** `md_viewer`
**App ID:** `net.tecktron.md_viewer` (used for .desktop, gschema, metainfo, icon names)
**Platform minimum:** Xubuntu 24.04 LTS
**Target environment:** Xfce/Xfwm4 (system-decorated windows, no CSD)
**Toolkit:** plain GTK4 + WebKitGTK 6.0. **No libadwaita** — the app must follow
the user's GTK theme.
**Singleton:** `Gtk.Application` with `HANDLES_OPEN`; a second launch hands
its files to the running process (one window per file).

---

## Writing code — holistic file awareness

Before finalising any change, take a pass over the **whole file**:

- **Imports** — module-level by default; inline only to break import cycles.
- **DRY** — scan for an existing helper before writing a new one. Collapse
  functions that only delegate.
- **Type hints** — precise (`list[Path]`, `X | None` when None is valid).
  Grep call sites when a parameter can be None.
- **Broad exception handlers** — `except Exception` must be paired with
  `_log.debug(…, exc_info=True)` on the next line. No silent broad catches.
- **Dead code** — remove code with no callers.
- **Callers** — when changing a signature, update every call site in the same diff.

---

## Running the app

```bash
cd /home/craig/Projects/xfce-md-viewer
# Anchored pattern: an unanchored one also matches (and kills) the calling shell.
pkill -f "^/usr/bin/python3 -m md_viewer" 2>/dev/null; sleep 0.5
# Dev source MUST come before system dist-packages. Use /usr/bin/python3 —
# the project venv has no PyGObject.
PYTHONPATH=src:/usr/lib/python3/dist-packages DISPLAY=:0 /usr/bin/python3 -m md_viewer.main FILE.md
```

The many `Theme parser error: gtk.css` warnings come from the user's GTK theme,
not this app.

## Tests

```bash
venv/bin/pytest -q                       # pythonpath=src is set in pyproject.toml
venv/bin/ruff check src/ tests/ tools/   # ruff lives in the project venv
venv/bin/ruff format --check src/ tests/ tools/
```

Tests are pure: no display, no network. Keep rendering logic (flavors, styles,
HTML assembly) free of GTK so it stays unit-testable.

**Python packages:** dev tools (pytest, ruff) live in `venv/` (created with
`--system-site-packages`). Runtime deps are apt packages listed in
`debian/control` — never pip-install them for the app. Note the venv has its
own newer `markdown-it-py` / `Pygments` (pulled in by other tools), so local
tests use newer libraries than users get; CI on ubuntu-24.04 with apt packages
covers the minimum versions. To test locally against apt versions:
`/usr/bin/python3 -m pytest -q -p no:cacheprovider`.

**Minimum library versions (Ubuntu 24.04):** markdown-it-py 3.0.0,
mdit-py-plugins 0.4.0, pandoc 3.1.3. Don't use APIs newer than these.

---

## File structure

```
src/md_viewer/
  __init__.py     __version__ (single source of truth), APP_ID, APP_NAME
  main.py         MdViewerApplication; app actions open/about/quit; CLI parsing
  flavors.py      Flavor registry (FLAVORS), render_body(text, flavor_id) → HTML fragment.
                  Backends: markdown-it (gfm, commonmark), python-markdown (original, extra),
                  pandoc subprocess (pandoc, commonmark_x, mmd, rmd). Raises
                  FlavorUnavailableError / RenderError.
  highlight.py    highlight_code_blocks(): one post-processing pass for all backends;
                  normalises code blocks to <pre class="highlight"><code class="language-X">.
                  Skips mermaid/math. highlight_css() = light + dark (prefers-color-scheme).
  styles.py       discover_styles() → {id: Style}; built-ins + ~/.local/share/md-viewer/styles/
                  (user wins on id clash); name/description from leading /* name: … */ comment.
  document.py     build_page() / render_document(); CONTENT_SECURITY_POLICY blocks scripts
                  and network; style CSS escaped so it can't close </style>.
  paths.py        data_dir() (repo data/ in dev, /usr/share/xfce-md-viewer installed),
                  builtin_styles_dir(), user_styles_dir()
  settings.py     get_settings() → Gio.Settings | None (None when schema not installed)
  links.py        classify_link(target, current) → LinkAction (ALLOW in-page anchor,
                  OPEN_DOCUMENT local .md, OPEN_EXTERNAL file/web/mail, BLOCK other schemes)
  history.py      History — browser-style back/forward list of file URIs
  ui/menus.py     ACCELS (all shortcuts, registered once by the app);
                  build_menu_model(recent, flavor, style menus) — one model shared by all
                  windows; fill_flavor_menu() (pandoc flavors → disabled
                  "win.flavor-unavailable" when pandoc missing); fill_style_menu();
                  context_menu_entries()
  ui/shortcuts.py ShortcutsWindow (plain Gtk.Window; Gtk.ShortcutsWindow is deprecated
                  since GTK 4.18) built from menus.SHORTCUT_HELP + ACCELS; a unit test
                  enforces that every ACCELS entry is listed and vice versa.
  ui/preferences.py
                  PreferencesWindow (Gtk.Window, instant-apply): default flavor/style
                  dropdowns, allow-remote-images checkbox (settings.bind), styles folder.
                  Disconnects its GSettings handlers on close; settings changes only
                  re-select (never rebuild the model inside notify::selected).
  ui/window.py    ViewerWindow (Gtk.ApplicationWindow): PopoverMenuBar, Gtk.SearchBar,
                  WebKit.WebView. See "Viewer window" below.
data/styles/      built-in styles — see "Built-in styles (8)". All but plain.css are
                  GENERATED by tools/update_vendored.py; never hand-edit, change
                  STYLE_PACKAGES in the script and re-run.
data/vendor/      katex/ (js, css, woff2 fonts), mermaid/ (mermaid.min.js) and latex.css/
                  (Latin Modern woff2 fonts for the LaTeX style), each with
                  LICENSE and VERSION — vendored by tools/update_vendored.py; never hand-edit.
data/js/enhance.js
                  OUR page script (mdViewer.enhance / scrollToId), runs in SCRIPT_WORLD.
src/md_viewer/postprocess.py
                  postprocess(body) → Processed: normalises pandoc mermaid and ```math,
                  adds unique GitHub-style heading ids (keeps existing), collects
                  headings for the TOC, flags has_math / has_mermaid.
data/icons/        hicolor PNGs 16–256 + scalable SVG, GENERATED by tools/render_icons.py from
                  data/icons/src/: -small.svg (smooth "MD", 16–48 px) and the main SVG
                  (pixel "MD" from the original 32 px icon; 64–256 px and scalable).
tools/update_vendored.py
                  stdlib-only; packages github-markdown-css, katex, mermaid; verifies npm
                  sha512 integrity; reads only named tar members; --check [PKG] exits 1
                  when outdated; `update_vendored.py PKG VERSION` pins a version.
```

## Vendored assets

`.github/workflows/update-vendored.yml` runs monthly (15th, 15:00 UTC) as a matrix over all six
packages (github-markdown-css, water.css, simpledotcss, latex.css, katex, mermaid); each with a new release gets its own PR (branch `vendored/PKG-VERSION`). Needs the repo setting
"Allow GitHub Actions to create and approve pull requests". PRs opened with
`GITHUB_TOKEN` don't fire `pull_request` workflows, so the job then runs
`gh workflow run ci.yml --ref <branch>` (ci.yml has `workflow_dispatch`; needs
`actions: write`). License for vendored
files is recorded in `debian/copyright`.

---

## Viewer window (ui/window.py)

- **Loading:** `load_contents_async` → `_render_page()` in a daemon thread →
  `GLib.idle_add(_on_rendered)` → `load_html(page, base_uri=file uri)`.
  `self._generation` is bumped on every load/reload/close; callbacks with a stale
  generation do nothing. `is_reload=True` failures keep the last good render.
- **Navigation policy (`_on_decide_policy`):** non-click navigations are allowed
  only when the URI equals `self._expected_load_uri` (set just before our own
  `load_html`) — this blocks meta refresh, forms, WebKit's own file drops. Clicks
  go through `classify_link`. External opens use `Gio.AppInfo.launch_default_for_uri`
  (works on Xfce without a portal).
- **Our JavaScript** runs in the isolated world `SCRIPT_WORLD` via
  `evaluate_javascript`; the page CSP does not block it, and the document can't see it.
- **File watching:** `Gio.FileMonitor` (WATCH_MOVES), debounced `RELOAD_DEBOUNCE_MS`;
  on timeout, `query_exists` decides reload vs "(deleted)" title.
- **Context menu** is rebuilt from scratch from the hit test via
  `menus.context_menu_entries()` (WebKit's default has Reload/Back/Open Link, which
  would bypass our policy, and only offers Select All for editable content).
  Layout: Copy (greyed via a disabled GAction when nothing is selected), Copy Link /
  Copy Image extras, separator, Select All.
- **File → Close All** is its own menu section using `app.quit-all` with
  `hidden-when="action-disabled"`; the app enables that action only while more than
  one ViewerWindow is open (`window-added` / `window-removed`), so with one window
  only Close shows and the section's separator disappears too. Ctrl+Q is bound to
  `app.quit`, which is always enabled.
- **GTK 4 popover menus have a ~46 px minimum height**, so any one-item menu shows
  ~20 px of empty space at the bottom (theme-independent). Never ship a one-item menu.
- **Copy / Select All** are native WebKit keys; menu items only *display* the accel.

**Manual test harness:** GTK/WebKit wiring isn't unit-tested. To exercise it,
drive a real window in-process (create `MdViewerApplication`, swap its
`activate` handler, step with `GLib.timeout_add`, inspect via
`evaluate_javascript` in `SCRIPT_WORLD`). Use `GSETTINGS_BACKEND=memory` and a
temp compiled schema dir. Use `win.activate_action("win.<name>")` — the bare
name silently does nothing. Synthetic X input is blocked by Xfwm focus-stealing
prevention, so don't rely on xdotool keys/clicks.

## Flavors, styles and defaults

- GSettings: `default-flavor`, `default-style`, `allow-remote-images`, `zoom-level`,
  window size keys.
- **App** (`main.py`) owns `styles` (re-scanned when the user styles dir changes,
  debounced `STYLES_RESCAN_DELAY_MS`), `pandoc_available` (checked at startup), the
  flavor/style menus and the single Preferences window. On a defaults change or a
  styles change it calls `ViewerWindow.on_defaults_changed()` / `on_styles_changed()`
  on every window.
- **Window** has stateful actions `win.flavor` / `win.style` (string targets, radio
  items in View). Picking one sets `_flavor_override` / `_style_override`; `None`
  means "follow the defaults". Effective style = override if it still exists →
  user default → built-in default (`resolve_style`).
- Remote images: `document.content_security_policy(allow_remote_images)`; scripts
  are blocked in both policies.

## Math, diagrams and table of contents

- `document.render_document()` returns `Rendered(page, headings, has_math, has_mermaid)`.
  KaTeX CSS is inlined only when `has_math`, with font URLs rewritten to the bundled
  `file://` fonts; the CSP allows `font-src file:` (still no script-src).
- GFM math: `dollarmath_plugin(allow_space=False, allow_digits=False)` — GitHub-like,
  "$5 or $10" stays text. `double_inline` is OFF (it emits <div> inside <p>).
  Pandoc runs with `--katex`. CommonMark/original/Extra have no math (per spec).
- Window: `_install_page_scripts()` before each load_html (enhance.js always;
  KaTeX/Mermaid only when needed; UserScript objects cached per process via
  `_user_script`). On load FINISHED, `mdViewer.enhance({scheme})` runs via
  `call_async_javascript_function` in SCRIPT_WORLD; scroll restore and find
  re-run happen in `_after_page_ready()` AFTER enhancement (diagrams change height).
- TOC: Gtk.Paned (start = ListBox "navigation-sidebar", end = WebView). The View
  menu shows "Show Table of Contents" OR "Hide Table of Contents" (win.toc-show /
  win.toc-hide, hidden-when=action-disabled; each window enables only the matching
  one — no checkbox, Craig found it crowded). F9 = win.toc toggle. Persisted as
  `show-toc`. Row click → `mdViewer.scrollToId`.
- The search bar is hidden (not just collapsed) when closed: Greybird draws its
  padding/border even with the revealer shut (7 px band under the menu bar).

## Built-in styles (8)

github, github-light, github-dark, github-dark-high-contrast (github-markdown-css),
water (water.css), simple (npm `simpledotcss` — NOT the unrelated npm `simple.css`),
latex (latex.css), plain (ours). Considered and not picked: Tufte CSS; skipped:
Typora themes (mixed licences, Typora-specific markup), CSS frameworks, Pandoc's
default CSS (GPL).

- All but plain.css are GENERATED by `tools/update_vendored.py` from `STYLE_PACKAGES`
  (`StyleSpec`: upstream file, header fields, layout CSS, checked regex removals and
  literal rewrites — a rewrite whose text vanished upstream fails the update).
- LaTeX.css: Libertinus @font-face blocks removed (opt-in upstream, not bundled);
  `.latex-dark-auto {` → `body {` (we have no body class); its 4 Latin Modern woff2
  fonts are vendored in data/vendor/latex.css/fonts/ (GUST Font License stanza in
  debian/copyright, text taken from Ubuntu's fonts-lmodern).
- Style CSS is inlined into the page, so relative font URLs would resolve against the
  .md file: vendored CSS uses `md-viewer-vendor:/<pkg>/…`, which `Style.read_css()`
  turns into the real data/vendor/ URL.
- Page wrapper is `<div class="markdown-body">`, NOT `<article>`: classless styles
  (Simple.css) draw every <article> as a bordered card. `document.BASE_CSS` (before
  every style, overridable) hides task-list bullets, which non-GitHub styles show.

## Theming notes

GTK 4 has no classic menus; all menus are popovers styled by the theme's
`gtk-4.0/gtk.css`. Greybird's GTK 4 port is partial (the `Theme parser error`
warnings), so menus won't match GTK 3 apps exactly. Accepted for now. repoman
can't help here: it uses libadwaita, which ignores the system theme.

## Window management

All windows are `Gtk.ApplicationWindow` / `Gtk.Window` so Xfwm4 draws the titlebar.
No `Adw.*`. No window positioning code — placement is the WM's job.

## Threading rules

- Background work runs in `threading.Thread(daemon=True)`.
- Results return to the GTK main thread only via `GLib.idle_add(callback, *args)`;
  callbacks return `GLib.SOURCE_REMOVE`.
- Never touch GTK widgets from a background thread.

---

## Releasing

The version lives in three places, kept in sync by `tests/test_package.py`:
`src/md_viewer/__init__.py`, the top entry of `debian/changelog`, and a
`<release>` in `data/net.tecktron.md_viewer.metainfo.xml`.

**Versioning:** this is a *native* Debian package (`debian/source/format` =
`3.0 (native)`): the changelog version is the plain app version, e.g. `1.0.0`,
never `1.0.0-1` (lintian error `malformed-debian-changelog-version`). For PPA
rebuilds of the same release per Ubuntu series, append e.g. `~noble1`.
(repoman uses `-1` without a declared format; that's a historical accident, not a
convention to copy.) `debian/source/options` keeps venv/caches out of the source
tarball — dpkg-source packs the working directory, not the git tree.

Before a release, validate: `appstreamcli validate --no-net data/*.metainfo.xml`,
`desktop-file-validate data/*.desktop`, and `lintian --pedantic` on the .changes
(expected: `initial-upload-closes-no-bugs` for Debian-archive ITPs only, and
pedantic notes about the vendored minified JS / restated default fields).

Build: `dpkg-buildpackage -us -uc` (output in `../`).
Publishing a GitHub release triggers `.github/workflows/build-deb.yml`,
which attaches the .deb.

Runtime deps (system packages): `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-webkit-6.0`,
`python3-markdown-it`, `python3-mdit-py-plugins`, `python3-markdown`, `python3-pygments`.
Recommends: `pandoc`.
Build deps: `debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools`.
