"""XPath — XPath evaluation with namespaces and variables.

The engine evaluates the full 3.1 grammar by default; pass
version="1.0" anywhere an expression is accepted to pin the
strict XPath 1.0 surface (3.x-only syntax raises XPathError).

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

_XPATH_VERSIONS = {
    "1.0": _ffi.lib.LEPTRIS_XPATH_10,
    "3.1": _ffi.lib.LEPTRIS_XPATH_31,
}


def _version_flag(version):
    """Map a version string to the engine flag (None = default
    full surface); validated once at the boundary."""
    if version is None:
        return None
    try:
        return _XPATH_VERSIONS[version]
    except KeyError:
        valid = ", ".join(sorted(_XPATH_VERSIONS))
        raise ValueError(
            f"unknown XPath version {version!r}; expected one of: {valid}"
        ) from None


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


def _vars_flat(variables):
    """Flatten a variables dict to the accelerator's [name, tag,
    value, ...] encoding (the compiled-XPath contract; TypeError on
    unsupported value types)."""
    flat = []
    for name, value in variables.items():
        if isinstance(value, bool):
            flat.extend((name, 0, value))
        elif isinstance(value, (int, float)):
            flat.extend((name, 1, value))
        elif isinstance(value, str):
            flat.extend((name, 2, value))
        else:
            raise TypeError(
                f"XPath variable {name!r} must be bool, int, float or str"
            )
    return flat


def _c_evaluate_vars(document, context_element, expression, variables):
    """One C call for the plain variables path (TODO.native/11):
    bind + evaluate + convert, mirroring the no-variables fast
    path. Returns None when the C path is unsuitable — callers
    fall back to the engine path."""
    from .element import _accel

    if _accel is None or document.closed:
        return None
    doc_addr = document._raw_addr
    if doc_addr is None:
        return None
    context_addr = (
        context_element._raw if context_element is not None else 0
    )
    return _accel.nodeset_vars(
        doc_addr, context_addr, expression, document,
        _vars_flat(variables),
    )


def _c_evaluate(document, context_element, expression, namespaces):
    """The single bridge from Python query entry points to all-C
    evaluation (eval, batch fill, element construction in one call).

    Returns the converted result, or None when the C path is
    unavailable or unsuitable (unbound accelerator, closed document,
    failed evaluation, mixed nodeset) — callers fall back to the
    engine path, which handles those faithfully.
    """
    from .element import _accel

    if _accel is None or document.closed:
        return None
    ctx = (
        context_element._raw
        if context_element is not None
        else None
    )
    if namespaces:
        flat = [v for pair in namespaces.items() for v in pair]
        return _accel.nodeset_ns(
            document._raw_addr, ctx, expression, document, flat
        )
    return _accel.nodeset(
        document._raw_addr, ctx, expression, document
    )


class _XPathEngine:
    def _convert(document, result):
        from . import _results

        return _results.convert(document, result)

    @staticmethod
    def evaluate(
        document,
        context_element,
        expression: str,
        *,
        namespaces: Optional[Dict[str, str]] = None,
        variables: Optional[dict] = None,
        version: Optional[str] = None,
    ):
        ffi = _ffi.ffi
        version_flag = _version_flag(version)
        if version_flag is not None:
            if namespaces or variables:
                raise ValueError(
                    "versioned evaluation does not accept namespaces or "
                    "variables yet (engine gap); use the default surface "
                    "for those calls"
                )
            ctx = (
                context_element._cd()
                if context_element is not None
                else ffi.NULL
            )
            status = ffi.new("LeptrisStatus*")
            result = _ffi.lib.leptris_xpath_eval_versioned(
                document._cd(), ctx, expression.encode("utf-8"),
                version_flag, status,
            )
            if result == ffi.NULL:
                message = _ffi.lib.leptris_document_last_error(
                    document._cd()
                )
                detail = (
                    ffi.string(message).decode("utf-8", "replace")
                    if message != ffi.NULL
                    else f"status {int(status[0])}"
                )
                raise XPathError(
                    f"XPath {version} evaluation failed: {detail}"
                )
            try:
                return _XPathEngine._convert(document, result)
            finally:
                _ffi.lib.leptris_xpath_result_free(result)
        if variables is None:
            items = _c_evaluate(
                document, context_element, expression, namespaces
            )
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
                    document._cd(), ctx, encoded, var_set
                )
            elif ns_set != ffi.NULL:
                result = _ffi.lib.leptris_xpath_eval_ns(
                    document._cd(), ctx, encoded, ns_set
                )
            else:
                result = _ffi.lib.leptris_xpath_eval(document._cd(), ctx, encoded)
            if result == ffi.NULL:
                message = _ffi.lib.leptris_document_last_error(document._cd())
                detail = (
                    ffi.string(message).decode("utf-8", "replace")
                    if message != ffi.NULL
                    else expression
                )
                raise XPathError(f"XPath evaluation failed: {detail}")

            return _XPathEngine._convert(document, result)
        finally:
            if result != ffi.NULL:
                _ffi.lib.leptris_xpath_result_free(result)
            if ns_set != ffi.NULL:
                _ffi.lib.leptris_xpath_ns_set_free(ns_set)
            if var_set != ffi.NULL:
                _ffi.lib.leptris_xpath_variable_set_free(var_set)

class XPath:
    """Precompiled XPath expression (lxml's etree.XPath equivalent).

    Compile once, evaluate many times:

        query = leptris.XPath("count(//book)")
        query(root)

    version="1.0" pins the strict XPath 1.0 surface (evaluation
    then runs through the engine's versioned entry; 3.x-only
    syntax raises XPathError). Default: the full 3.1 grammar.
    """

    def __init__(self, expression: str, *, version: Optional[str] = None):
        self._expression = expression
        self._version = version
        _version_flag(version)  # validate at construction
        self._compiled = _ffi.lib.leptris_xpath_compile(
            expression.encode("utf-8")
        )
        if self._compiled == _ffi.ffi.NULL:
            raise XPathError(f"XPath compilation failed: {expression!r}")
        self._compiled_addr = int(
            _ffi.ffi.cast("uintptr_t", self._compiled)
        )

    @property
    def expression(self) -> str:
        return self._expression

    def __call__(self, element_or_document, *, namespaces=None, variables=None):
        from .document import Document
        from .element import Element, _accel

        if isinstance(element_or_document, Element):
            element = element_or_document
            document = element.document
        elif isinstance(element_or_document, Document):
            element, document = None, element_or_document
        else:
            raise TypeError("expected an Element or Document")
        if document.closed:
            raise XPathError("document is closed")
        if self._version is not None:
            return _XPathEngine.evaluate(
                document, element, self._expression,
                namespaces=namespaces, variables=variables,
                version=self._version,
            )
        # All-C fast path: eval + result conversion in one call. None
        # falls back to the engine path below (mixed nodeset, eval
        # failure, ns+vars combined, or a borrowed document without
        # a raw address).
        doc_addr = document._raw_addr
        if doc_addr is not None:
            context_addr = element._raw if element is not None else 0
            flat = (
                [v for pair in namespaces.items() for v in pair]
                if namespaces
                else None
            )
            vars_flat = None
            if variables:
                vars_flat = []
                for name, value in variables.items():
                    if isinstance(value, bool):
                        vars_flat.extend((name, 0, value))
                    elif isinstance(value, (int, float)):
                        vars_flat.extend((name, 1, value))
                    elif isinstance(value, str):
                        vars_flat.extend((name, 2, value))
                    else:
                        raise TypeError(
                            f"XPath variable {name!r} must be bool, "
                            "int, float or str"
                        )
            items = _accel.compiled_eval(
                self._compiled_addr, doc_addr, context_addr, document, flat,
                vars_flat
            )
            if items is not None:
                return items
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
                    self._compiled, document._cd(), context, ns_set
                )
            finally:
                _ffi.lib.leptris_xpath_ns_set_free(ns_set)
        else:
            result = _ffi.lib.leptris_xpath_compiled_eval(
                self._compiled, document._cd(), context
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

