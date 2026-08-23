"""Build configuration for the optional C accelerator.

The accelerator is a limited-API (abi3) extension: one wheel per
platform serves every supported CPython. When compilation is
impossible (no toolchain), the build degrades to the pure-Python
wheel and leptris runs in pure mode.
"""

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext


class OptionalBuildExt(build_ext):
    def run(self):
        try:
            super().run()
        except Exception as error:  # noqa: BLE001 - degrade to pure wheel
            self.warn(f"skipping leptris._leptrisaccel: {error}")

    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception as error:  # noqa: BLE001
            self.warn(f"skipping leptris._leptrisaccel: {error}")


setup(
    ext_modules=[
        Extension(
            "leptris._leptrisaccel",
            sources=["leptris/_leptrisaccel.c"],
            py_limited_api=True,
            define_macros=[("Py_LIMITED_API", "0x03090000")],
        )
    ],
    cmdclass={"build_ext": OptionalBuildExt},
    options={"bdist_wheel": {"py_limited_api": "cp39"}},
)
