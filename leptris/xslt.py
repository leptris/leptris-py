"""XSLT 1.0 transformation — lxml's etree.XSLT shape.

Compile a stylesheet once, apply it to any number of documents:

    transform = leptris.XSLT(stylesheet_xml)
    result = transform(source_doc)          # -> Document
    leptris.tostring(result)

The engine ships the full XSLT 1.0 core plus EXSLT functions
(libleptris 1.9.1+); EXSLT registration is enabled on each result.
"""

from __future__ import annotations

from typing import Union

from . import _ffi
from .error import LeptrisError


class XSLT:
    """A compiled XSLT 1.0 stylesheet (lxml's etree.XSLT equivalent)."""

    def __init__(self, source: Union[str, bytes]):
        if isinstance(source, str):
            source = source.encode("utf-8")
        if not isinstance(source, (bytes, bytearray, memoryview)):
            raise TypeError("expected stylesheet XML as str or bytes")
        self._source = bytes(source)
        self._xslt = _ffi.lib.leptris_xslt_parse(self._source, len(self._source))
        if self._xslt == _ffi.ffi.NULL:
            message = _ffi.lib.leptris_last_error()
            detail = (
                _ffi.ffi.string(message).decode("utf-8", "replace")
                if message != _ffi.ffi.NULL
                else "stylesheet compilation failed"
            )
            raise LeptrisError(detail)

    def __call__(self, document, *, exslt: bool = True):
        """Apply to a Document (or an Element via its document)."""
        from .document import Document
        from .element import Element, _accel

        if isinstance(document, Element):
            document = document.document
        if not isinstance(document, Document):
            raise TypeError("expected an Element or Document")
        if document.closed:
            raise LeptrisError("operation on a closed document")
        if exslt:
            _ffi.lib.leptris_exslt_enable(document._cd())
        result = _ffi.lib.leptris_xslt_apply(self._xslt, document._cd())
        if result == _ffi.ffi.NULL:
            raise LeptrisError("XSLT transformation failed")
        registry = _accel.new_registry()
        doc = Document._from_parts(
            int(_ffi.ffi.cast("uintptr_t", result)), registry
        )
        _ffi.lib.leptris_document_root(result)
        return doc

    def __del__(self):
        try:
            if getattr(self, "_xslt", _ffi.ffi.NULL) != _ffi.ffi.NULL:
                _ffi.lib.leptris_xslt_free(self._xslt)
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"<XSLT {len(self._source)} bytes>"
