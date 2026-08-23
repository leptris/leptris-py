"""Module-level helpers mirroring lxml.etree's free functions."""

from __future__ import annotations

from typing import List, Optional, Union

from . import _ffi
from .document import Document, serialize_options
from .element import Element
from .error import LeptrisError


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
    options, _keepalive = serialize_options(c_encoding, pretty_print, xml_declaration)
    if elem is not None:
        ptr = _ffi.lib.leptris_element_serialize(elem._cd(), options)
    else:
        ptr = _ffi.lib.leptris_document_serialize(doc._ptr, options)
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
        ptr = _ffi.lib.leptris_c14n_canonicalize_ex(
            target._ptr, versions[version], mode, prefixes, int(with_comments)
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
