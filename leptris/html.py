"""Tolerant HTML parsing (libleptris 1.9.75+), lxml HTMLParser-shaped.

Implied end tags (p/li/td/tr/...), void elements, raw-text
script/style, unquoted attribute values, case-insensitive tag and
attribute names, the HTML named-entity table, and a synthesized
<html>/<body> wrapper — structure is byte-exact lxml
etree.HTMLParser output (since libleptris 1.9.76). Malformed input never fails the parse; it
degrades to text. The result serializes and queries (XPath, XSLT)
like any document.
"""

from . import _ffi
from .document import Document
from .element import _accel
from .error import ParseError


def document(html) -> Document:
    """Parse HTML into a Document (use as a context manager)."""
    if isinstance(html, str):
        html = html.encode("utf-8")
    status = _ffi.ffi.new("int*")
    ptr = _ffi.lib.leptris_parse_html_string(html, len(html), status)
    if ptr == _ffi.ffi.NULL:
        raise ParseError("HTML parse produced no nodes")
    registry = _accel.new_registry()
    return Document._from_parts(
        int(_ffi.ffi.cast("uintptr_t", ptr)), registry
    )


def fromstring(html):
    """Parse HTML; returns the first element of the fragment."""
    return document(html).getroot()
