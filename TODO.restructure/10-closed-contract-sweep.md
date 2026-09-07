**STATUS: DONE 2026-09-07 — sweep executed; TWO SEGFAULTS found and fixed: `find()` (Python fast path lacked `_check_alive`) and `get()` (C `elem_get_method` lacked the `check_poisoned` guard every other accessor has). `TestClosedDocumentContract` pins raise-not-crash across the public surface.**

# 10 — Closed-contract sweep: raise, never crash (P0)

## Problem
The XQuery use-after-free (fixed in 03) was one instance of a
class: any public entry point accepting a Document/Element must
RAISE `LeptrisError` on a closed document, never touch freed
memory. The contract was unverified across the surface.

## Plan
Isolated-process sweep of every public entry point against a
freshly-closed document; fix crashes; pin the whole contract in
one spec class.

## Findings
- CRASH (SIGSEGV): `Element.find` — fast path used `_raw` without
  `_check_alive`; fixed in `element.py`.
- CRASH (SIGSEGV): `Element.get` — the C `elem_get_method` was the
  one accessor missing `check_poisoned` (~5ns, the check every
  other accessor pays); fixed in `_leptrisaccel.c`.
- Correct-by-design (raise): tostring, c14n, iter, text, xpath,
  XSLT, XQuery, write, getroot, Document.xpath.

## Acceptance
`TestClosedDocumentContract` green; sweep repros now raise.
