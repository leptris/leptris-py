"""leptris — Python bindings for libleptris, shaped like lxml.

Usage:

    from leptris import fromstring

    root = fromstring("<root><item>hi</item></root>")
    print(root.tag)

Requires libleptris on the library search path (or LEPTRIS_LIB_PATH).
"""

from __future__ import annotations

__version__ = "1.19.0"

from . import sax
from .api import XML, c14n, fromstring, iterparse, libleptris_version, parse, tostring
from .document import Document
from .element import Element
from .error import LeptrisError, ParseError, XPathError
from .xpath import XPath
from .node import Node

__all__ = [
    "Document",
    "Element",
    "Node",
    "LeptrisError",
    "ParseError",
    "XPathError",
    "XML",
    "XPath",
    "c14n",
    "iterparse",
    "fromstring",
    "libleptris_version",
    "parse",
    "tostring",
    "sax",
]
