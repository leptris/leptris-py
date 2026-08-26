"""Node — generic tree traversal over every node type.

Element is the lxml-shaped typed view; Node exposes the underlying
DOM: text, comment, CDATA, PI and doctype nodes, which lxml users
reach through text/tail only.
"""

from __future__ import annotations

from typing import Optional

from . import _ffi
from .error import LeptrisError


class Node:
    __slots__ = ("_ptr", "_document")

    def __init__(self, _ptr, document):
        self._ptr = _ptr
        self._document = document

    def _check_alive(self) -> None:
        if self._document.closed:
            raise LeptrisError("operation on a closed document")

    @property
    def type(self) -> int:
        self._check_alive()
        return _ffi.lib.leptris_node_get_type(self._ptr)

    def is_element(self) -> bool:
        return self.type == _ffi.NODE_ELEMENT

    def is_text(self) -> bool:
        return self.type == _ffi.NODE_TEXT

    def is_comment(self) -> bool:
        return self.type == _ffi.NODE_COMMENT

    def is_cdata(self) -> bool:
        return self.type == _ffi.NODE_CDATA

    def is_pi(self) -> bool:
        return self.type == _ffi.NODE_PI

    def is_doctype(self) -> bool:
        return self.type == _ffi.NODE_DOCTYPE

    @property
    def content(self) -> Optional[str]:
        t = self.type
        if t == _ffi.NODE_TEXT:
            getter = _ffi.lib.leptris_text_node_get_content
        elif t == _ffi.NODE_COMMENT:
            getter = _ffi.lib.leptris_comment_node_get_content
        elif t == _ffi.NODE_CDATA:
            getter = _ffi.lib.leptris_cdata_node_get_content
        else:
            return None
        value = getter(self._ptr)
        return _ffi.ffi.string(value).decode("utf-8") if value != _ffi.ffi.NULL else ""

    @property
    def first_child(self) -> Optional["Node"]:
        self._check_alive()
        ptr = _ffi.lib.leptris_node_first_child(self._ptr)
        return None if ptr == _ffi.ffi.NULL else Node(ptr, self._document)

    @property
    def next_sibling(self) -> Optional["Node"]:
        self._check_alive()
        ptr = _ffi.lib.leptris_node_next_sibling(self._ptr)
        return None if ptr == _ffi.ffi.NULL else Node(ptr, self._document)

    @property
    def previous_sibling(self) -> Optional["Node"]:
        self._check_alive()
        ptr = _ffi.lib.leptris_node_previous_sibling(self._ptr)
        return None if ptr == _ffi.ffi.NULL else Node(ptr, self._document)

    @property
    def child_count(self) -> int:
        self._check_alive()
        return _ffi.lib.leptris_node_child_count(self._ptr)

    def as_element(self) -> Optional["Element"]:
        if not self.is_element():
            return None
        ptr = _ffi.lib.leptris_node_as_element(self._ptr)
        if ptr == _ffi.ffi.NULL:
            return None
        from .element import _make

        # _make links the element into the document registry so
        # close() poisons it; constructing Element directly bypassed
        # the registry and left a raw pointer into freed memory.
        return _make(ptr, self._document)

    def __repr__(self) -> str:
        return f"<leptris.Node type={self.type}>"
