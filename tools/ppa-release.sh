#!/bin/bash
# Release the current version to ppa:tecktron-studios/xfce-md-viewer.
#
#   tools/ppa-release.sh            stamp today's date, commit, tag, build the
#                                   signed source package, lintian, upload (asks)
#   tools/ppa-release.sh --dry-run  checks + unsigned source build + lintian only;
#                                   changes nothing in the repo, uploads nothing
#
# Before running: the new version is already in src/md_viewer/__init__.py, the
# top debian/changelog entry and a metainfo <release>, and committed on main.
# The script uploads for noble only; copy the package to the other series on
# Launchpad afterwards (printed at the end). Pushing is left to you.

set -euo pipefail

PPA="ppa:tecktron-studios/xfce-md-viewer"
PPA_URL="https://launchpad.net/~tecktron-studios/+archive/ubuntu/xfce-md-viewer"
SERIES="noble"
MAINTAINER="Tecktron Studios <software@tecktron.net>"
SIGNING_KEY="software@tecktron.net"
METAINFO="data/net.tecktron.md_viewer.metainfo.xml"

DRY_RUN=0
case "${1:-}" in
    "") ;;
    --dry-run) DRY_RUN=1 ;;
    *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."
ROOT=$(pwd)

step() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# --- Checks -------------------------------------------------------------------
step "Checking the repository"

[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || die "not on main"
if [ -n "$(git status --porcelain)" ]; then
    [ "$DRY_RUN" -eq 1 ] || die "working tree not clean (commit or stash first)"
    echo "Warning: uncommitted changes are not part of the build (it uses HEAD)"
fi

VERSION=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/md_viewer/__init__.py)
CHANGELOG_VERSION=$(dpkg-parsechangelog -S Version)
DISTRIBUTION=$(dpkg-parsechangelog -S Distribution)
CHANGELOG_MAINTAINER=$(dpkg-parsechangelog -S Maintainer)
[ -n "$VERSION" ] || die "no __version__ in src/md_viewer/__init__.py"
[ "$CHANGELOG_VERSION" = "$VERSION" ] || die "debian/changelog is $CHANGELOG_VERSION, __init__.py is $VERSION"
grep -q "<release version=\"$VERSION\"" "$METAINFO" || die "no <release version=\"$VERSION\"> in $METAINFO"
[ "$DISTRIBUTION" = "$SERIES" ] || die "debian/changelog distribution is $DISTRIBUTION, expected $SERIES"
[ "$CHANGELOG_MAINTAINER" = "$MAINTAINER" ] || die "debian/changelog maintainer is '$CHANGELOG_MAINTAINER', expected '$MAINTAINER'"
echo "Version $VERSION for $SERIES"

TAG_COMMIT=$(git rev-parse -q --verify "refs/tags/$VERSION^{commit}" || true)
if [ -n "$TAG_COMMIT" ] && [ "$TAG_COMMIT" != "$(git rev-parse HEAD)" ]; then
    die "tag $VERSION already exists on another commit; bump the version for a new release"
fi

if [ "$DRY_RUN" -eq 0 ]; then
    gpg --list-secret-keys "$SIGNING_KEY" >/dev/null 2>&1 || die "no secret GPG key for $SIGNING_KEY"
fi

step "Lint and tests"
venv/bin/ruff check -q src/ tests/ tools/
venv/bin/ruff format --check -q src/ tests/ tools/
/usr/bin/python3 -m pytest -q -p no:cacheprovider

step "Metadata"
appstreamcli validate --no-net "$METAINFO"
desktop-file-validate data/net.tecktron.md_viewer.desktop
echo "desktop file OK"

# --- Stamp the release date, commit, tag --------------------------------------
if [ "$DRY_RUN" -eq 0 ] && [ -z "$TAG_COMMIT" ]; then
    step "Stamping today's date, committing and tagging $VERSION"
    # Only the top changelog entry's trailer line (the first " -- " line).
    sed -i "0,/^ -- .*/s//\ -- $MAINTAINER  $(LC_ALL=C date -R)/" debian/changelog
    sed -i "s/<release version=\"$VERSION\" date=\"[0-9-]*\"/<release version=\"$VERSION\" date=\"$(date +%F)\"/" "$METAINFO"
    if [ -n "$(git status --porcelain)" ]; then
        git add debian/changelog "$METAINFO"
        git commit -q -m "Release $VERSION"
    fi
    git tag -a "$VERSION" -m "xfce-md-viewer $VERSION"
    echo "Tagged $VERSION at $(git rev-parse --short HEAD)"
fi

# --- Build the source package from the committed tree -------------------------
# git archive, not the working directory: dpkg-source packs everything it finds.
BUILD_DIR="$ROOT/build/ppa"
SRC_DIR="$BUILD_DIR/xfce-md-viewer-$VERSION"
step "Building the source package in build/ppa/"
rm -rf "$BUILD_DIR"
mkdir -p "$SRC_DIR"
git archive HEAD | tar -x -C "$SRC_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
    SIGN_ARGS=(-us -uc)
else
    SIGN_ARGS=("-k$SIGNING_KEY")
fi
(cd "$SRC_DIR" && debuild --no-lintian -S -sa "${SIGN_ARGS[@]}")

CHANGES="$BUILD_DIR/xfce-md-viewer_${VERSION}_source.changes"
[ -f "$CHANGES" ] || die "build produced no $CHANGES"

step "lintian"
LINTIAN_OUT=$(lintian --pedantic "$CHANGES" || true)
[ -n "$LINTIAN_OUT" ] && echo "$LINTIAN_OUT"
if grep -q '^E:' <<<"$LINTIAN_OUT"; then
    die "lintian reported errors"
fi

if [ "$DRY_RUN" -eq 1 ]; then
    step "Dry run complete: $CHANGES (unsigned, not uploaded)"
    exit 0
fi

# --- Upload -------------------------------------------------------------------
step "Upload"
read -r -p "Upload xfce-md-viewer $VERSION to $PPA ($SERIES)? [y/N] " answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    echo "Not uploaded. To upload later: dput $PPA $CHANGES"
    exit 0
fi
dput "$PPA" "$CHANGES"

cat <<EOF

Uploaded. Remaining steps:
  1. Push:            git push origin main && git push origin $VERSION
  2. GitHub release:  publish release $VERSION (build-deb.yml attaches the .deb)
  3. Other series:    when the $SERIES build succeeds, open
                      $PPA_URL/+copy-packages
                      and copy xfce-md-viewer $VERSION to resolute and stonking
                      ("Copy existing binaries").
EOF
