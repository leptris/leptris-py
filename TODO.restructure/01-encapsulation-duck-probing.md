**STATUS: DONE 2026-09-07 — xpath.py/api.py/element.py probes replaced with typed access; TypeError spec pinned; accepted-idioms list preserved above.**

# 01 — Encapsulation: eliminate duck-typed attribute probing (P0)

## Problem
`respond_to?`-style capability probing (Python: `getattr(x, "attr", None)`
as a TYPE test) hides type errors until runtime and couples callers to
internal shape:

- `xpath.py:253-255` — `getattr(document, "_raw_addr", None)` +
  `getattr(element, "_raw", None) or 0` in the fast-path dispatch
- `api.py:81` — `getattr(elem, "_raw", None)` in `tostring`
- `element.py:142` — `getattr(self, "_raw", None)` in `find`

## Plan
Replace with explicit typing: attribute access on known types,
`isinstance` where the parameter genuinely admits two types.

## Accepted (kept, with reasons — do not re-flag)
- `hasattr(source, "read")` (api.py, document.py): file-like PROTOCOL
  dispatch (any `read()`-bearing object), not a type test — the Python
  file protocol is defined by capability.
- `getattr(self, "_handle", None)` in `__del__`/`close()`: partial-init
  safety when `__init__` raised before assigning slots.
- `element.py:188` attach-rule `getattr(...) is getattr(...)`: the
  documented self-describing-bind invariant.
- `element.py:280` symbol-by-name lookup: the Fns positional-bind
  protocol itself.

## Acceptance
No `getattr(..., default)` used as a type test; suite green; a
`TypeError` spec pins the wrong-argument contract on `XPath()`.
