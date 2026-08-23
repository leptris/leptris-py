"""Exception types for leptris."""

from __future__ import annotations

from . import _ffi


class LeptrisError(Exception):
    """Base error for leptris operations."""


class ParseError(LeptrisError):
    """XML parsing failed (lxml's etree.XMLSyntaxError equivalent)."""


class XPathError(LeptrisError):
    """XPath evaluation failed."""


def status_message(status: int) -> str:
    """Human-readable text for a LeptrisStatus code, plus the
    thread-local last error when one is recorded."""
    ffi = _ffi.ffi
    text = None
    msg = _ffi.lib.leptris_error_message(status)
    if msg != ffi.NULL:
        text = ffi.string(msg).decode("utf-8", "replace")
    if not text:
        text = f"status {status}"
    last = _ffi.lib.leptris_last_error()
    if last != ffi.NULL:
        detail = ffi.string(last).decode("utf-8", "replace")
        if detail:
            return f"{text}: {detail}"
    return text
