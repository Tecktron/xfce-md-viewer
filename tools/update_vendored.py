#!/usr/bin/python3
"""Refresh vendored third-party assets from npm.

Packages:
    github-markdown-css  -> data/styles/github*.css   (generated: header + upstream CSS + layout)
    water.css            -> data/styles/water.css
    simpledotcss         -> data/styles/simple.css    (Simple.css; NOT the unrelated npm "simple.css")
    latex.css            -> data/styles/latex.css + data/vendor/latex.css/fonts/ (Latin Modern woff2)
    katex                -> data/vendor/katex/         (katex.min.js, katex.min.css, fonts/*.woff2)
    mermaid              -> data/vendor/mermaid/       (mermaid.min.js)

Usage:
    tools/update_vendored.py                      # update every package to its latest version
    tools/update_vendored.py katex                # update one package
    tools/update_vendored.py katex 0.19.1         # pin one package to a version
    tools/update_vendored.py --check [PKG ...]    # exit 1 if any (listed) package is outdated

Every tarball is verified against npm's sha512 integrity before use, and only
named files are read from it (no extraction to disk). Do not hand-edit the
generated/vendored files; change this script and re-run it.

Only the Python standard library is used, so the GitHub Action needs no setup.
"""

from __future__ import annotations

import argparse
import base64
import functools
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REGISTRY = "https://registry.npmjs.org"
ROOT = Path(__file__).resolve().parent.parent
STYLES_DIR = ROOT / "data" / "styles"
VENDOR_DIR = ROOT / "data" / "vendor"

# ----------------------------------------------------------------------
# npm access
# ----------------------------------------------------------------------


def _fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-https URL: {url}")
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 — https enforced above
        return response.read()


def _metadata(package: str, version: str) -> dict:
    return json.loads(_fetch(f"{REGISTRY}/{package}/{version}"))


def _verified_tarball(meta: dict) -> tarfile.TarFile:
    data = _fetch(meta["dist"]["tarball"])
    algo, _, expected = meta["dist"]["integrity"].partition("-")
    if algo != "sha512":
        raise ValueError(f"unexpected integrity algorithm: {algo}")
    if base64.b64encode(hashlib.sha512(data).digest()).decode() != expected:
        raise ValueError(f"{meta['name']} {meta['version']}: tarball integrity check failed")
    return tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")


def _read(tar: tarfile.TarFile, name: str) -> bytes:
    member = tar.getmember(f"package/{name}")
    if not member.isfile():
        raise ValueError(f"{name} is not a regular file in the tarball")
    extracted = tar.extractfile(member)
    assert extracted is not None
    return extracted.read()


def _license_text(tar: tarfile.TarFile) -> bytes:
    for name in ("LICENSE", "license", "LICENSE.md", "LICENSE.txt"):
        try:
            return _read(tar, name)
        except KeyError:
            continue
    raise ValueError("no license file in tarball")


# ----------------------------------------------------------------------
# CSS style packages -> data/styles/<stem>.css (+ fonts in data/vendor/<package>/)
# ----------------------------------------------------------------------

# Style CSS is inlined into each page, so relative font URLs would resolve against
# the Markdown file. Vendored styles use this prefix instead; styles.Style.read_css()
# replaces it with the installed data/vendor/ URL.
VENDOR_URL_PREFIX = "md-viewer-vendor:/"

LAYOUT_HEADER = "\n/* ---- xfce-md-viewer layout (not part of upstream) ---- */\n"

GITHUB_LAYOUT_CSS = (
    LAYOUT_HEADER
    + """html, body {
  margin: 0;
  padding: 0;
}
.markdown-body {
  box-sizing: border-box;
  min-height: 100vh;
  padding: 32px max(16px, calc((100% - 980px) / 2));
}
"""
)


@dataclass(frozen=True)
class StyleSpec:
    stem: str  # output file data/styles/<stem>.css (= style id)
    upstream_file: str  # path inside the npm package
    name: str
    description: str
    scheme: str  # light | dark | auto
    layout: str = ""
    removals: tuple[str, ...] = ()  # regexes; each must match at least once
    rewrites: tuple[tuple[str, str], ...] = ()  # literal (old, new); each old must be present


