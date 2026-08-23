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
from collections.abc import Mapping
from itertools import repeat
from typing import Iterator, List, Optional, Union

from . import _ffi
from .error import LeptrisError

_CLARK = re.compile(r"\{([^}]*)\}")

_QNAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
_QNAME_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*(::.*)?$")

_TextNodes = (_ffi.NODE_TEXT, _ffi.NODE_CDATA)


class _AttribMap(Mapping):
    """Read-only dict view of an element's attributes."""

    __slots__ = ("_element",)

    def __init__(self, element: "Element"):
        self._element = element

    def __getitem__(self, name: str) -> str:
        value = self._element.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(self._element.keys())

    def __len__(self) -> int:
        self._element._check_alive()
        return _ffi.lib.leptris_element_attribute_count(self._element._ptr)

    def __repr__(self) -> str:
        return repr(dict(self))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self) == dict(other)
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]


class _PureElement:
    """Element as a plain Python class (fallback when the C
    accelerator is unavailable — same behavior, slower allocation)."""

    __slots__ = ("_ptr", "_document")

    def __init__(self, _ptr, document):
        self._ptr = _ptr
        self._document = document

    @property
    def document(self) -> "Document":
        return self._document

    def _check_alive(self) -> None:
        if self._document.closed:
            raise LeptrisError("operation on a closed document")

    # -- names and namespaces -------------------------------------------

    @property
    def tag(self) -> str:
        self._check_alive()
        name = _ffi.ffi.string(_ffi.lib.leptris_element_name(self._cd())).decode("utf-8")
        ns = _ffi.lib.leptris_element_namespace(self._cd())
        if ns == _ffi.ffi.NULL:
            return name
        return "{%s}%s" % (_ffi.ffi.string(ns).decode("utf-8"), name)

    @property
    def namespace(self) -> Optional[str]:
        self._check_alive()
        value = _ffi.lib.leptris_element_namespace(self._cd())
        if value == _ffi.ffi.NULL:
            return None
        return _ffi.ffi.string(value).decode("utf-8")

    @property
    def prefix(self) -> Optional[str]:
        self._check_alive()
        value = _ffi.lib.leptris_element_prefix(self._cd())
        if value == _ffi.ffi.NULL:
            return None
        return _ffi.ffi.string(value).decode("utf-8")

    # -- text (ElementTree model) ---------------------------------------

    def _run_at(self, node: Optional["Node"]) -> Optional[str]:
        parts = []
        while node is not None and node.type in _TextNodes:
            parts.append(node.content or "")
            node = node.next_sibling
        return "".join(parts) if parts else None

    @property
    def text(self) -> Optional[str]:
        self._check_alive()
        return self._run_at(self.to_node().first_child)

    @property
    def tail(self) -> Optional[str]:
        self._check_alive()
        return self._run_at(self.to_node().next_sibling)

    def itertext(self) -> Iterator[str]:
        self._check_alive()

        def walk(element: "Element") -> Iterator[str]:
            node = element.to_node().first_child
            while node is not None:
                if node.type in _TextNodes:
                    parts = []
                    while node is not None and node.type in _TextNodes:
                        parts.append(node.content or "")
                        node = node.next_sibling
                    yield "".join(parts)
                else:
                    if node.is_element():
                        yield from walk(node.as_element())
                    node = node.next_sibling

        yield from walk(self)

    # -- attributes ------------------------------------------------------

    def get(self, name: str, default=None):
        self._check_alive()
        value = _ffi.lib.leptris_element_attribute(
            self._cd(), name.encode("utf-8")
        )
        if value == _ffi.ffi.NULL:
            return default
        return _ffi.ffi.string(value).decode("utf-8")

    @property
    def attrib(self) -> Mapping:
        return _AttribMap(self)

    def _iter_attributes(self):
        attr = _ffi.lib.leptris_element_first_attribute(self._cd())
        while attr != _ffi.ffi.NULL:
            name = _ffi.ffi.string(
                _ffi.lib.leptris_attribute_get_name(attr)
            ).decode("utf-8")
            value = _ffi.ffi.string(
                _ffi.lib.leptris_attribute_get_value(self._ptr, attr)
            ).decode("utf-8")
            yield (name, value)
            attr = _ffi.lib.leptris_attribute_next(attr)

    def keys(self) -> List[str]:
        self._check_alive()
        return [name for name, _ in self._iter_attributes()]

    def items(self) -> List[tuple]:
        self._check_alive()
        return list(self._iter_attributes())

    def values(self) -> List[str]:
        self._check_alive()
        return [value for _, value in self._iter_attributes()]

    # -- tree navigation -------------------------------------------------

    @property
    def sourceline(self) -> int:
        """1-based source line of the element's start tag (lxml parity)."""
        self._check_alive()
        return _ffi.lib.leptris_node_line(
            _ffi.lib.leptris_element_as_node(self._cd())
        )

    def getparent(self) -> Optional["Element"]:
        self._check_alive()
        ptr = _ffi.lib.leptris_element_parent(self._ptr)
        if ptr == _ffi.ffi.NULL:
            return None
        return _make(ptr, self._document)

    def getnext(self) -> Optional["Element"]:
        # Element-level sibling chain skips text nodes (lxml getnext).
        self._check_alive()
        ptr = _ffi.lib.leptris_element_next_sibling_any(self._ptr)
        return None if ptr == _ffi.ffi.NULL else _make(ptr, self._document)

    def getprevious(self) -> Optional["Element"]:
        self._check_alive()
        ptr = _ffi.lib.leptris_element_previous_sibling_any(self._cd())
        return None if ptr == _ffi.ffi.NULL else _make(ptr, self._document)

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

    __getitem__ = _py_getitem

    def __len__(self) -> int:
        self._check_alive()
        return _ffi.lib.leptris_element_child_count(self._ptr)

    def __iter__(self) -> Iterator["Element"]:
        self._check_alive()
        lib = _ffi.lib
        count = lib.leptris_element_child_count(self._ptr)
        if count > 3:
            # Bulk fill wins from ~4 children up (measured crossover).
            buffer = _ffi.ffi.new("LeptrisElement[]", count)
            lib.leptris_element_children(self._cd(), buffer, count)
            return iter(_materialize(buffer, self._document))
        return self._iter_chain()

    def _iter_chain(self) -> Iterator["Element"]:
        lib = _ffi.lib
        child = lib.leptris_element_first_child_any(self._cd())
        while child != _ffi.ffi.NULL:
            yield _make(child, self._document)
            child = lib.leptris_element_next_sibling_any(child)

    def iter(self, tag: Optional[str] = None) -> Iterator["Element"]:
        # Subtree walks delegate to the engine: one descendant-or-self
        # evaluation at C speed plus batch materialization replaces
        # ~2 FFI dispatches per element (5x measured on the benchmark
        # matrix). Yields self first, then descendants in document
        # order — lxml's iter() contract.
        if tag is None or tag == "*":
            return iter(self.xpath("descendant-or-self::*"))
        if tag.startswith("{"):
            from .xpath import expand_clark_names

            expression, extra = expand_clark_names(
                "descendant-or-self::" + tag, None
            )
            return iter(self.xpath(expression, namespaces=extra or None))
        if _QNAME.match(tag):
            return iter(self.xpath("descendant-or-self::" + tag))
        return self._iter_filter(tag)

    def _iter_filter(self, tag) -> Iterator["Element"]:
        # Names that are not expressible as an XPath name test
        # (lxml treats them as non-matching filters).
        if self.tag == tag:
            yield self
        for child in self:
            yield from child._iter_filter(tag)

    def iterdescendants(self, tag: Optional[str] = None) -> Iterator["Element"]:
        if tag is None or tag == "*":
            return iter(self.xpath("descendant::*"))
        if tag.startswith("{"):
            from .xpath import expand_clark_names

            expression, extra = expand_clark_names("descendant::" + tag, None)
            return iter(self.xpath(expression, namespaces=extra or None))
        if _QNAME.match(tag):
            return iter(self.xpath("descendant::" + tag))
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
            raw = getattr(self, "_raw", None)
            if _accel is not None and raw is not None:
                from . import _ffi

                if namespaces:
                    flat = [v for pair in namespaces.items() for v in pair]
                    items = _accel.nodeset_ns(
                        self._document._raw_addr,
                        raw,
                        expression,
                        self._document,
                        flat,
                    )
                else:
                    items = _accel.nodeset(
                        self._document._raw_addr,
                        raw,
                        expression,
                        self._document,
                    )
                if items is not None:
                    return items
        return self._document.xpath(
            expression, context=self, namespaces=namespaces, variables=variables
        )

    def findall(self, path: str, namespaces=None) -> list:
        if "{" in path or namespaces:
            from .xpath import expand_clark_names

            expression, extra = expand_clark_names(path, namespaces)
            merged = dict(namespaces) if namespaces else {}
            merged.update(extra)
            if merged:
                raw = getattr(self, "_raw", None)
                if _accel is not None and raw is not None:
                    from . import _ffi

                    flat = [v for pair in merged.items() for v in pair]
                    items = _accel.nodeset_ns(
                        self._document._raw_addr,
                        raw,
                        expression,
                        self._document,
                        flat,
                    )
                    if items is not None:
                        return items
            return self.xpath(expression, namespaces=merged or None)
        if namespaces is None and "{" not in path and _QNAME_OK.match(path):
            # plain path: straight to the all-C evaluator
            raw = getattr(self, "_raw", None)
            if _accel is not None and raw is not None:
                from . import _ffi

                items = _accel.nodeset(
                    self._document._raw_addr,
                    raw,
                    path,
                    self._document,
                )
                if items is not None:
                    return items
            return self.xpath(path)
        from .xpath import expand_clark_names

        expression, extra = expand_clark_names(path, namespaces)
        merged = dict(namespaces) if namespaces else {}
        merged.update(extra)
        return self.xpath(expression, namespaces=merged or None)

    def find(self, path: str, namespaces=None) -> Optional["Element"]:
        if (
            namespaces is None
            and "{" not in path
            and "/" not in path
            and _QNAME_OK.match(path)
        ):
            raw = getattr(self, "_raw", None)
            if _accel is not None and raw is not None:
                found = _accel.find_first(raw, path, self._document)
                if found is not None:
                    return found
                return None
            results = self.findall(f"{path}[1]")
            return results[0] if results else None
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


