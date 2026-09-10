"""ISO Schematron validation (libleptris 1.9.126+): compile a
schema once, validate any number of documents. Validity = zero
failed asserts (successful reports do not invalidate); the SVRL
report carries locations, tests and messages. The engine gates
50/50 on schematron/schematron-conformance.
"""

from __future__ import annotations

from . import _engine, _ffi
from .document import Document
from .error import SchematronError


class Schematron(_engine.CompiledSource):
    """A compiled ISO Schematron schema."""

    @staticmethod
    def _parse(encoded, length):
        return _ffi.lib.leptris_schematron_parse(
            encoded, length, _ffi.ffi.NULL)

    _free = _ffi.lib.leptris_schematron_free
    _label = "Schematron schema"
    _error = SchematronError

    @classmethod
    def from_file(cls, path) -> "Schematron":
        """Compile a schema from a file path."""
        source = str(path).encode("utf-8")
        handle = _ffi.lib.leptris_schematron_parse_file(
            source, _ffi.ffi.NULL)
        if handle == _ffi.ffi.NULL:
            raise SchematronError(
                f"schema file could not be parsed: {path}")
        obj = cls.__new__(cls)
        obj._source = source
        obj._handle = handle
        return obj

    @classmethod
    def from_phase(cls, schema, phase) -> "Schematron":
        """Compile with a phase selected: only the patterns the
        phase activates are evaluated."""
        encoded = schema if isinstance(schema, bytes) else str(schema).encode("utf-8")
        phase_b = str(phase).encode("utf-8")
        handle = _ffi.lib.leptris_schematron_parse_phase(
            encoded, len(encoded), phase_b, _ffi.ffi.NULL)
        if handle == _ffi.ffi.NULL:
            obj = cls.__new__(cls)
            obj._source = encoded
            obj._handle = _ffi.ffi.NULL
            raise SchematronError(obj._compile_detail())
        obj = cls.__new__(cls)
        obj._source = encoded
        obj._handle = handle
        return obj

    def is_valid(self, document_or_element) -> bool:
        """Validity = zero failed asserts (reports do not
        invalidate)."""
        document = self._document(document_or_element)
        return bool(
            _ffi.lib.leptris_schematron_valid(self._handle,
                                              document._cd()))

    def validate(self, document_or_element):
        """The full SVRL report as a Document:
        svrl:schematron-output with failed-assert /
        successful-report entries carrying @test, @location and
        svrl:text."""
        document = self._document(document_or_element)
        raw = _ffi.lib.leptris_schematron_validate(
            self._handle, document._cd())
        if raw == _ffi.ffi.NULL:
            return None
        ptr = _ffi.lib.leptris_document_serialize(raw, _ffi.ffi.NULL)
        text = (
            _ffi.ffi.string(ptr).decode("utf-8", "replace")
            if ptr != _ffi.ffi.NULL else ""
        )
        if ptr != _ffi.ffi.NULL:
            _ffi.lib.leptris_free_string(ptr)
        _ffi.lib.leptris_document_free(raw)
        if not text:
            return None
        return Document.parse(text)
