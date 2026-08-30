"""Module-level helpers mirroring lxml.etree's free functions."""

from __future__ import annotations

from typing import List, Optional, Union

from . import _ffi
from .document import Document, serialize_options
from .element import Element
from .error import LeptrisError, ParseError


def libleptris_version() -> str:
    """Runtime version string of the loaded libleptris."""
    value = _ffi.lib.leptris_version()
    if value == _ffi.ffi.NULL:
        return ""
    return _ffi.ffi.string(value).decode("utf-8")


def fromstring(xml) -> Element:
    """Parse XML from a str or bytes; returns the root Element."""
    return Document.parse(xml).getroot()


XML = fromstring


def parse(source) -> Document:
    """Parse XML from a file path or a file-like object.

    Unlike lxml (which supports HTTP/FTP URLs), only the local
    filesystem and file objects are accepted.
    """
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        return Document.parse(data)
    return Document.parse_file(source)


def tostring(
    element_or_document,
    *,
    encoding: Optional[str] = None,
    pretty_print: bool = False,
    xml_declaration: Optional[bool] = None,
) -> Union[bytes, str]:
    """Serialize an Element subtree or a whole Document.

    Returns bytes; pass encoding="unicode" for str (lxml convention).
    An explicit encoding implies an XML declaration unless
    xml_declaration=False.
    """
    ffi = _ffi.ffi
    if isinstance(element_or_document, Document):
        doc, elem = element_or_document, None
    elif isinstance(element_or_document, Element):
        doc, elem = element_or_document.document, element_or_document
    else:
        raise TypeError("expected an Element or Document")
    if doc.closed:
        raise LeptrisError("operation on a closed document")
    c_encoding = None if encoding in (None, "unicode") else encoding
    if (
        elem is None
        and c_encoding is None
        and not pretty_print
        and xml_declaration in (None, False)
    ):
        from .element import _accel

        data = _accel.serialize_doc(doc._raw_addr)
        if data is None:
            raise LeptrisError("serialization failed")
        return data.decode("utf-8") if encoding == "unicode" else data
    if elem is not None:
        from .element import _accel

        raw = getattr(elem, "_raw", None)
        if (
            _accel is not None
            and raw is not None
            and c_encoding is None
            and xml_declaration in (None, False)
        ):
            data = _accel.serialize_elem(
                raw, 2 if pretty_print else 0, 0
            )
            if data is None:
                raise LeptrisError("serialization failed")
            if encoding == "unicode":
                return data.decode("utf-8")
            return data
    options, _keepalive = serialize_options(c_encoding, pretty_print, xml_declaration)
    if elem is not None:
        ptr = _ffi.lib.leptris_element_serialize(elem._cd(), options)
    else:
        ptr = _ffi.lib.leptris_document_serialize(doc._cd(), options)
    if ptr == ffi.NULL:
        raise LeptrisError("serialization failed")
    data = ffi.string(ptr)
    _ffi.lib.leptris_free_string(ptr)
    if encoding == "unicode":
        return data.decode("utf-8")
    return data


def _prefix_array(prefixes: Optional[List[str]]):
    if not prefixes:
        return _ffi.ffi.NULL, []
    array = _ffi.ffi.new("const char*[]", len(prefixes) + 1)
    keepalive = [_ffi.ffi.new("char[]", p.encode("utf-8")) for p in prefixes]
    for index, buffer in enumerate(keepalive):
        array[index] = buffer
    array[len(prefixes)] = _ffi.ffi.NULL
    return array, keepalive


def c14n(
    target,
    *,
    exclusive: bool = False,
    with_comments: bool = False,
    inclusive_ns_prefixes: Optional[List[str]] = None,
    version: str = "1.0",
) -> bytes:
    """Canonical XML (C14N 1.0 or 1.1, inclusive or exclusive mode)."""
    versions = {"1.0": _ffi.C14N_1_0, "1.1": _ffi.C14N_1_1}
    if version not in versions:
        raise ValueError("version must be '1.0' or '1.1'")
    mode = _ffi.C14N_EXCLUSIVE if exclusive else _ffi.C14N_CANONICAL
    prefixes, _keepalive = _prefix_array(inclusive_ns_prefixes)
    if isinstance(target, Document):
        if target.closed:
            raise LeptrisError("operation on a closed document")
        ptr = _ffi.lib.leptris_c14n_canonicalize_ex(
            target._cd(), versions[version], mode, prefixes, int(with_comments)
        )
    elif isinstance(target, Element):
        if target.document.closed:
            raise LeptrisError("operation on a closed document")
        ptr = _ffi.lib.leptris_c14n_canonicalize_subtree_ex(
            target._cd(), versions[version], mode, prefixes, int(with_comments)
        )
    else:
        raise TypeError("expected an Element or Document")
    if ptr == _ffi.ffi.NULL:
        raise LeptrisError("canonicalization failed")
    data = _ffi.ffi.string(ptr)
    _ffi.lib.leptris_free_string(ptr)
    return data

class _BorrowedDocument:
    """Sentinel owner for borrowed iterparse elements: the iterator,
    not a Document, owns their memory."""

    closed = False
    _raw_addr = None

    def close(self):
        pass


def iterparse(source, events=("end",), *, full_document: bool = False):
    """Incrementally parse XML with bounded memory (lxml parity).

    Yields ("end", element) pairs as elements complete; each element
    (and its subtree) stays valid only until the next yield — the
    engine releases it then, keeping memory bounded by the largest
    subtree, not the document.

    By default only the root's top-level children are yielded; with
    full_document=True every element is (in completion order —
    children before parents).

    Accepts a file path or an XML str/bytes. Only "end" events are
    supported. Names are the QNames as written. Malformed or
    truncated input raises ParseError when iteration ends
    (libleptris 1.9.4+).
    """
    requested = tuple(events) if not isinstance(events, str) else (events,)
    if requested != ("end",):
        raise ValueError("only 'end' events are supported")
    from . import _ffi as _binding

    lib, ffi = _binding.lib, _binding.ffi
    mode = 1 if full_document else 0
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        iterator = lib.leptris_iterparse_new_ex(data, len(data), mode)
    else:
        import os

        path = os.fspath(source)
        if isinstance(path, str):
            path = path.encode("utf-8")
        iterator = lib.leptris_iterparse_new_file_ex(path, mode)
    if iterator == ffi.NULL:
        raise ParseError("iterparse could not start")

    sentinel = _BorrowedDocument()
    iterator_addr = int(ffi.cast("uintptr_t", iterator))
    from .element import _accel

    def generate():
        try:
            while True:
                # next + wrap in one C call; the element is borrowed
                # until the following call (the iterator's contract)
                element = _accel.iterparse_next(iterator_addr, sentinel)
                if element is None:
                    error = lib.leptris_iterparse_error(iterator)
                    if error != ffi.NULL:
                        message = ffi.string(error).decode(
                            "utf-8", "replace"
                        )
                        if message:
                            raise ParseError(message)
                    return
                yield ("end", element)
        finally:
            lib.leptris_iterparse_free(iterator)

    return generate()

