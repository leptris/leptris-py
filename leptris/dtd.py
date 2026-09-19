"""DTD validation (libleptris 1.9.202+): compile a DTD once,
validate any number of documents.

Two DTD sources: standalone text (:class:`DTD`), or a document's
DOCTYPE internal subset (:meth:`DTD.from_document` — owned by the
document, never freed here). External subsets and external parameter
entities use application-owned I/O (:meth:`parse_external_subset`,
:meth:`set_pe_loader`); the engine never touches the filesystem.
"""

from __future__ import annotations

from collections import namedtuple

from . import _engine, _ffi
from .error import DTDError

DTDErrorEntry = namedtuple(
    "DTDErrorEntry", ["message", "element", "line", "column"]
)
DTDErrorEntry.__doc__ = (
    "One DTD validation failure: the engine's message, the offending "
    "element name (None when the engine does not attribute one), and "
    "line/column where available."
)
DTDErrorEntry.__repr__ = lambda self: (
    f"DTDErrorEntry(message={self.message!r}, element={self.element!r}, "
    f"line={self.line}, column={self.column})"
)

# PE-loader buffers must come from the same libc heap the engine
# free()s from (leptris/leptris#1217 tracks a first-class allocator
# export). A private FFI handle keeps libc declarations out of the
# drift-gated cdef mirror: dlopen(None) covers POSIX; the Windows
# wheels build the engine with MSVC /MD, so ucrtbase carries its
# heap (msvcrt as a legacy fallback).
try:
    from cffi import FFI as _CFFI

    _libc_ffi = _CFFI()
    _libc_ffi.cdef("void* malloc(size_t); void free(void*);")
    _libc = None
    for _candidate in (None, "ucrtbase.dll", "msvcrt.dll"):
        try:
            _libc = _libc_ffi.dlopen(_candidate)
            break
        except OSError:
            continue
except Exception:  # pragma: no cover
    _libc = None


def _noop_free(_handle):
    pass


class DTD(_engine.CompiledSource):
    """A compiled DTD (lxml's ``etree.DTD`` equivalent)."""

    __slots__ = ("_owned", "_owner", "_last_error", "_pe_keepalive")

    _label = "DTD"
    _error = DTDError

    @staticmethod
    def _parse(encoded, length):
        return _ffi.lib.leptris_dtd_parse(encoded, length)

    _free = _ffi.lib.leptris_dtd_free

    @classmethod
    def from_file(cls, path) -> "DTD":
        """Compile a DTD from a file path."""
        with open(path, "rb") as handle:
            return cls(handle.read())

    @classmethod
    def from_document(cls, document) -> "DTD":
        """The document's DOCTYPE internal subset.

        The handle is owned by the document: it lives until the
        document closes and is never freed through this wrapper —
        which pins the document for exactly that lifetime. For a
        document without a DOCTYPE the engine attaches an empty
        DTD — the handle for :meth:`parse_external_subset`.
        """
        handle = _ffi.lib.leptris_document_get_dtd(document._cd())
        if handle == _ffi.ffi.NULL:
            raise DTDError("document DTD unavailable")
        obj = cls.__new__(cls)
        obj._source = None
        obj._handle = handle
        obj._owned = True
        obj._owner = document
        obj._last_error = None
        obj._pe_keepalive = None
        return obj

    def parse_external_subset(self, source) -> None:
        """Merge an external subset's declarations into this DTD.

        First declaration of a name wins, so an existing internal
        subset is never overridden (XML 1.0).
        """
        if isinstance(source, str):
            source = source.encode("utf-8")
        elif isinstance(source, (bytearray, memoryview)):
            source = bytes(source)
        rc = _ffi.lib.leptris_dtd_parse_external_subset(
            self._handle, source, len(source)
        )
        if rc != 1:
            raise DTDError("external subset could not be parsed")

    def set_pe_loader(self, loader) -> None:
        """Register a loader for external parameter entities.

        ``loader(system_id: str) -> bytes | None`` — return the
        resource's text, or None for "unavailable" (the reference is
        skipped). Must be registered before the DTD content that
        references the entities is parsed. ``None`` clears it.
        """
        lib, ffi = _ffi.lib, _ffi.ffi
        if loader is None:
            self._pe_keepalive = None
            lib.leptris_dtd_set_pe_loader(self._handle, ffi.NULL, ffi.NULL)
            return
        if _libc is None:  # pragma: no cover
            raise DTDError(
                "parameter-entity loader requires a libc allocator"
            )

        def trampoline(_user_data, system_id, out_len):
            name = (
                ffi.string(system_id).decode("utf-8", "replace")
                if system_id != ffi.NULL
                else ""
            )
            data = loader(name)
            if not isinstance(data, (bytes, bytearray)):
                return ffi.NULL
            data = bytes(data)
            buf = _libc.malloc(len(data) + 1)
            if buf == ffi.NULL:
                return ffi.NULL
            ffi.memmove(buf, data, len(data))
            ffi.memmove(buf + len(data), b"\x00", 1)
            out_len[0] = len(data)
            return _ffi.ffi.cast("char*", buf)

        callback = _ffi.ffi.callback(
            "char*(*)(void*, const char*, size_t*)"
        )(trampoline)
        self._pe_keepalive = (callback, loader)
        lib.leptris_dtd_set_pe_loader(self._handle, callback, ffi.NULL)

    def validate(self, document_or_element) -> bool:
        """Validate a Document (or an Element via its document).

        False failures publish to :attr:`error_log`.
        """
        document = self._document(document_or_element)
        err = _ffi.ffi.new("LeptrisDTDError*")
        valid = _ffi.lib.leptris_dtd_validate(
            document._cd(), self._handle, err
        )
        if valid == -1:
            raise DTDError("internal error during DTD validation")
        self._last_error = None
        if not valid and err.message != _ffi.ffi.NULL:
            self._last_error = DTDErrorEntry(
                message=_ffi.ffi.string(err.message).decode(
                    "utf-8", "replace"
                ),
                element=(
                    _ffi.ffi.string(err.element_name).decode(
                        "utf-8", "replace"
                    )
                    if err.element_name != _ffi.ffi.NULL
                    else None
                ),
                line=err.line,
                column=err.column,
            )
            _ffi.lib.leptris_dtd_error_free(err)
        return bool(valid)

    @property
    def error_log(self):
        """The failure from the last :meth:`validate` call (a
        one-entry list, empty for a valid document)."""
        entry = getattr(self, "_last_error", None)
        return [entry] if entry else []

    def __del__(self):
        # Document-attached handles are freed with the document.
        if getattr(self, "_owned", False):
            self._handle = _ffi.ffi.NULL
        try:
            super().__del__()
        except Exception:
            pass
