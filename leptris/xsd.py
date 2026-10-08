"""W3C XML Schema (XSD) — tier 1 (libleptris 1.9.319+, #1075):
compile a schema and validate lexical values.

Tier-1 scope: the top-level declaration model (xs:element /
xs:attribute / xs:simpleType / xs:complexType / xs:group /
xs:attributeGroup / xs:notation), built-in datatype lexical
validation, user simpleType validation with restriction facets, and
INSTANCE VALIDATION with enumerated errors (slices 3+4,
libleptris 1.9.321+ — element declarations, attribute rows with
typed values, text lexical checks, and content models via NFA).
Identity constraints are later slices.
"""

from __future__ import annotations

from . import _engine, _ffi
from .error import XSDError


class XSD(_engine.CompiledSource):
    """A compiled XSD schema: declaration model plus lexical
    validation of built-in and user simple types."""

    @staticmethod
    def _parse(encoded, length):
        # xsd_compile returns an ERROR-CARRYING handle on failure
        # (xsd_error says why) — the compiled-source base raises on
        # NULL only, so the error path is surfaced by __init__ via
        # error() below, and the handle still needs freeing.
        return _ffi.lib.leptris_xsd_compile(
            encoded, length, _ffi.ffi.NULL
        )

    _free = _ffi.lib.leptris_xsd_free
    _label = "XSD schema"
    _error = XSDError

    def __init__(self, text):
        super().__init__(text)
        if self.error() is not None:
            detail = self.error()
            handle = self._handle
            self._handle = None
            if handle is not None:
                _ffi.lib.leptris_xsd_free(handle)
            raise XSDError(f"XSD schema invalid: {detail}")

    def error(self):
        """The last compile error detail, or ``None`` when the
        schema is valid (engine-owned; lives until :meth:`close`)."""
        char = _ffi.lib.leptris_xsd_error(self._handle)
        return (
            _ffi.ffi.string(char).decode("utf-8", "replace")
            if char != _ffi.ffi.NULL
            else None
        )

    @property
    def declaration_count(self) -> int:
        """Top-level schema declarations compiled (0 is valid)."""
        return _ffi.lib.leptris_xsd_declaration_count(self._handle)

    def valid_builtin(self, builtin: str, lexical: str) -> bool | None:
        """Validate ``lexical`` against the built-in datatype named
        ``builtin`` (the ``"xs:NAME"`` reference spelling).

        Returns ``True``/``False``; ``None`` when the name is not in
        the tier-1 built-in table.
        """
        rc = _ffi.lib.leptris_xsd_builtin_valid(
            builtin.encode("utf-8"), lexical.encode("utf-8")
        )
        return None if rc == -1 else bool(rc)

    def validate(self, document_or_element) -> bool:
        """Validate a Document (or an Element via its document)
        against the schema: element declarations by name, attribute
        rows (required use + typed values, lenient qualified
        spellings), text lexical checks for simple-typed elements,
        and child content models.

        Failures accumulate on the schema and enumerate through
        :attr:`error_log` (the next :meth:`validate` replaces them).

        Slice-4 boundary (leptris/leptris#1075): the root element's
        own typed attributes are lexical-checked; nested element
        attributes are checked for required-use and structure but
        not lexically yet.

        .. versionadded:: 1.9.321.0
        """
        document = self._document(document_or_element)
        rc = _ffi.lib.leptris_xsd_validate(
            self._handle, document._cd()
        )
        if rc == -1:
            raise XSDError("xsd_validate: bad arguments")
        return bool(rc)

    @property
    def error_log(self):
        """Every failure from the last :meth:`validate` call (empty
        for a valid document), as engine-templated strings."""
        count = _ffi.lib.leptris_xsd_error_count(self._handle)
        out = []
        for i in range(count):
            char = _ffi.lib.leptris_xsd_error_at(self._handle, i)
            out.append(
                _ffi.ffi.string(char).decode("utf-8", "replace")
                if char != _ffi.ffi.NULL
                else ""
            )
        return out

    def valid(self, type_name: str, lexical: str) -> bool | None:
        """Validate ``lexical`` against a user simpleType compiled
        into this schema, by local name — restriction chains
        validate every hop's facets.

        Returns ``True``/``False``; ``None`` when the schema has no
        such simpleType.
        """
        rc = _ffi.lib.leptris_xsd_simple_valid(
            self._handle,
            type_name.encode("utf-8"),
            lexical.encode("utf-8"),
        )
        return None if rc == -1 else bool(rc)
