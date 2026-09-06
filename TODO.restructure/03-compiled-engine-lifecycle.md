**STATUS: DONE 2026-09-07 — leptris/_engine.py CompiledSource; XSLT/XQuery refactored; RelaxNG-ready.**

# 03 — DRY/OCP: one lifecycle for compiled language sources (P1)

## Problem
`XSLT` and `XQuery` duplicate the compile-once lifecycle: encode →
FFI parse → NULL → `leptris_last_error()` detail (with the NULL
fallback message) → raise; `__del__` guarded free. Two copies today,
RelaxNG (#878) is announced as the third — the seam is real.

## Plan
A `CompiledSource` base in `leptris/_engine.py` owning the lifecycle;
subclasses declare only `_parse`, `_free`, `_label`, `_error_class`
and their evaluation method (open for extension, closed for
modification). Deletion test: removing it re-scatters the lifecycle
into 3+ modules — it concentrates complexity.

## Acceptance
XSLT/XQuery keep byte-identical public behavior; the shared error
detailing lives once; suite green.
