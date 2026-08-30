"""Element — lxml-compatible view over LeptrisElement.

Elements are owned by their parent Document; they are never freed
directly. Element objects keep a reference to the Document so the
tree cannot outlive its pool.

``tag`` uses lxml's Clark notation (``{uri}local``). ``text``/``tail``
follow the ElementTree model: computed from the adjacent node-level
text and CDATA runs (runs merge, as lxml's default parser does),
NOT from the C API's whole-subtree concatenated ``element_text``.
"""

from __future__ import annotations

import re
from typing import Iterator, Optional

from . import _ffi
from .error import LeptrisError

_QNAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
_QNAME_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*(::.*)?$")



class _ElementMethods:
    """Method host: the API surface attached onto the C heap type in
    _leptrisaccel (allocation and the hot accessors live there)."""

    __slots__ = ()

    @property
    def document(self) -> "Document":
        return self._document

    def _check_alive(self) -> None:
        if self._document.closed:
            raise LeptrisError("operation on a closed document")

    def _child_at(self, index: int) -> "Element":
        ptr = _ffi.lib.leptris_element_child(self._cd(), index)
        if ptr == _ffi.ffi.NULL:
            raise IndexError("child index out of range")
        return _make(ptr, self._document)

    def _py_getitem(self, index):
        # C fast path handles plain ints when the accelerator is
        # bound; this covers slices (and is the whole implementation
        # in pure mode).
        self._check_alive()
        count = _ffi.lib.leptris_element_child_count(self._cd())
        if isinstance(index, slice):
            return [self._child_at(i) for i in range(*index.indices(count))]
        if index < 0:
            index += count
        if not 0 <= index < count:
            raise IndexError("child index out of range")
        return self._child_at(index)

    def __iter__(self) -> Iterator["Element"]:
        self._check_alive()
        return iter(_accel.children(self))

    def iter(self, tag: Optional[str] = None) -> Iterator["Element"]:
        # The C cursor walks first_child/next_sibling/parent directly —
        # no expression is built and no engine evaluation happens, so
        # the descendant-or-self root omission (leptris/leptris#557)
        # cannot bite here.
        self._check_alive()
        if tag is None or tag == "*":
            return _accel.subtree_iter(self, True, None, None)
        if tag.startswith("{") and "}" in tag:
            uri, local = tag[1:].split("}", 1)
            return _accel.subtree_iter(self, True, uri, local)
        if _QNAME.match(tag):
            return _accel.subtree_iter(self, True, None, tag)
        return self._iter_filter(tag)

    def _iter_filter(self, tag) -> Iterator["Element"]:
        # Names that are not expressible as an XPath name test
        # (lxml treats them as non-matching filters).
        if self.tag == tag:
            yield self
        for child in self:
            yield from child._iter_filter(tag)

    def iterdescendants(self, tag: Optional[str] = None) -> Iterator["Element"]:
        self._check_alive()
        if tag is None or tag == "*":
            return _accel.subtree_iter(self, False, None, None)
        if tag.startswith("{") and "}" in tag:
            uri, local = tag[1:].split("}", 1)
            return _accel.subtree_iter(self, False, uri, local)
        if _QNAME.match(tag):
            return _accel.subtree_iter(self, False, None, tag)
        return self._iter_descendants_filter(tag)

    def _iter_descendants_filter(self, tag) -> Iterator["Element"]:
        for child in self:
            yield from child._iter_filter(tag)

    def to_node(self) -> "Node":
        from .node import Node

        return Node(_ffi.lib.leptris_element_as_node(self._cd()), self._document)

    # -- queries ---------------------------------------------------------

    def xpath(self, expression: str, *, namespaces=None, variables=None):
        if variables is None:
            items = _c_evaluate(self._document, self, expression, namespaces)
            if items is not None:
                return items
        return self._document.xpath(
            expression, context=self, namespaces=namespaces, variables=variables
        )

    def findall(self, path: str, namespaces=None) -> list:
        if "{" in path or namespaces:
            expression, extra = expand_clark_names(path, namespaces)
            merged = dict(namespaces) if namespaces else {}
            merged.update(extra)
            items = _c_evaluate(self._document, self, expression, merged or None)
            if items is not None:
                return items
            return self._document.xpath(
                expression, context=self, namespaces=merged or None
            )
        if _QNAME_OK.match(path):
            # plain path: straight to the all-C evaluator
            items = _c_evaluate(self._document, self, path, None)
            if items is not None:
                return items
            return self._document.xpath(path, context=self)
        expression, extra = expand_clark_names(path, namespaces)
        return self._document.xpath(
            expression, context=self, namespaces=extra or None
        )

    def find(self, path: str, namespaces=None) -> Optional["Element"]:
        if namespaces is None and "{" not in path:
            raw = getattr(self, "_raw", None)
            if _accel is not None and raw is not None:
                if "/" in path:
                    # plain multi-step path: first-match walk, no list
                    steps = path.split("/")
                    if steps and all(_QNAME.match(s) for s in steps):
                        return _accel.find_path(raw, steps, self._document)
                elif _QNAME_OK.match(path):
                    return _accel.find_first(raw, path, self._document)
        results = self.findall(path, namespaces)
        return results[0] if results else None

    def findtext(self, path: str, default=None, namespaces=None) -> Optional[str]:
        found = self.find(path, namespaces)
        if found is None:
            return default
        text = found.text
        return text if text is not None else default

    def _cd(self):
        """cffi handle for this element, created lazily when the C
        fast paths produced it without one."""
        ptr = self._ptr
        if ptr is None:
            ptr = _ffi.ffi.cast("LeptrisElement", self._raw)
            self._ptr = ptr
        return ptr

    def __repr__(self) -> str:
        return f"<Element {self.tag!r} at {id(self):#x}>"


