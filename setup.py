"""Build configuration: the C accelerator is a required component.

Wheels ship it compiled; building from sdist requires a C toolchain
(failure is an error, not a silent pure-Python fallback).
"""

from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "leptris._leptrisaccel",
            sources=["leptris/_leptrisaccel.c"],
            py_limited_api=True,
            define_macros=[("Py_LIMITED_API", "0x03090000")],
        )
    ],
    options={"bdist_wheel": {"py_limited_api": "cp39"}},
)
