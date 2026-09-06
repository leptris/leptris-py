"""XSLT 1.0 transformation — lxml's etree.XSLT shape.

Compile a stylesheet once, apply it to any number of documents:

    transform = leptris.XSLT(stylesheet_xml)
    result = transform(source_doc)          # -> Document
    leptris.tostring(result)

The engine ships the full XSLT 1.0 core plus EXSLT functions
(libleptris 1.9.1+); EXSLT registration is enabled on each result.
"""

from __future__ import annotations

from . import _engine, _ffi
from .document import Document
from .error import XSLTError


class XSLT(_engine.CompiledSource):
    """A compiled XSLT 1.0 stylesheet (lxml's etree.XSLT equivalent)."""

    _parse = _ffi.lib.leptris_xslt_parse
    _free = _ffi.lib.leptris_xslt_free
    _label = "XSLT stylesheet"
    _error = XSLTError

    def __call__(self, document, *, exslt: bool = True) -> Document:
        """Apply to a Document (or an Element via its document)."""
        from .element import _accel

        document = self._document(document)
        if exslt:
            _ffi.lib.leptris_exslt_enable(document._cd())
        result = _ffi.lib.leptris_xslt_apply(self._handle, document._cd())
        if result == _ffi.ffi.NULL:
            raise XSLTError("XSLT transformation failed")
        registry = _accel.new_registry()
        doc = Document._from_parts(
            int(_ffi.ffi.cast("uintptr_t", result)), registry
        )
        _ffi.lib.leptris_document_root(result)
        return doc

    def __repr__(self) -> str:
        return f"<XSLT {len(self._source)} bytes>"
