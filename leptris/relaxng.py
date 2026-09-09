"""RELAX NG validation (libleptris 1.9.115+): compile a schema
once, validate any number of documents — the core grammar subset
(element/attribute/text/data/value/choice/group/interleave/
repeats/ref), with Jing-compatible failure messages.
"""

from __future__ import annotations

from . import _engine, _ffi
from .document import Document
from .error import RelaxNGError


class RelaxNG(_engine.CompiledSource):
    """A compiled RELAX NG schema (lxml's etree.RelaxNG equivalent)."""

    @staticmethod
    def _parse(encoded, length):
        return _ffi.lib.leptris_rng_parse(encoded, length, _ffi.ffi.NULL)

    _free = _ffi.lib.leptris_rng_free
    _label = "RELAX NG schema"
    _error = RelaxNGError

    @classmethod
    def from_file(cls, path) -> "RelaxNG":
        """Compile a schema from a file path."""
        source = _ffi.lib.leptris_rng_parse_file(
            str(path).encode("utf-8"), _ffi.ffi.NULL
        )
        if source == _ffi.ffi.NULL:
            raise RelaxNGError(
                f"schema file could not be parsed: {path}"
            )
        obj = cls.__new__(cls)
        obj._source = str(path).encode("utf-8")
        obj._handle = source
        return obj

    def validate(self, document_or_element) -> bool:
        """Validate a Document (or an Element via its document).

        False failures publish to :attr:`error_log` in Jing's
        ``line:col: error: message`` shape.
        """
        document = self._document(document_or_element)
        valid = _ffi.lib.leptris_rng_validate(self._handle, document._cd())
        return bool(valid)

    @property
    def error_log(self):
        """The first validation failure (Jing message shape), or
        None after a valid parse with no failed validation."""
        message = _ffi.lib.leptris_rng_error(self._handle)
        if message == _ffi.ffi.NULL:
            return None
        return _ffi.ffi.string(message).decode("utf-8", "replace")