from . import _leptrisaccel as _accel
from .xpath import _c_evaluate, expand_clark_names

# The C heap type is self-describing: a member it provides (hot
# accessors, slots) resolves to something beyond object's default, so
# it is left alone — the ownership contract has one home, the C module.
Element = _accel.Element
_TYPE_MACHINERY = frozenset(
    ("__slots__", "__module__", "__dict__", "__weakref__",
     "__doc__", "__qualname__")
)
for _name, _value in _ElementMethods.__dict__.items():
    if _name in _TYPE_MACHINERY:
        continue
    if getattr(Element, _name, None) is getattr(object, _name, None):
        setattr(Element, _name, _value)


def _element_init(self, _ptr, document):
    self._ptr = _ptr
    self._document = document
    self._raw = int(_ffi.ffi.cast("uintptr_t", _ptr))


Element.__init__ = _element_init

# The C itertext returns a list; the API contract is an iterator.
_itertext_c = Element.itertext
Element.itertext = lambda self: iter(_itertext_c(self))


def _make(_ptr, document):
    return _accel.create(int(_ffi.ffi.cast("uintptr_t", _ptr)), _ptr, document)


def _materialize(buffer, document):
    count = len(buffer)
    return _accel.materialize(
        _ffi.ffi.unpack(buffer, count),
        document,
        _ffi.ffi.unpack(_ffi.ffi.cast("uintptr_t*", buffer), count),
    )


_lib = _ffi.lib
# Fns declaration order in _leptrisaccel.c is the protocol: this
# tuple must list the libleptris symbols in exactly that order.
_BIND_NAMES = (
    "leptris_element_name",
    "leptris_element_namespace",
    "leptris_element_attribute",
    "leptris_element_attribute_ns",
    "leptris_element_child",
    "leptris_element_child_count",
    "leptris_element_as_node",
    "leptris_node_first_child",
    "leptris_node_next_sibling",
    "leptris_node_get_type",
    "leptris_text_node_get_content",
    "leptris_cdata_node_get_content",
    "leptris_element_first_child_any",
    "leptris_element_prefix",
    "leptris_element_previous_sibling_any",
    "leptris_element_first_attribute",
    "leptris_attribute_next",
    "leptris_attribute_get_name",
    "leptris_attribute_get_value",
    "leptris_element_parent",
    "leptris_element_next_sibling_any",
    "leptris_node_line",
    "leptris_xpath_eval",
    "leptris_xpath_result_type",
    "leptris_xpath_result_count",
    "leptris_xpath_result_get_nodes",
    "leptris_xpath_result_free",
    "leptris_xpath_result_number",
    "leptris_xpath_result_boolean",
    "leptris_xpath_result_string",
    "leptris_free_string",
    "leptris_xpath_ns_set_new",
    "leptris_xpath_ns_set_free",
    "leptris_xpath_ns_set_add",
    "leptris_xpath_eval_ns",
    "leptris_element_serialize",
    "leptris_element_serialize_into",
    "leptris_document_serialize",
    "leptris_parse_string",
    "leptris_parse_string_ex",
    "leptris_parse_file",
    "leptris_document_root",
    "leptris_document_free",
    "leptris_xpath_compiled_eval",
    "leptris_xpath_compiled_eval_ns",
    "leptris_parse_string_inplace",
    "leptris_xpath_variable_set_new",
    "leptris_xpath_variable_set_free",
    "leptris_xpath_variable_set_boolean",
    "leptris_xpath_variable_set_number",
    "leptris_xpath_variable_set_string",
    "leptris_xpath_compiled_eval_vars",
    "leptris_parse_string_with_encoding",
    "leptris_xpath_compiled_eval_ns_vars",
    "leptris_iterparse_next",
)
_accel.bind(
    [
        int(_ffi.ffi.cast("uintptr_t", getattr(_lib, name)))
        for name in _BIND_NAMES
    ],
    LeptrisError,
)
