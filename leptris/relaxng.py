"""RELAX NG validation (libleptris 1.9.115+): compile a schema
once, validate any number of documents — the core grammar subset
(element/attribute/text/data/value/choice/group/interleave/
repeats/ref), with Jing-compatible failure messages.
"""

from __future__ import annotations

from . import _engine, _ffi
from .document import Document
from collections import namedtuple

from .error import RelaxNGError

RelaxNGErrorEntry = namedtuple("RelaxNGErrorEntry", ["line", "column", "message"])
RelaxNGErrorEntry.__doc__ = "One RELAX NG validation failure (Jing-compatible position)."
RelaxNGErrorEntry.__repr__ = lambda self: (
    f"RelaxNGErrorEntry(line={self.line}, column={self.column}, "
    f"message={self.message!r})"
)


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
        """Every failure from the last :meth:`validate` call (empty
        for a valid document), as :class:`RelaxNGErrorEntry` records
        with Jing-compatible ``line``/``column``/``message`` —
        libleptris 1.9.179+ accumulates them (#878); older engines
        surface only the first failure as a pre-parsed entry.

        .. versionchanged:: 1.9.181.0
            Returns the full list instead of the first failure's
            ``"line:col: error: message"`` string."""
        lib, ffi = _ffi.lib, _ffi.ffi
        count = lib.leptris_rng_error_count(self._handle)
        if count:
            entries = []
            for i in range(count):
                message = lib.leptris_rng_error_message(self._handle, i)
                entries.append(
                    RelaxNGErrorEntry(
                        line=lib.leptris_rng_error_line(self._handle, i),
                        column=lib.leptris_rng_error_column(self._handle, i),
                        message=ffi.string(message).decode("utf-8", "replace")
                        if message != ffi.NULL
                        else "",
                    )
                )
            return entries
        message = lib.leptris_rng_error(self._handle)
        if message == ffi.NULL:
            return []
        text = ffi.string(message).decode("utf-8", "replace")
        head, _, msg = text.partition(": error: ")
        line, _, column = head.partition(":")
        try:
            return [
                RelaxNGErrorEntry(
                    line=int(line), column=int(column), message=msg
                )
            ]
        except ValueError:
            return [RelaxNGErrorEntry(line=0, column=0, message=text)]