@dataclass(frozen=True)
class StylePackage:
    author: str
    homepage: str
    styles: tuple[StyleSpec, ...]
    fonts: tuple[str, ...] = ()  # package paths copied to data/vendor/<package>/fonts/


STYLE_PACKAGES: dict[str, StylePackage] = {
    "github-markdown-css": StylePackage(
        "Sindre Sorhus",
        "https://github.com/sindresorhus/github-markdown-css",
        (
            StyleSpec(
                "github",
                "github-markdown.css",
                "GitHub",
                "GitHub's Markdown look; follows the system light/dark setting",
                "auto",
                GITHUB_LAYOUT_CSS,
            ),
            StyleSpec(
                "github-light",
                "github-markdown-light.css",
                "GitHub Light",
                "GitHub's Markdown look, always light",
                "light",
                GITHUB_LAYOUT_CSS,
            ),
            StyleSpec(
                "github-dark",
                "github-markdown-dark.css",
                "GitHub Dark",
                "GitHub's Markdown look, always dark",
                "dark",
                GITHUB_LAYOUT_CSS,
            ),
            StyleSpec(
                "github-dark-high-contrast",
                "github-markdown-dark-high-contrast.css",
                "GitHub Dark High Contrast",
                "GitHub's high-contrast dark look, for low vision",
                "dark",
                GITHUB_LAYOUT_CSS,
            ),
        ),
    ),
    "water.css": StylePackage(
        "Kognise",
        "https://github.com/kognise/water.css",
        (
            StyleSpec(
                "water",
                "out/water.css",
                "Water",
                "Clean and minimal (Water.css); follows the system light/dark setting",
                "auto",
            ),
        ),
    ),
    "simpledotcss": StylePackage(
        "Kev Quirk",
        "https://github.com/kevquirk/simple.css",
        (
            StyleSpec(
                "simple",
                "simple.css",
                "Simple",
                "Readable and classless (Simple.css); follows the system light/dark setting",
                "auto",
            ),
        ),
    ),
    "latex.css": StylePackage(
        "Vincent Dörig",
        "https://github.com/vincentdoerig/latex-css",
        (
            StyleSpec(
                "latex",
                "style.css",
                "LaTeX",
                "Looks like a LaTeX document (LaTeX.css); follows the system light/dark setting",
                "auto",
                # Libertinus is opt-in upstream (body.libertinus) and not bundled.
                removals=(r"@font-face\s*\{[^}]*Libertinus[^}]*\}",),
                rewrites=(
                    ("./fonts/", f"{VENDOR_URL_PREFIX}latex.css/fonts/"),
                    # Upstream's automatic dark mode needs <body class="latex-dark-auto">;
                    # our page has no body class, so apply it to body directly.
                    (".latex-dark-auto {", "body {"),
                ),
            ),
        ),
        fonts=tuple(f"fonts/LM-{w}.woff2" for w in ("regular", "italic", "bold", "bold-italic")),
    ),
}


