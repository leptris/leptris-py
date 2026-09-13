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

CMAKE_FLAGS=(-DCMAKE_BUILD_TYPE=Release
    -DLEPTRIS_BUILD_SHARED=ON -DLEPTRIS_BUILD_STATIC=OFF
    -DBUILD_TESTING=OFF -DLEPTRIS_BUILD_CLI=OFF
    -DLEPTRIS_BUILD_BENCHMARKS=OFF
    -DLEPTRIS_ENABLE_UTF8PROC=OFF -DLEPTRIS_ENABLE_ICONV=OFF)

find_lib() {
    find "$1" -type f \
        \( -name 'libleptris.1*.dylib' -o -name 'libleptris.so.1*' -o \
           -name 'libleptris.so' -o -name '*leptris.dll' \) | sort | tail -1
}

if [ "$(uname -s)" = "Darwin" ]; then
    # macOS needs ONE universal2 dylib: cibuildwheel tests the
    # x86_64 wheel under Rosetta on an arm64 runner. The engine's
    # SIMD dispatch keys on the HOST processor, so each slice gets
    # its own cmake run — the x86_64 run must preset the platform
    # triple to select the AVX2 path (NEON TUs do not compile for
    # x86_64).
    for arch in arm64 x86_64; do
        flags=("${CMAKE_FLAGS[@]}" "-DCMAKE_OSX_ARCHITECTURES=$arch")
        if [ "$arch" = "x86_64" ]; then
            flags+=(-DCMAKE_SYSTEM_NAME=Darwin -DCMAKE_SYSTEM_PROCESSOR=x86_64)
        fi
        cmake -S "$SRC" -B "$SRC/build-$arch" "${flags[@]}"
        cmake --build "$SRC/build-$arch" --config Release
    done
    lipo -create \
        "$(find_lib "$SRC/build-arm64")" \
        "$(find_lib "$SRC/build-x86_64")" \
        -output "$VENDOR/libleptris.dylib"
    echo "vendored: $VENDOR/libleptris.dylib (universal2, libleptris v${VERSION})"
    exit 0
fi

cmake -S "$SRC" -B "$SRC/build" "${CMAKE_FLAGS[@]}"
cmake --build "$SRC/build" --config Release

lib=$(find_lib "$SRC/build")
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
