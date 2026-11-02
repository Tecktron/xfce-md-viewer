# Contributing to xfce-md-viewer

## Getting started

1. Fork the repository and create a feature branch from `main`.
2. Set up your dev environment — see [Running from source](README.md#running-from-source-development).
3. Keep pull requests focused: one feature or fix per PR.
4. Describe what changed and why.

## Running tests

```bash
python3 -m pytest tests/ -q
```

Tests are pure (no GTK display, no network) and must all pass.

## Lint and format

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Code conventions

See [CLAUDE.md](CLAUDE.md) for the full coding guide.

## Adding a style

Styles are plain CSS files applied to the rendered HTML. To share a style,
add it to `data/styles/` with a comment header naming the style and its
license, and open a PR.

## What we don't accept

- libadwaita widgets — the app uses plain GTK4 so it follows the user's Xfce theme
- GNOME-portal or GNOME-specific service dependencies
- Window positioning code — placement is left to the window manager
- Editing features — this is a viewer

## Reporting bugs

Open an issue at <https://github.com/Tecktron/xfce-md-viewer/issues> with your
Ubuntu/Xubuntu release, the app version (Help → About) and steps to reproduce.
If it's a rendering issue, attach the Markdown file and say which flavor/style
you were using.
