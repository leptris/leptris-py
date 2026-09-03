"""XQuery 1.0 core: compile once, evaluate many (libleptris 1.9.64+)."""

from . import _ffi
from .error import LeptrisError


class XQuery:
    """Precompiled XQuery query.

    Supports the XQuery 1.0 core shipped by libleptris: FLWOR
    expressions (for/let/where/order by/return, positional ``at``),
    the prolog (declare variable/namespace, declare function
    local:*), and try/catch expressions.

    Results follow the binding's XPath conventions: element
    sequences wrap as Element, scalar FLWOR items and constructed
    values come back as plain str/float/bool.
    """

    __slots__ = ("_query",)

    def __init__(self, query: str):
        if isinstance(query, bytes):
            query = query.decode("utf-8")
        qb = query.encode("utf-8")
        self._query = _ffi.lib.leptris_xquery_parse(qb, len(qb))
        if self._query == _ffi.ffi.NULL:
            message = _ffi.lib.leptris_last_error()
            detail = (
                _ffi.ffi.string(message).decode("utf-8", "replace")
                if message != _ffi.ffi.NULL
                else "query compilation failed"
            )
            raise LeptrisError(detail)

    def __call__(self, document_or_element):
        from .document import Document
        from .xpath import _XPathEngine

        if isinstance(document_or_element, Document):
            document = document_or_element
            context = _ffi.ffi.NULL
        else:
            element = document_or_element
            document = element._document
            context = element._cd()

        result = _ffi.lib.leptris_xquery_eval(
            self._query, document._cd(), context
        )
        if result == _ffi.ffi.NULL:
            message = _ffi.lib.leptris_document_last_error(document._cd())
            detail = (
                _ffi.ffi.string(message).decode("utf-8", "replace")
                if message != _ffi.ffi.NULL
                else "query evaluation failed"
            )
            raise LeptrisError(f"XQuery evaluation failed: {detail}")
        return _XPathEngine._convert(document, result)

    def __del__(self):
        if getattr(self, "_query", None) is not None and self._query != _ffi.ffi.NULL:
            _ffi.lib.leptris_xquery_free(self._query)
            self._query = _ffi.ffi.NULL
