"""XPath — XPath 1.0 evaluation with namespaces and variables.

Scalar results convert to native Python types. Nodeset results
yield Element lists; attribute and text node selections yield
plain strings (lxml returns its "smart" strings for those).
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from . import _ffi
from .error import XPathError

_CLARK = re.compile(r"\{([^}]*)\}")


def expand_clark_names(
    path: str, namespaces: Optional[Dict[str, str]] = None
) -> Tuple[str, Dict[str, str]]:
    """Translate {uri}local names into prefixed names, generating
    prefixes for URIs the caller did not bind.

    Returns (expression, {prefix: uri} for generated prefixes).
    """
    extra: Dict[str, str] = {}
    declared = namespaces or {}

    def replacement(match: "re.Match[str]") -> str:
        uri = match.group(1)
        for prefix, bound in declared.items():
            if bound == uri:
                return prefix + ":"
        prefix = f"ns{len(extra)}"
        extra[prefix] = uri
        return prefix + ":"

    return _CLARK.sub(replacement, path), extra


class _XPathEngine:
    @staticmethod
    def _convert(document, result):
        """Convert a live LeptrisXPathResult (nodeset or scalar)."""
        from .element import _make

        ffi = _ffi.ffi
        result_type = _ffi.lib.leptris_xpath_result_type(result)
        try:
            if result_type == _ffi.XPATH_NODESET:
                return _XPathEngine._nodeset(document, result)
            if result_type == _ffi.XPATH_NUMBER:
                return _ffi.lib.leptris_xpath_result_number(result)
            if result_type == _ffi.XPATH_STRING:
                ptr = _ffi.lib.leptris_xpath_result_string(result)
                if ptr == ffi.NULL:
                    return ""
                value = ffi.string(ptr).decode("utf-8")
                _ffi.lib.leptris_free_string(ptr)
                return value
            if result_type == _ffi.XPATH_BOOLEAN:
                return bool(_ffi.lib.leptris_xpath_result_boolean(result))
            return None
        finally:
            _ffi.lib.leptris_xpath_result_free(result)

    @staticmethod
    def evaluate(
        document,
        context_element,
        expression: str,
        *,
        namespaces: Optional[Dict[str, str]] = None,
        variables: Optional[dict] = None,
    ):
        ffi = _ffi.ffi
        if variables is None:
            from .element import _accel

            if _accel is not None and not document.closed:
                # All-C fast path: eval, batch fill and element
                # construction in one call. Returns None when the
                # expression failed or the nodeset is mixed — the
                # Python path below handles both faithfully.
                doc_raw = document._raw_addr
                ctx = None
                if context_element is not None:
                    raw = getattr(context_element, "_raw", None)
                    ctx = (
                        raw
                        if raw is not None and raw is not False
                        else int(ffi.cast(
                            "uintptr_t", context_element._ptr
                        ))
                    )
                if namespaces:
                    flat = []
                    for prefix, uri in namespaces.items():
                        flat.append(prefix)
                        flat.append(uri)
                    items = _accel.nodeset_ns(
                        doc_raw, ctx, expression, document, flat
                    )
                else:
                    items = _accel.nodeset(doc_raw, ctx, expression, document)
                if items is not None:
                    return items
        ns_set = ffi.NULL
        var_set = ffi.NULL
        result = ffi.NULL
        try:
            if namespaces:
                ns_set = _ffi.lib.leptris_xpath_ns_set_new()
                if ns_set == ffi.NULL:
                    raise XPathError("could not create namespace set")
                for prefix, uri in namespaces.items():
                    rc = _ffi.lib.leptris_xpath_ns_set_add(
                        ns_set, prefix.encode("utf-8"), uri.encode("utf-8")
                    )
                    if rc != 0:
                        raise XPathError(f"invalid namespace binding {prefix!r}")
            if variables:
                var_set = _ffi.lib.leptris_xpath_variable_set_new()
                if var_set == ffi.NULL:
                    raise XPathError("could not create variable set")
                for name, value in variables.items():
                    if isinstance(value, bool):
                        rc = _ffi.lib.leptris_xpath_variable_set_boolean(
                            var_set, name.encode("utf-8"), int(value)
                        )
                    elif isinstance(value, (int, float)):
                        rc = _ffi.lib.leptris_xpath_variable_set_number(
                            var_set, name.encode("utf-8"), float(value)
                        )
                    elif isinstance(value, str):
                        rc = _ffi.lib.leptris_xpath_variable_set_string(
                            var_set, name.encode("utf-8"), value.encode("utf-8")
                        )
                    else:
                        raise TypeError(
                            f"XPath variable {name!r} must be bool, int, float or str"
                        )
                    if rc != 0:
                        raise XPathError(f"could not bind variable {name!r}")

            ctx = context_element._cd() if context_element is not None else ffi.NULL
            encoded = expression.encode("utf-8")
            if var_set != ffi.NULL:
                result = _ffi.lib.leptris_xpath_eval_with_vars_context(
                    document._ptr, ctx, encoded, var_set
                )
            elif ns_set != ffi.NULL:
                result = _ffi.lib.leptris_xpath_eval_ns(
                    document._ptr, ctx, encoded, ns_set
                )
            else:
                result = _ffi.lib.leptris_xpath_eval(document._ptr, ctx, encoded)
            if result == ffi.NULL:
                message = _ffi.lib.leptris_document_last_error(document._ptr)
                detail = (
                    ffi.string(message).decode("utf-8", "replace")
                    if message != ffi.NULL
                    else expression
                )
                raise XPathError(f"XPath evaluation failed: {detail}")

            result_type = _ffi.lib.leptris_xpath_result_type(result)
            if result_type == _ffi.XPATH_NODESET:
                return _XPathEngine._nodeset(document, result)
            if result_type == _ffi.XPATH_NUMBER:
                return _ffi.lib.leptris_xpath_result_number(result)
            if result_type == _ffi.XPATH_STRING:
                ptr = _ffi.lib.leptris_xpath_result_string(result)
                if ptr == ffi.NULL:
                    return ""
                value = ffi.string(ptr).decode("utf-8")
                _ffi.lib.leptris_free_string(ptr)
                return value
            if result_type == _ffi.XPATH_BOOLEAN:
                return bool(_ffi.lib.leptris_xpath_result_boolean(result))
            return None
        finally:
            if result != ffi.NULL:
                _ffi.lib.leptris_xpath_result_free(result)
            if ns_set != ffi.NULL:
                _ffi.lib.leptris_xpath_ns_set_free(ns_set)
            if var_set != ffi.NULL:
                _ffi.lib.leptris_xpath_variable_set_free(var_set)

    @staticmethod
    def _nodeset(document, result) -> list:
        from .element import Element

        lib = _ffi.lib
        ffi = _ffi.ffi
        count = lib.leptris_xpath_result_count(result)
        if count == 0:
            return []
        # Fast path: one batch call fills the array when every node in
        # the result is an element; mixed nodesets return copied <
        # count and take the per-index path (strings for non-element
        # slots, which result_get reports as NULL).
        buffer = ffi.new("LeptrisElement[]", count)
        copied = lib.leptris_xpath_result_get_nodes(result, buffer, count)
        if copied == count:
            from .element import _materialize

            return _materialize(buffer, document)
        from .element import _make

        items = []
        append = items.append
        for index in range(count):
            ptr = lib.leptris_xpath_result_get(result, index)
            if ptr != ffi.NULL:
                append(_make(ptr, document))
            else:
                value = lib.leptris_xpath_result_node_value(result, index)
                append(ffi.string(value).decode("utf-8") if value != ffi.NULL else "")
        return items

class XPath:
    """Precompiled XPath expression (lxml's etree.XPath equivalent).

    Compile once, evaluate many times:

        query = leptris.XPath("count(//book)")
        query(root)
    """

    def __init__(self, expression: str):
        self._expression = expression
        self._compiled = _ffi.lib.leptris_xpath_compile(
            expression.encode("utf-8")
        )
        if self._compiled == _ffi.ffi.NULL:
            raise XPathError(f"XPath compilation failed: {expression!r}")

    @property
    def expression(self) -> str:
        return self._expression

    def __call__(self, element_or_document, *, namespaces=None):
        from .document import Document
        from .element import Element

        if isinstance(element_or_document, Element):
            element = element_or_document
            document = element.document
        elif isinstance(element_or_document, Document):
            element, document = None, element_or_document
        else:
            raise TypeError("expected an Element or Document")
        if document.closed:
            raise XPathError("document is closed")
        context = element._cd() if element is not None else _ffi.ffi.NULL
        if namespaces:
            ns_set = _ffi.lib.leptris_xpath_ns_set_new()
            if ns_set == _ffi.ffi.NULL:
                raise XPathError("could not create namespace set")
            try:
                for prefix, uri in namespaces.items():
                    rc = _ffi.lib.leptris_xpath_ns_set_add(
                        ns_set, prefix.encode("utf-8"), uri.encode("utf-8")
                    )
                    if rc != 0:
                        raise XPathError(f"invalid namespace binding {prefix!r}")
                result = _ffi.lib.leptris_xpath_compiled_eval_ns(
                    self._compiled, document._ptr, context, ns_set
                )
            finally:
                _ffi.lib.leptris_xpath_ns_set_free(ns_set)
        else:
            result = _ffi.lib.leptris_xpath_compiled_eval(
                self._compiled, document._ptr, context
            )
        if result == _ffi.ffi.NULL:
            raise XPathError(f"XPath evaluation failed: {self._expression!r}")
        return _XPathEngine._convert(document, result)

    def __del__(self):
        try:
            if getattr(self, "_compiled", _ffi.ffi.NULL) != _ffi.ffi.NULL:
                _ffi.lib.leptris_xpath_compiled_free(self._compiled)
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"<XPath {self._expression!r}>"

