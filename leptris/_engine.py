"""Lifecycle for FFI-compiled language sources (XSLT, XQuery, and
future engines such as RelaxNG): encode, compile once through the
engine's parse entry, raise the engine's domain error with the
thread-local diagnostic, guard the live-document contract, and free
on GC."""

from __future__ import annotations

from . import _ffi
from .error import LeptrisError


class CompiledSource:
    """Compile-once base for engine objects.

    Subclasses declare the FFI seams as class attributes (open for
    extension) and implement their evaluation method; the lifecycle
    lives here exactly once.
    """

    __slots__ = ("_source", "_handle")

    _parse = None            # (bytes, length) -> handle, NULL on failure
    _free = None             # handle -> None
    _label = "source"        # e.g. "XSLT stylesheet"
    _error = LeptrisError    # the engine's domain error class

    def __init__(self, source):
        if isinstance(source, str):
            source = source.encode("utf-8")
        elif isinstance(source, (bytearray, memoryview)):
            source = bytes(source)
        if not isinstance(source, bytes):
            raise TypeError(f"expected {self._label} as str or bytes")
        self._source = source
        handle = self._parse(source, len(source))
        if handle == _ffi.ffi.NULL:
            raise self._error(self._compile_detail())
        self._handle = handle

    def _compile_detail(self) -> str:
        message = _ffi.lib.leptris_last_error()
        if message != _ffi.ffi.NULL:
            return _ffi.ffi.string(message).decode("utf-8", "replace")
        return f"{self._label} compilation failed"

    def _document(self, target):
        """Resolve a Document-or-Element argument and guard the
        live-document contract (evaluating against a closed
        document is a use-after-free)."""
        from .document import Document
        from .element import Element

        if isinstance(target, Element):
            target = target.document
        if not isinstance(target, Document):
            raise TypeError("expected an Element or Document")
        if target.closed:
            raise self._error("operation on a closed document")
        return target

    def __del__(self):
        handle = getattr(self, "_handle", None)
        if handle is not None and handle != _ffi.ffi.NULL:
            self._free(handle)
            self._handle = _ffi.ffi.NULL
