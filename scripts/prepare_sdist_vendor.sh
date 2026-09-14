#!/usr/bin/env bash
# Prepare the sdist's bundled engine source: extract the PINNED
# libleptris release into vendor/libleptris (grafted into the sdist
# by MANIFEST.in). Never committed; binaries are never included —
# the source installs compile it via setup.py when no prebuilt
# wheel/vendored library serves the platform.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(cat libleptris-version.txt)
DEST=vendor/libleptris

rm -rf "$DEST"
mkdir -p "$DEST"
curl -sL "https://codeload.github.com/leptris/leptris/tar.gz/refs/tags/v${VERSION}" |
    tar xz --strip-components=1 -C "$DEST"
echo "prepared ${DEST}: libleptris v${VERSION} source"
