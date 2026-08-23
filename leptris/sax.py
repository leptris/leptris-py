"""SAX parsing over the libleptris push parser (Ruby-parity surface).

Every event crosses the FFI boundary through a libffi callback, so
per-event cost is far higher than the DOM API; use SAX for huge
documents where you must not hold the tree.

Error model: raising inside a callback does not propagate (cffi
swallows it). The default SAXHandler.error records the failure and
leptris.sax raises ParseError after the C call returns; override
error() only if you want different behavior.
"""

from __future__ import annotations

from typing import Optional, Tuple

from . import _ffi
from .error import ParseError


class SAXHandler:
    """Subclass and override the events you care about."""

    last_error: Optional[Tuple[str, int, int]] = None

    def start_document(self) -> None:
        pass

    def end_document(self) -> None:
        pass

    def start_element(self, name: str, attributes: dict) -> None:
        pass

    def end_element(self, name: str) -> None:
        pass

    def characters(self, text: str) -> None:
        pass

    def comment(self, text: str) -> None:
        pass

    def cdata(self, text: str) -> None:
        pass

    def processing_instruction(self, target: str, data: str) -> None:
        pass

    def start_prefix_mapping(self, prefix: str, uri: str) -> None:
        pass

    def end_prefix_mapping(self, prefix: str) -> None:
        pass

    def error(self, message: str, line: int, column: int) -> None:
        self.last_error = (message, line, column)


def _decode(value) -> Optional[str]:
    if value == _ffi.ffi.NULL:
        return None
    return _ffi.ffi.string(value).decode("utf-8", "replace")


def _wrap(handler: SAXHandler):
    """Build the C handler struct; keeps every ffi.callback alive."""
    ffi = _ffi.ffi
    keepalive = []

    def callback(ctype, fn):
        c = ffi.callback(ctype, fn)
        keepalive.append(c)
        return c

    def attrs(pairs) -> dict:
        attributes = {}
        index = 0
        while pairs[index] != ffi.NULL:
            attributes[
                ffi.string(pairs[index]).decode("utf-8", "replace")
            ] = ffi.string(pairs[index + 1]).decode("utf-8", "replace")
            index += 2
        return attributes

    struct = ffi.new("LeptrisSAXHandler*")
    struct.start_document = callback(
        "void(*)(void*)", lambda ud: handler.start_document()
    )
    struct.end_document = callback(
        "void(*)(void*)", lambda ud: handler.end_document()
    )
    struct.start_element = callback(
        "void(*)(void*, const char*, const char**)",
        lambda ud, name, pairs: handler.start_element(
            _decode(name), attrs(pairs)
        ),
    )
    struct.end_element = callback(
        "void(*)(void*, const char*)",
        lambda ud, name: handler.end_element(_decode(name)),
    )
    struct.characters = callback(
        "void(*)(void*, const char*, size_t)",
        lambda ud, text, length: handler.characters(
            ffi.string(text, length).decode("utf-8", "replace")
        ),
    )
    struct.comment = callback(
        "void(*)(void*, const char*)",
        lambda ud, text: handler.comment(_decode(text)),
    )
    struct.cdata = callback(
        "void(*)(void*, const char*)",
        lambda ud, text: handler.cdata(_decode(text)),
    )
    struct.processing_instruction = callback(
        "void(*)(void*, const char*, const char*)",
        lambda ud, target, data: handler.processing_instruction(
            _decode(target), _decode(data)
        ),
    )
    struct.start_prefix_mapping = callback(
        "void(*)(void*, const char*, const char*)",
        lambda ud, prefix, uri: handler.start_prefix_mapping(
            _decode(prefix), _decode(uri)
        ),
    )
    struct.end_prefix_mapping = callback(
        "void(*)(void*, const char*)",
        lambda ud, prefix: handler.end_prefix_mapping(_decode(prefix)),
    )
    struct.error = callback(
        "void(*)(void*, const char*, int, int)",
        lambda ud, message, line, column: handler.error(
            _decode(message), line, column
        ),
    )
    return struct, keepalive


def _raise_if_failed(handler: SAXHandler, rc: int) -> None:
    if handler.last_error is not None:
        message, line, column = handler.last_error
        raise ParseError(f"{message} (line {line}, column {column})")
    if rc != 0:
        raise ParseError("SAX parse failed")


def parse(xml, handler: SAXHandler) -> None:
    """One-shot SAX parse of a complete document."""
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    struct, _keepalive = _wrap(handler)
    rc = _ffi.lib.leptris_sax_parse(xml, len(xml), struct, _ffi.ffi.NULL)
    _raise_if_failed(handler, rc)


class StreamingParser:
    """Push parser: feed() chunks, mark the last one final=True.

    With streaming=True (default) events are emitted as chunks
    arrive, with memory bounded by nesting depth, not document
    size; set_streaming must run before the first feed, which the
    constructor guarantees.
    """

    def __init__(self, handler: SAXHandler, *, streaming: bool = True):
        self._handler = handler
        struct, self._keepalive = _wrap(handler)
        self._parser = _ffi.lib.leptris_sax_parser_create(struct, _ffi.ffi.NULL)
        if self._parser == _ffi.ffi.NULL:
            raise ParseError("could not create SAX parser")
        if streaming:
            _ffi.lib.leptris_sax_parser_set_streaming(self._parser, 1)

    def feed(self, chunk, *, final: bool = False) -> None:
        if self._parser is None:
            raise ParseError("parser is closed")
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        rc = _ffi.lib.leptris_sax_parser_feed(
            self._parser, chunk, len(chunk), 1 if final else 0
        )
        _raise_if_failed(self._handler, rc)

    def close(self) -> None:
        if self._parser is not None:
            _ffi.lib.leptris_sax_parser_free(self._parser)
            self._parser = None

    def __enter__(self) -> "StreamingParser":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
