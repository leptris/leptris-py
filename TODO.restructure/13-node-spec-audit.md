**STATUS: DONE 2026-09-07 — `TestNode` red-first specs added for every public method (kind is_*, content, traversal, child_count, as_element, closed-contract). Module's pure Python, no probing.**

# 13 — Node module spec coverage (P2)

## Problem
`leptris/node.py` is the substrate for non-Element DOM views (text,
comment, CDATA, PI, doctype). 14 public methods, no `getattr`/
`hasattr` (clean), no `_check_alive` semantics outside the existing
one. Direct method-host targets: minimal surface, easy to spec.

## Plan
`TestNode` adding one spec per public method (is_* predicates,
content dispatching on kind, traversal ordering, child_count vs
traversal, the close contract).

## Acceptance
`TestNode` green; `node.py` is fully behavior-pinned.
