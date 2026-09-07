"""Tolerant HTML parsing (libleptris 1.9.75+), two modes since 1.9.104.

``html4`` (the default) keeps the libxml2/Nokogiri compatibility
shape — byte-exact with lxml's ``etree.HTMLParser`` on every probe
corpus to date: implied end tags, void elements, case-insensitive
names, unquoted attributes, the named-entity table, title/meta/
link/base head-lift, and a synthesized ``<html>/<body>`` wrapper.

``whatwg`` selects the WHATWG-conformant engine: additionally, a
contiguous leading run of script/style/noscript/template/basefont/
bgsound/noframes lifts into the implied ``<head>`` (html5lib corpus
conformance ~48 points higher; NOT lxml byte-compatible).

Malformed input never fails the parse; it degrades to text.
"""

from . import _ffi
from .document import Document
from .element import _accel
from .error import ParseError

_PARSE = {
    "html4": _ffi.lib.leptris_parse_html4_string,
    "whatwg": _ffi.lib.leptris_parse_html_string,
}


def document(html: "str | bytes", *, mode: str = "html4") -> Document:
    """Parse HTML into a Document (use as a context manager).

    mode: "html4" (Nokogiri/lxml byte parity, default) or "whatwg".
    """
    try:
        parse = _PARSE[mode]
    except KeyError:
        raise ValueError(
            f"unknown mode {mode!r}; expected 'html4' or 'whatwg'"
        ) from None
    if isinstance(html, str):
        html = html.encode("utf-8")
    status = _ffi.ffi.new("int*")
    ptr = parse(html, len(html), status)
    if ptr == _ffi.ffi.NULL:
        raise ParseError("HTML parse produced no nodes")
    registry = _accel.new_registry()
    return Document._from_parts(
        int(_ffi.ffi.cast("uintptr_t", ptr)), registry
    )


def fromstring(html: "str | bytes", *, mode: str = "html4"):
    """Parse HTML; returns the first element of the fragment."""
    return document(html, mode=mode).getroot()
