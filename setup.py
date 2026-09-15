"""Build configuration: the C accelerator is a required component.

Wheels ship it compiled; building from sdist requires a C toolchain
(failure is an error, not a silent pure-Python fallback).

Zero-setup for source installs: the sdist bundles the pinned
libleptris source under vendor/libleptris/. When no vendored library
is present and LEPTRIS_LIB_PATH is not set, the engine is compiled
here into leptris/_vendor/ before the accelerator builds — a source
install already needs a compiler, so no new prerequisite class.
"""

import os
import shutil
import subprocess
import sys
import sysconfig

from setuptools import Extension, setup
from setuptools.command.build import build


def _vendored_library():
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("libleptris.dylib", "libleptris.so", "leptris.dll"):
        path = os.path.join(here, "leptris", "_vendor", name)
        if os.path.exists(path):
            return path
    return None


def _build_bundled_engine():
    """cmake-build vendor/libleptris into leptris/_vendor/."""
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "vendor", "libleptris")
    if not os.path.isfile(os.path.join(src, "CMakeLists.txt")):
        return
    build = os.path.join(here, "build", "vendor-libleptris")
    subprocess.run(
        [
            "cmake", "-S", src, "-B", build,
            "-DCMAKE_BUILD_TYPE=Release",
            "-DLEPTRIS_BUILD_SHARED=ON",
            "-DLEPTRIS_BUILD_STATIC=OFF",
            "-DBUILD_TESTING=OFF",
            "-DLEPTRIS_BUILD_CLI=OFF",
            "-DLEPTRIS_BUILD_BENCHMARKS=OFF",
            "-DLEPTRIS_ENABLE_UTF8PROC=OFF",
            "-DLEPTRIS_ENABLE_ICONV=OFF",
        ],
        check=True,
    )
    subprocess.run(
        ["cmake", "--build", build, "--config", "Release"], check=True
    )
    for root, _dirs, files in os.walk(build):
        for name in files:
            if name in ("libleptris.dylib", "libleptris.so",
                        "libleptris.dll", "leptris.dll"):
                os.makedirs(
                    os.path.join(here, "leptris", "_vendor"), exist_ok=True
                )
                shutil.copy2(
                    os.path.join(root, name),
                    os.path.join(
                        here, "leptris", "_vendor",
                        "libleptris.dylib" if name.endswith(".dylib")
                        else "leptris.dll" if name.endswith(".dll")
                        else "libleptris.so",
                    ),
                )
                return
    print(
        "leptris: bundled engine source present but no shared library "
        "was produced; set LEPTRIS_LIB_PATH to point at your own build",
        file=sys.stderr,
    )


class build_with_engine(build):
    """The engine must be compiled BEFORE build_py: package_data
    (leptris/_vendor/*) is copied when build_py runs, which precedes
    build_ext in the default command order."""

    def run(self):
        if _vendored_library() is None and not os.environ.get(
            "LEPTRIS_LIB_PATH"
        ):
            _build_bundled_engine()
        super().run()


# Free-threaded builds (the cpXXt wheels) are version-specific:
# Py_GIL_DISABLED + the 3.9 limited API are mutually exclusive.
# Detection needs three signals because no single one is portable:
# sysconfig Py_GIL_DISABLED (some builds), sys.abiflags 't'
# (Unix-only), and the EXT_SUFFIX 'cpXXt' marker (every platform —
# e.g. '.cp314t-win_amd64.pyd').
import re as _re

FREE_THREADED = (
    sysconfig.get_config_var("Py_GIL_DISABLED") == "1"
    or "t" in (getattr(sys, "abiflags", "") or "")
    or _re.search(r"3\d+t", sysconfig.get_config_var("EXT_SUFFIX") or "")
    is not None
)

if FREE_THREADED:
    ext_kwargs = dict(
        define_macros=[("Py_GIL_DISABLED", "1")],
    )
    bdist_options = {}
else:
    ext_kwargs = dict(
        py_limited_api=True,
        define_macros=[("Py_LIMITED_API", "0x03090000")],
    )
    bdist_options = {"bdist_wheel": {"py_limited_api": "cp39"}}

setup(
    cmdclass={"build": build_with_engine},
    ext_modules=[
        Extension(
            "leptris._leptrisaccel",
            sources=["leptris/_leptrisaccel.c"],
            **ext_kwargs,
        )
    ],
    options=bdist_options,
)
