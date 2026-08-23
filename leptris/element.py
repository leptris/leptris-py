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
from typing import Iterator, List, Optional, Union

from . import _ffi
from .error import LeptrisError

_CLARK = re.compile(r"\{([^}]*)\}")

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


class Element:
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
        name = _ffi.ffi.string(_ffi.lib.leptris_element_name(self._ptr)).decode("utf-8")
        ns = _ffi.lib.leptris_element_namespace(self._ptr)
        if ns == _ffi.ffi.NULL:
            return name
        return "{%s}%s" % (_ffi.ffi.string(ns).decode("utf-8"), name)

    @property
    def namespace(self) -> Optional[str]:
        self._check_alive()
        value = _ffi.lib.leptris_element_namespace(self._ptr)
        if value == _ffi.ffi.NULL:
            return None
        return _ffi.ffi.string(value).decode("utf-8")

    @property
    def prefix(self) -> Optional[str]:
        self._check_alive()
        value = _ffi.lib.leptris_element_prefix(self._ptr)
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
            self._ptr, name.encode("utf-8")
        )
        if value == _ffi.ffi.NULL:
            return default
        return _ffi.ffi.string(value).decode("utf-8")

    @property
    def attrib(self) -> Mapping:
        return _AttribMap(self)

    def _iter_attributes(self):
        attr = _ffi.lib.leptris_element_first_attribute(self._ptr)
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

    def getparent(self) -> Optional["Element"]:
        self._check_alive()
        ptr = _ffi.lib.leptris_element_parent(self._ptr)
        if ptr == _ffi.ffi.NULL:
            return None
        return Element(ptr, self._document)

    def getnext(self) -> Optional["Element"]:
        # Element-level sibling chain skips text nodes (lxml getnext).
        self._check_alive()
        ptr = _ffi.lib.leptris_element_next_sibling_any(self._ptr)
        return None if ptr == _ffi.ffi.NULL else Element(ptr, self._document)

    def getprevious(self) -> Optional["Element"]:
        self._check_alive()
        ptr = _ffi.lib.leptris_element_previous_sibling_any(self._ptr)
        return None if ptr == _ffi.ffi.NULL else Element(ptr, self._document)

    def _child_at(self, index: int) -> "Element":
        ptr = _ffi.lib.leptris_element_child(self._ptr, index)
        if ptr == _ffi.ffi.NULL:
            raise IndexError("child index out of range")
        return Element(ptr, self._document)

    def __getitem__(self, index: Union[int, slice]) -> Union["Element", List["Element"]]:
        self._check_alive()
        count = _ffi.lib.leptris_element_child_count(self._ptr)
        if isinstance(index, slice):
            return [self._child_at(i) for i in range(*index.indices(count))]
        if index < 0:
            index += count
        if not 0 <= index < count:
            raise IndexError("child index out of range")
        return self._child_at(index)

    def __len__(self) -> int:
        self._check_alive()
        return _ffi.lib.leptris_element_child_count(self._ptr)

    def __iter__(self) -> Iterator["Element"]:
        self._check_alive()
        lib = _ffi.lib
        child = lib.leptris_element_first_child_any(self._ptr)
        while child != _ffi.ffi.NULL:
            yield Element(child, self._document)
            child = lib.leptris_element_next_sibling_any(child)

    def iter(self, tag: Optional[str] = None) -> Iterator["Element"]:
        if tag is None or self.tag == tag:
            yield self
        for child in self:
            yield from child.iter(tag)

    def iterdescendants(self, tag: Optional[str] = None) -> Iterator["Element"]:
        for child in self:
            yield from child.iter(tag)

    def to_node(self) -> "Node":
        from .node import Node

        return Node(_ffi.lib.leptris_element_as_node(self._ptr), self._document)

    # -- queries ---------------------------------------------------------

    def xpath(self, expression: str, *, namespaces=None, variables=None):
        return self._document.xpath(
            expression, context=self, namespaces=namespaces, variables=variables
        )

    def findall(self, path: str, namespaces=None) -> list:
        from .xpath import expand_clark_names

        expression, extra = expand_clark_names(path, namespaces)
        merged = dict(namespaces) if namespaces else {}
        merged.update(extra)
        return self.xpath(expression, namespaces=merged or None)

    def find(self, path: str, namespaces=None) -> Optional["Element"]:
        results = self.findall(path, namespaces)
        return results[0] if results else None

    def findtext(self, path: str, default=None, namespaces=None) -> Optional[str]:
        found = self.find(path, namespaces)
        if found is None:
            return default
        return found.text if found.text is not None else default

    def __repr__(self) -> str:
        return f"<Element {self.tag!r} at {id(self):#x}>"