import os as _os

if _os.environ.get("LEPTRIS_PURE"):
    # Explicit pure mode (CI exercises the fallback path this way).
    _accel = None
else:
    try:
        from . import _leptrisaccel as _accel
    except ImportError:
        _accel = None

if _accel is not None:
    Element = _accel.Element
    # The whole API surface lives in Python; the C heap type
    # contributes allocation plus the hot accessors (tag, text,
    # attrib, get, len, int indexing, getparent/getnext) which bind
    # to libleptris directly. Dunders attach post-creation (heap
    # types update their slots); _PureElement remains the reference
    # implementation and the pure-mode fallback.
    _accelerated = {
        "tag", "text", "tail", "attrib", "get", "getparent", "getnext",
        "getprevious", "keys", "items", "values", "itertext",
        "namespace", "prefix", "sourceline",
        "__len__", "__getitem__", "_ptr", "_document",
    }
    for _name, _value in _PureElement.__dict__.items():
        if _name in _accelerated or _name in (
            "__slots__", "__module__", "__dict__", "__weakref__",
            "__init__", "__doc__", "__qualname__",
        ):
            continue
        setattr(Element, _name, _value)


    def _accel_init(self, _ptr, document):
        self._ptr = _ptr
        self._document = document
        self._raw = int(_ffi.ffi.cast("uintptr_t", _ptr))

    _accel_itertext_c = Element.itertext
    Element.itertext = lambda self: iter(_accel_itertext_c(self))
    Element.__init__ = _accel_init

    _ffi.ffi  # ensure loaded
    _lib = _ffi.lib
    _accel.bind(
        **{
            name[8:]: int(_ffi.ffi.cast("uintptr_t", getattr(_lib, name)))
            for name in (
                "leptris_element_name", "leptris_element_namespace",
                "leptris_element_attribute", "leptris_element_child",
                "leptris_element_child_count", "leptris_element_as_node",
                "leptris_element_first_child_any",
                "leptris_node_first_child", "leptris_node_next_sibling",
                "leptris_node_get_type", "leptris_text_node_get_content",
                "leptris_cdata_node_get_content",
                "leptris_element_first_attribute",
                "leptris_attribute_next", "leptris_attribute_get_name",
                "leptris_attribute_get_value", "leptris_element_parent",
                "leptris_element_next_sibling_any", "leptris_node_line",
                "leptris_xpath_eval", "leptris_xpath_result_type",
                "leptris_xpath_result_count",
                "leptris_xpath_result_get_nodes",
                "leptris_xpath_result_free",
                "leptris_xpath_result_number",
                "leptris_xpath_result_boolean",
                "leptris_xpath_result_string",
                "leptris_free_string",
            )
        },
        ns_set_new=int(
            _ffi.ffi.cast("uintptr_t", _lib.leptris_xpath_ns_set_new)
        ),
        ns_set_free=int(
            _ffi.ffi.cast("uintptr_t", _lib.leptris_xpath_ns_set_free)
        ),
        ns_set_add=int(
            _ffi.ffi.cast("uintptr_t", _lib.leptris_xpath_ns_set_add)
        ),
        xpath_eval_ns=int(
            _ffi.ffi.cast("uintptr_t", _lib.leptris_xpath_eval_ns)
        ),
        element_serialize=int(
            _ffi.ffi.cast("uintptr_t", _lib.leptris_element_serialize)
        ),
        element_prefix_fn=int(
            _ffi.ffi.cast("uintptr_t", _lib.leptris_element_prefix)
        ),
        element_previous_sibling_any_fn=int(
            _ffi.ffi.cast(
                "uintptr_t", _lib.leptris_element_previous_sibling_any
            )
        ),
        error_class=LeptrisError,
    )

    def _make(_ptr, document):
        return _accel.create(
            int(_ffi.ffi.cast("uintptr_t", _ptr)), _ptr, document
        )

    def _materialize(buffer, document):
        count = len(buffer)
        return _accel.materialize(
            _ffi.ffi.unpack(buffer, count),
            document,
            _ffi.ffi.unpack(_ffi.ffi.cast("uintptr_t*", buffer), count),
        )

else:
    Element = _PureElement
    _make = Element

    def _materialize(buffer, document):
        return [
            Element(ptr, document)
            for ptr in _ffi.ffi.unpack(buffer, len(buffer))
        ]
