"""Document — the ElementTree analogue; owns the tree and its pool.

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
    __slots__ = ("_ptr", "_freed", "_accel_registry", "_raw_addr")

    def __init__(self, _ptr):
        self._ptr = _ptr
        self._freed = False
        try:
            from .element import _accel
            self._accel_registry = _accel.new_registry()
        except (ImportError, AttributeError):
            self._accel_registry = None
        self._raw_addr = int(_ffi.ffi.cast("uintptr_t", _ptr))
        # Touch the root once: flat-path documents misbehave on XPath
        # and serialization until promoted (leptris/leptris#550).
        _ffi.lib.leptris_document_root(_ptr)

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
        xml = bytes(xml)
        status = _ffi.ffi.new("int*")
        if recover:
            options = _ffi.ffi.new("LeptrisParseOptions*")
            options.flags = 0
            options.strict_mode = -1
            options.max_depth = 0
            options.recover = 1
            ptr = _ffi.lib.leptris_parse_string_ex(
                xml, len(xml), options, status
            )
        else:
            ptr = _ffi.lib.leptris_parse_string(xml, len(xml), status)
        if ptr == _ffi.ffi.NULL:
            raise ParseError(status_message(status[0]))
        return cls(ptr)

    @classmethod
    def parse_file(cls, path) -> "Document":
        path = os.fspath(path)
        if isinstance(path, str):
            path = path.encode("utf-8")
        status = _ffi.ffi.new("int*")
        ptr = _ffi.lib.leptris_parse_file(path, status)
        if ptr == _ffi.ffi.NULL:
            raise ParseError(status_message(status[0]))
        return cls(ptr)

    @property
    def root(self) -> Optional["Element"]:
        ptr = _ffi.lib.leptris_document_root(self._ptr)
        if ptr == _ffi.ffi.NULL:
            return None
        from .element import _make

        return _make(ptr, self)

    def getroot(self) -> Optional["Element"]:
        return self.root

    def xpath(self, expression: str, *, context=None, namespaces=None, variables=None):
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
        status = _ffi.lib.leptris_document_save_file(self._ptr, path, options)
        if status != 0:
            raise LeptrisError(status_message(status))

    def process_xinclude(self, base_url: Optional[str] = None) -> "Document":
        base = base_url.encode("utf-8") if base_url is not None else _ffi.ffi.NULL
        rc = _ffi.lib.leptris_xinclude_process(self._ptr, base)
        if rc != 0:
            raise LeptrisError("XInclude processing failed")
        return self

    def close(self) -> None:
        if not self._freed:
            registry = getattr(self, "_accel_registry", None)
            if registry is not None:
                from .element import _accel
                _accel.invalidate(registry)
            _ffi.lib.leptris_document_free(self._ptr)
            self._freed = True
            self._ptr = _ffi.ffi.NULL

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