def _style_current(package: str) -> str | None:
    path = STYLES_DIR / f"{STYLE_PACKAGES[package].styles[0].stem}.css"
    if not path.is_file():
        return None
    match = re.search(rf"upstream: {re.escape(package)} (\S+)", path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _transform(spec: StyleSpec, css: str) -> str:
    for pattern in spec.removals:
        css, count = re.subn(pattern, "", css, flags=re.DOTALL)
        if not count:
            raise ValueError(f"{spec.stem}: removal pattern no longer matches upstream: {pattern}")
    for old, new in spec.rewrites:
        if old not in css:
            raise ValueError(f"{spec.stem}: expected text no longer in upstream CSS: {old!r}")
        css = css.replace(old, new)
    return css


def _style_install(package: str, tar: tarfile.TarFile, meta: dict) -> None:
    pkg = STYLE_PACKAGES[package]
    for spec in pkg.styles:
        css = _transform(spec, _read(tar, spec.upstream_file).decode("utf-8"))
        header = (
            f"/* name: {spec.name}\n"
            f"   description: {spec.description}\n"
            f"   scheme: {spec.scheme}\n"
            f"   upstream: {package} {meta['version']} ({meta.get('license', 'MIT')}, {pkg.author}, {pkg.homepage})\n"
            "   Generated by tools/update_vendored.py — do not edit by hand. */\n\n"
        )
        (STYLES_DIR / f"{spec.stem}.css").write_text(header + css.rstrip() + "\n" + spec.layout, encoding="utf-8")
    if pkg.fonts:
        target = _fresh_vendor_dir(package)
        (target / "fonts").mkdir()
        for font in pkg.fonts:
            (target / "fonts" / PurePosixPath(font).name).write_bytes(_read(tar, font))
        (target / "LICENSE").write_bytes(_license_text(tar))
        (target / "VERSION").write_text(meta["version"] + "\n", encoding="utf-8")


# ----------------------------------------------------------------------
# katex / mermaid (copied into data/vendor/<package>/)
# ----------------------------------------------------------------------


def _vendor_current(package: str) -> str | None:
    path = VENDOR_DIR / package / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def _fresh_vendor_dir(package: str) -> Path:
    target = VENDOR_DIR / package
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    return target


def _katex_install(tar: tarfile.TarFile, meta: dict) -> None:
    target = _fresh_vendor_dir("katex")
    (target / "fonts").mkdir()
    for name in ("katex.min.js", "katex.min.css"):
        (target / name).write_bytes(_read(tar, f"dist/{name}"))
    # woff2 only: every engine we run on supports it, and the CSS lists it first,
    # so the woff/ttf fallbacks are never requested.
    for member in tar.getmembers():
        path = PurePosixPath(member.name)
        if member.isfile() and path.parent == PurePosixPath("package/dist/fonts") and path.suffix == ".woff2":
            (target / "fonts" / path.name).write_bytes(_read(tar, f"dist/fonts/{path.name}"))
    (target / "LICENSE").write_bytes(_license_text(tar))
    (target / "VERSION").write_text(meta["version"] + "\n", encoding="utf-8")


def _mermaid_install(tar: tarfile.TarFile, meta: dict) -> None:
    target = _fresh_vendor_dir("mermaid")
    (target / "mermaid.min.js").write_bytes(_read(tar, "dist/mermaid.min.js"))
    (target / "LICENSE").write_bytes(_license_text(tar))
    (target / "VERSION").write_text(meta["version"] + "\n", encoding="utf-8")


# package -> (current-version reader, installer)
PACKAGES: dict[str, tuple[Callable[[], str | None], Callable[[tarfile.TarFile, dict], None]]] = {
    **{
        name: (functools.partial(_style_current, name), functools.partial(_style_install, name))
        for name in STYLE_PACKAGES
    },
    "katex": (lambda: _vendor_current("katex"), _katex_install),
    "mermaid": (lambda: _vendor_current("mermaid"), _mermaid_install),
}


def update(package: str, version: str = "latest") -> str:
    """Vendor *package* at *version*; returns the resolved version."""
    _current, install = PACKAGES[package]
    meta = _metadata(package, version)
    with _verified_tarball(meta) as tar:
        install(tar, meta)
    return meta["version"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packages", nargs="*", metavar="PKG [VERSION]")
    parser.add_argument("--check", action="store_true", help="only report whether updates are available")
    args = parser.parse_args()

    if args.check:
        names = args.packages or list(PACKAGES)
        outdated = False
        for name in names:
            current, latest = PACKAGES[name][0](), _metadata(name, "latest")["version"]
            print(f"{name}: current {current}  latest {latest}")
            outdated |= current != latest
        return 1 if outdated else 0

    if len(args.packages) == 2 and args.packages[1] not in PACKAGES:
        targets = [(args.packages[0], args.packages[1])]
    else:
        targets = [(name, "latest") for name in (args.packages or PACKAGES)]
    for name, version in targets:
        if name not in PACKAGES:
            parser.error(f"unknown package {name!r}; choose from {', '.join(PACKAGES)}")
        before = PACKAGES[name][0]()
        print(f"{name}: {before} -> {update(name, version)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
