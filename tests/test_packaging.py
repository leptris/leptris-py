"""Packaging doctrine: compiled packages carry the engine binary AND
its source; source installs compile it automatically.

The full gate runs in the release workflow against every artifact
pre-upload; this checks the installed layout when a vendored build
is present (wheel installs and source installs both vendor; dev
checkouts with LEPTRIS_LIB_PATH skip).
"""

import os

import pytest

import leptris

VENDOR = os.path.join(os.path.dirname(leptris.__file__), "_vendor")


@pytest.mark.skipif(
    not os.path.isdir(VENDOR), reason="no vendored engine (LEPTRIS_LIB_PATH dev build)"
)
class TestVendoredLayout:
    def test_engine_binary_present(self):
        assert any(
            os.path.isfile(os.path.join(VENDOR, n))
            for n in ("libleptris.so", "libleptris.dylib", "leptris.dll")
        )

    def test_engine_source_present(self):
        assert os.path.isfile(
            os.path.join(VENDOR, "engine", "CMakeLists.txt")
        )
        assert os.path.isdir(os.path.join(VENDOR, "engine", "src"))

    def test_rebuild_notes_present(self):
        assert os.path.isfile(os.path.join(VENDOR, "README.md"))
