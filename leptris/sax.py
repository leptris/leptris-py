"""SAX parsing over the libleptris event recorder (Ruby-parity surface).

Events are buffered C-side and drained in bulk (records + a packed
arena, one transfer per chunk — libleptris 1.9.4+): no per-event
libffi callbacks, which measured ~2.5 µs each. Use SAX for huge
documents where you must not hold the tree.

Error model: parse failures surface as a recorded ERROR event; the
default SAXHandler.error stores it and leptris.sax raises ParseError
after the drain completes.
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


_KIND_START_DOCUMENT = 0
_KIND_END_DOCUMENT = 1
_KIND_START_ELEMENT = 2
_KIND_END_ELEMENT = 3
_KIND_CHARACTERS = 4
_KIND_COMMENT = 5
_KIND_CDATA = 6
_KIND_PI = 7
_KIND_START_PREFIX = 8
_KIND_END_PREFIX = 9
_KIND_ERROR = 10


def _drain(handler: SAXHandler, recorder, chunk_label: str) -> None:
    """Read one chunk's buffered records and dispatch them."""
    lib, ffi = _ffi.lib, _ffi.ffi
    count = ffi.new("size_t*")
    records = lib.leptris_sax_recorder_records(recorder, count)
    if records == ffi.NULL or count[0] == 0:
        return
    arena_len = ffi.new("size_t*")
    arena = bytes(
        ffi.buffer(lib.leptris_sax_recorder_arena(recorder, arena_len), arena_len[0])
    )

    def slice_(offset: int, length: int) -> str:
        return arena[offset : offset + length].decode("utf-8", "replace") if length else ""

    for index in range(count[0]):
        record = records[index]
        kind = record.kind
        name = slice_(record.name_off, record.name_len)
        text = slice_(record.text_off, record.text_len)
        if kind == _KIND_START_DOCUMENT:
            handler.start_document()
        elif kind == _KIND_END_DOCUMENT:
            handler.end_document()
        elif kind == _KIND_START_ELEMENT:
            attributes = {}
            offset = record.attrs_off
            for _ in range(record.attr_count):
                end = arena.index(b"\x00", offset)
                attr_name = arena[offset:end].decode("utf-8", "replace")
                value_start = end + 1
                value_end = arena.index(b"\x00", value_start)
                attributes[attr_name] = arena[value_start:value_end].decode(
                    "utf-8", "replace"
                )
                offset = value_end + 1
            handler.start_element(name, attributes)
        elif kind == _KIND_END_ELEMENT:
            handler.end_element(name)
        elif kind == _KIND_CHARACTERS:
            handler.characters(text)
        elif kind == _KIND_COMMENT:
            handler.comment(text)
        elif kind == _KIND_CDATA:
            handler.cdata(text)
        elif kind == _KIND_PI:
            handler.processing_instruction(name, text)
        elif kind == _KIND_START_PREFIX:
            handler.start_prefix_mapping(name, text)
        elif kind == _KIND_END_PREFIX:
            handler.end_prefix_mapping(name)
        elif kind == _KIND_ERROR:
            handler.error(text, record.line, record.column)


def _raise_if_failed(handler: SAXHandler) -> None:
    if handler.last_error is not None:
        message, line, column = handler.last_error
        raise ParseError(f"{message} (line {line}, column {column})")


def parse(xml, handler: SAXHandler) -> None:
    """One-shot SAX parse of a complete document."""
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    handler.last_error = None
    lib, ffi = _ffi.lib, _ffi.ffi
    recorder = lib.leptris_sax_recorder_new()
    if recorder == ffi.NULL:
        raise ParseError("could not create SAX recorder")
    try:
        rc = lib.leptris_sax_recorder_feed(recorder, xml, len(xml), 1)
        _drain(handler, recorder, "document")
        _raise_if_failed(handler)
        if rc != 0 and handler.last_error is None:
            raise ParseError("SAX parse failed")
    finally:
        lib.leptris_sax_recorder_free(recorder)


class StreamingParser:
    """Push parser: feed() chunks, mark the last one final=True.

    Events for each chunk are buffered C-side and drained in bulk on
    return (libleptris 1.9.4+ recorder); memory stays bounded by the
    largest chunk's event backlog, not the document size.

    The `streaming` keyword is accepted for backward compatibility
    and ignored: the recorder always streams (the legacy buffering
    mode it used to select no longer exists); passing False emits a
    DeprecationWarning.
    """

    def __init__(self, handler: SAXHandler, *, streaming: bool = True):
        if not streaming:
            import warnings

            warnings.warn(
                "streaming=False is deprecated: the event recorder "
                "always streams (legacy buffering mode is gone)",
                DeprecationWarning,
                stacklevel=2,
            )
        self._handler = handler
        handler.last_error = None  # same reuse contract as sax.parse
        self._recorder = _ffi.lib.leptris_sax_recorder_new()
        if self._recorder == _ffi.ffi.NULL:
            raise ParseError("could not create SAX recorder")

    def feed(self, chunk, *, final: bool = False) -> None:
        if self._recorder is None:
            raise ParseError("parser is closed")
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        rc = _ffi.lib.leptris_sax_recorder_feed(
            self._recorder, chunk, len(chunk), 1 if final else 0
        )
        _drain(self._handler, self._recorder, "chunk")
        _raise_if_failed(self._handler)
        if rc != 0 and self._handler.last_error is None:
            raise ParseError("SAX parse failed")

    def close(self) -> None:
        if self._recorder is not None:
            _ffi.lib.leptris_sax_recorder_free(self._recorder)
            self._recorder = None

    def __enter__(self) -> "StreamingParser":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
