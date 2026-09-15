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

    def __call__(self, document_or_element: "Document | Element", *,
                 variables=None):
        """Evaluate; ``variables`` binds ``declare variable $name
        external`` prologs (values are XPath expressions, QT3
        select semantics — libleptris 1.9.144+)."""
        from . import _results
        from .element import Element

        element = (
            document_or_element
            if isinstance(document_or_element, Element)
            else None
        )
        document = self._document(document_or_element)
        context = element._cd() if element is not None else _ffi.ffi.NULL

        # TODO.native/22: one C call for the no-variables path
        # (eval + result conversion; the Python converter was 42%
        # of the row). Variables keep the cffi eval_params path.
        if not variables:
            from .element import _accel

            if _accel is not None:
                doc_addr = document._raw_addr
                if doc_addr is not None:
                    items = _accel.xquery_eval(
                        int(_ffi.ffi.cast("uintptr_t", self._handle)),
                        doc_addr,
                        element._raw if element is not None else 0,
                        document,
                    )
                    if items is not None:
                        return items
        if variables:
            keepalive = []
            name_ptrs = []
            select_ptrs = []
            for name, select in variables.items():
                name_b = name.encode("utf-8") if isinstance(name, str) else name
                select_b = (
                    select.encode("utf-8") if isinstance(select, str) else select
                )
                name_c = _ffi.ffi.new("char[]", name_b)
                select_c = _ffi.ffi.new("char[]", select_b)
                keepalive += [name_c, select_c]
                name_ptrs.append(name_c)
                select_ptrs.append(select_c)
            name_array = _ffi.ffi.new("char*[]", name_ptrs)
            select_array = _ffi.ffi.new("char*[]", select_ptrs)
            keepalive += [name_array, select_array]
            result = _ffi.lib.leptris_xquery_eval_params(
                self._handle, document._cd(), context,
                name_array, select_array, len(name_ptrs),
            )
        else:
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
        return _results.convert(document, result)
