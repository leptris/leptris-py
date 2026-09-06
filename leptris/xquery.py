"""XQuery 1.0 core: compile once, evaluate many (libleptris 1.9.64+)."""

from . import _engine, _ffi
from .error import XQueryError


class XQuery(_engine.CompiledSource):
    """Precompiled XQuery query.

    Supports the XQuery 1.0 core shipped by libleptris: FLWOR
    expressions (for/let/where/order by/return, positional ``at``),
    the prolog (declare variable/namespace, declare function
    local:*), and try/catch expressions.

    Results follow the binding's XPath conventions: element
    sequences wrap as Element, scalar FLWOR items and constructed
    values come back as plain str/float/bool.
    """

    _parse = _ffi.lib.leptris_xquery_parse
    _free = _ffi.lib.leptris_xquery_free
    _label = "XQuery query"
    _error = XQueryError

    def __call__(self, document_or_element: "Document | Element"):
        from .element import Element
        from .xpath import _XPathEngine

        element = (
            document_or_element
            if isinstance(document_or_element, Element)
            else None
        )
        document = self._document(document_or_element)
        context = element._cd() if element is not None else _ffi.ffi.NULL

        result = _ffi.lib.leptris_xquery_eval(
            self._handle, document._cd(), context
        )
        if result == _ffi.ffi.NULL:
            message = _ffi.lib.leptris_document_last_error(document._cd())
            detail = (
                _ffi.ffi.string(message).decode("utf-8", "replace")
                if message != _ffi.ffi.NULL
                else "query evaluation failed"
            )
            raise XQueryError(f"XQuery evaluation failed: {detail}")
        return _XPathEngine._convert(document, result)
