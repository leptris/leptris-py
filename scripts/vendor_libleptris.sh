#!/usr/bin/env bash
# Build the pinned libleptris release and vendor the shared library
# into leptris/_vendor/ so wheels bundle our compiled engine. Runs
# per wheel target inside cibuildwheel (CIBW_BEFORE_ALL) on every
# platform; also usable locally: bash scripts/vendor_libleptris.sh
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(cat libleptris-version.txt)
SRC=tmp/vendor-libleptris
VENDOR=leptris/_vendor

rm -rf "$SRC" "$VENDOR"
mkdir -p "$SRC" "$VENDOR"
curl -sL "https://codeload.github.com/leptris/leptris/tar.gz/refs/tags/v${VERSION}" |
    tar xz --strip-components=1 -C "$SRC"

cmake -S "$SRC" -B "$SRC/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DLEPTRIS_BUILD_SHARED=ON -DLEPTRIS_BUILD_STATIC=OFF \
    -DBUILD_TESTING=OFF -DLEPTRIS_BUILD_CLI=OFF \
    -DLEPTRIS_BUILD_BENCHMARKS=OFF \
    -DLEPTRIS_ENABLE_UTF8PROC=OFF -DLEPTRIS_ENABLE_ICONV=OFF
cmake --build "$SRC/build" --config Release

lib=$(find "$SRC/build" -type f \
    \( -name 'libleptris*.dylib' -o -name 'libleptris*.so*' -o -name '*leptris.dll' \) |
    sort | tail -1)
if [ -z "$lib" ]; then
    echo "vendor_libleptris: shared library not found in build tree" >&2
    exit 1
fi

case "$lib" in
    *.dylib)  dest="$VENDOR/libleptris.dylib" ;;
    *.so*)    dest="$VENDOR/libleptris.so" ;;
    *.dll)    dest="$VENDOR/leptris.dll" ;;
esac
cp "$lib" "$dest"
echo "vendored: $dest ($(basename "$lib"), libleptris v${VERSION})"
