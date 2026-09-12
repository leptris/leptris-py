"""Native XML diff (libleptris 1.9.144+): digest-pruned ordered
edit scripts between two documents.
"""

from __future__ import annotations

from collections import namedtuple
from typing import Iterator, Optional

from . import _ffi
from .error import LeptrisError

DiffOp = namedtuple("DiffOp", "type path name before after")

_OP_TYPES = {
    1: "insert",
    2: "delete",
    3: "update-text",
    4: "update-attr",
}


def diff(a, b, *, ignore_ws_text: bool = False) -> "Diff":
    """Compute the ordered edit script from document ``a`` to ``b``.

    Elements are compared structurally (digest-pruned); whitespace-
    only text nodes are treated as absent with ignore_ws_text.
    """
    from .document import Document

    if not isinstance(a, Document) or not isinstance(b, Document):
        raise TypeError("expected two Documents")
    flags = 1 if ignore_ws_text else 0
    handle = _ffi.lib.leptris_diff(a._cd(), b._cd(), flags, _ffi.ffi.NULL)
    if handle == _ffi.ffi.NULL:
        raise LeptrisError("diff failed")
    return Diff(handle)


class Diff:
    """An edit script between two documents (iterate the ops)."""

    __slots__ = ("_handle",)

    def __init__(self, _handle):
        self._handle = _handle

    def __len__(self) -> int:
        return int(_ffi.lib.leptris_diff_op_count(self._handle))

    def __iter__(self) -> Iterator[DiffOp]:
        lib = _ffi.lib
        ffi = _ffi.ffi

        def _text(ptr):
            return ffi.string(ptr).decode("utf-8", "replace") if ptr != ffi.NULL else ""

        for index in range(len(self)):
            yield DiffOp(
                _OP_TYPES.get(
                    lib.leptris_diff_op_type(self._handle, index), "?"
                ),
                _text(lib.leptris_diff_op_path(self._handle, index)),
                _text(lib.leptris_diff_op_name(self._handle, index)),
                _text(lib.leptris_diff_op_before(self._handle, index)),
                _text(lib.leptris_diff_op_after(self._handle, index)),
            )

    def serialize(self) -> str:
        """Line-per-op text form ('- path @attr "before" -> "after"' …)."""
        ptr = _ffi.lib.leptris_diff_serialize(self._handle)
        if ptr == _ffi.ffi.NULL:
            raise LeptrisError("diff serialization failed")
        try:
            return _ffi.ffi.string(ptr).decode("utf-8", "replace")
        finally:
            _ffi.lib.leptris_free_string(ptr)

    def __repr__(self) -> str:
        return f"<Diff {len(self)} ops>"

    def __del__(self):
        try:
            handle = getattr(self, "_handle", None)
            if handle is not None:
                _ffi.lib.leptris_diff_free(handle)
                self._handle = None
        except Exception:
            pass
