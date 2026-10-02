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

    def __call__(self, document, *, exslt: bool = True,
                 params=None, string_params=None):
        """Apply to a Document (or an Element via its document).

        ``params`` (libleptris 1.9.287+) binds top-level ``xsl:param``
        values before the stylesheet's globals run (XSLT §11.4) — a
        dict of ``{name: xpath-expression}``; each value is an XPath
        expression evaluated with the source document as context
        (pre-quote string literals: ``{"x": "'text'"}``, the libxslt
        convention). Returns a Document.

        ``string_params`` takes the same expression values but
        returns the SERIALIZED result (``str``) — the engine's
        string-apply contract (top-level text nodes preserved).
        ``params`` and ``string_params`` are mutually exclusive.
        """
        from .element import _accel

        if params and string_params:
            raise TypeError(
                "params and string_params are mutually exclusive; "
                "pre-quote string literals in params instead"
            )
        document = self._document(document)
        if exslt:
            _ffi.lib.leptris_exslt_enable(document._cd())
        ffi = _ffi.ffi
        if params or string_params:
            def pairs(d):
                flat = []
                for name, value in (d or {}).items():
                    if not isinstance(name, str) or not name:
                        raise ValueError(
                            "param names must be non-empty str"
                        )
                    flat.append(name.encode("utf-8"))
                    flat.append(str(value).encode("utf-8"))
                arr = ffi.new("char*[]", max(len(flat), 1))
                for i, item in enumerate(flat):
                    slot = ffi.new("char[]", item)
                    keepalive.append(slot)
                    arr[i] = slot
                return arr, len(flat) // 2
            keepalive = []
            if params:
                arr, count = pairs(params)
                keepalive.append(arr)
                result = _ffi.lib.leptris_xslt_apply_params(
                    self._handle, document._cd(), arr, count
                )
                if result == ffi.NULL:
                    raise XSLTError("XSLT transformation failed")
                registry = _accel.new_registry()
                doc = Document._from_parts(
                    int(ffi.cast("uintptr_t", result)), registry
                )
                _ffi.lib.leptris_document_root(result)
                return doc
            arr, count = pairs(string_params)
            keepalive.append(arr)
            text = _ffi.lib.leptris_xslt_apply_string_params(
                self._handle, document._cd(), arr, count
            )
            if text == ffi.NULL:
                raise XSLTError("XSLT transformation failed")
            out = ffi.string(text).decode("utf-8")
            _ffi.lib.leptris_free_string(text)
            return out
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
