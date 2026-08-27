"""Document — the ElementTree analogue; owns the tree, its pool, and
(when parsed from a string) the buffer the engine parsed in place.

Release it with close() (or the context manager); __del__ is a
last-resort safety net for CPython refcounting, not a contract.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from . import _ffi
from .error import LeptrisError, ParseError, status_message


def serialize_options(
    encoding: Optional[str] = None,
    pretty_print: bool = False,
    xml_declaration: Optional[bool] = None,
) -> Tuple[object, List[object]]:
    """Build a LeptrisSerializeOptions (or NULL for defaults).

    Returns (pointer, keepalive) — the keepalive list must stay
    referenced until serialization completes.
    """
    ffi = _ffi.ffi
    declaration = xml_declaration
    if declaration is None:
        # lxml default: an explicit encoding implies a declaration.
        declaration = encoding is not None
    if not declaration and not pretty_print and encoding is None:
        return ffi.NULL, []
    options = ffi.new("LeptrisSerializeOptions*")
    keepalive = [options]
    options.indent = 2 if pretty_print else 0
    options.xml_declaration = 1 if declaration else 0
    if encoding is not None:
        buffer = ffi.new("char[]", encoding.encode("utf-8"))
        options.encoding = buffer
        keepalive.append(buffer)
    return options, keepalive


class Document:
    __slots__ = ("_ptr", "_freed", "_accel_registry", "_raw_addr", "_buffer")

    @classmethod
    def _from_parts(cls, address, registry, buffer=None):
        doc = cls.__new__(cls)
        doc._ptr = _ffi.ffi.NULL
        doc._freed = False
        doc._accel_registry = registry
        doc._raw_addr = address
        # In-place parses retain pointers into the input buffer until
        # document_free; the view (which owns the bytearray) must
        # outlive the document. Dropped in close(), after the free.
        doc._buffer = buffer
        return doc

    @classmethod
    def parse(cls, xml, *, recover: bool = False) -> "Document":
        """Parse XML. With recover=True a malformed document yields an
        empty (rootless) Document instead of raising ParseError
        (libleptris 1.9.0 recover mode — partial-tree recovery is not
        yet implemented upstream)."""
        if isinstance(xml, str):
            xml = xml.encode("utf-8")
        if not isinstance(xml, (bytes, bytearray, memoryview)):
            raise TypeError("xml must be str or bytes")
        data = bytearray(xml)  # writable copy: the engine may parse in place
        if not data:
            raise ParseError("parse error: empty input")
        from .element import _accel

        view = _ffi.ffi.from_buffer("char[]", data)
        address, registry, status = _accel.parse_inplace(
            int(_ffi.ffi.cast("uintptr_t", view)), len(data), recover
        )
        if address is None:
            raise ParseError(status_message(status))
        return cls._from_parts(address, registry, view)

    @classmethod
    def parse_file(cls, path) -> "Document":
        path = os.fspath(path)
        if isinstance(path, str):
            path = path.encode("utf-8")
        from .element import _accel

        address, registry, status = _accel.parse_file(path)
        if address is None:
            raise ParseError(status_message(status))
        return cls._from_parts(address, registry)  # file parse copies internally

    def _cd(self):
        """cffi handle for cold cffi paths, created lazily."""
        ptr = self._ptr
        if ptr == _ffi.ffi.NULL:
            ptr = _ffi.ffi.cast("LeptrisDocument", self._raw_addr)
            self._ptr = ptr
        return ptr

    @property
    def root(self) -> Optional["Element"]:
        if self._freed:
            raise LeptrisError("operation on a closed document")
        from .element import _accel

        return _accel.document_root(self._raw_addr, self)

    def getroot(self) -> Optional["Element"]:
        return self.root

    def toplevel_comments(self) -> List[str]:
        """Document-level comments outside the root (prolog then epilog).

        Requires libleptris 1.9.3+. Contents are the text between the
        markers; the markers themselves are not included.
        """
        if self._freed:
            raise LeptrisError("operation on a closed document")
        lib, ffi = _ffi.lib, _ffi.ffi
        doc = self._cd()
        count = lib.leptris_document_comment_count(doc)
        items = []
        for index in range(count):
            ptr = lib.leptris_document_comment_content(doc, index)
            items.append(
                ffi.string(ptr).decode("utf-8") if ptr != ffi.NULL else ""
            )
        return items

    def toplevel_pis(self) -> List[Tuple[str, Optional[str]]]:
        """Document-level processing instructions outside the root.

        Returns (target, data) pairs. A dataless PI (<?target?>)
        yields data as the empty string (libleptris 1.9.3+).
        """
        if self._freed:
            raise LeptrisError("operation on a closed document")
        lib, ffi = _ffi.lib, _ffi.ffi
        doc = self._cd()
        count = lib.leptris_document_pi_count(doc)
        items = []
        for index in range(count):
            target = lib.leptris_document_pi_target(doc, index)
            data = lib.leptris_document_pi_data(doc, index)
            items.append(
                (
                    ffi.string(target).decode("utf-8") if target != ffi.NULL else "",
                    (
                        ffi.string(data).decode("utf-8")
                        if data != ffi.NULL
                        else None
                    ),
                )
            )
        return items

    def xpath(self, expression: str, *, context=None, namespaces=None, variables=None):
        if self._freed:
            raise LeptrisError("operation on a closed document")
        if variables is None:
            from .xpath import _c_evaluate

            items = _c_evaluate(self, context, expression, namespaces)
            if items is not None:
                return items
        from .xpath import _XPathEngine

        return _XPathEngine.evaluate(
            self, context, expression, namespaces=namespaces, variables=variables
        )

    def write(
        self,
        file,
        *,
        encoding: Optional[str] = None,
        pretty_print: bool = False,
        xml_declaration: Optional[bool] = None,
    ) -> None:
        if self._freed:
            raise LeptrisError("operation on a closed document")
        if hasattr(file, "write"):
            from .api import tostring

            file.write(
                tostring(
                    self,
                    encoding=encoding,
                    pretty_print=pretty_print,
                    xml_declaration=xml_declaration,
                )
            )
            return
        path = os.fspath(file)
        if isinstance(path, str):
            path = path.encode("utf-8")
        options, _keepalive = serialize_options(encoding, pretty_print, xml_declaration)
        status = _ffi.lib.leptris_document_save_file(self._cd(), path, options)
        if status != 0:
            raise LeptrisError(status_message(status))

    def process_xinclude(self, base_url: Optional[str] = None) -> "Document":
        if self._freed:
            raise LeptrisError("operation on a closed document")
        base = base_url.encode("utf-8") if base_url is not None else _ffi.ffi.NULL
        rc = _ffi.lib.leptris_xinclude_process(self._cd(), base)
        if rc != 0:
            raise LeptrisError("XInclude processing failed")
        return self

    def close(self) -> None:
        if not self._freed:
            from .element import _accel

            registry = getattr(self, "_accel_registry", None)
            if registry is not None:
                _accel.invalidate(registry)
            _accel.close_document(self._raw_addr)
            self._freed = True
            self._ptr = _ffi.ffi.NULL
            self._buffer = None

    @property
    def closed(self) -> bool:
        return self._freed

    def __enter__(self) -> "Document":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
