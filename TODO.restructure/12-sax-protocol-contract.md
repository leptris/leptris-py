**STATUS: DONE 2026-09-07 — direct-call dispatch verified (zero duck probing); the "raising on unhandled callback" contract codified as a spec to prevent future drift to optional-capability dispatch.**

# 12 — SAX protocol: raise-not-skip (P1)

## Problem
`sax._drain` calls user callbacks directly (`handler.start_element(...)`).
A user handler missing that method raises AttributeError — unlike
lxml's silent skip on missing target methods (capability
dispatch). Both are defensible; ours is the explicit Pythonic choice
and a *contract* a spec must lock in so future "convenience" changes
don't silently diverge.

## Accepted (kept, no churn)
- Zero `getattr`/`hasattr` in `sax.py` — the dispatch is direct.
- `hasattr(source, "read")` file-like protocol (idem in `document.parse`)
  is capability dispatch for file objects — Python idiom, not a type
  test; rule does not apply.

## Plan
Red-first specs asserting AttributeError on missing handler methods,
plus the optional-callback shape (None vs missing-method). No code
change.

## Acceptance
SAXHandler coverage complete; contract pinned.
