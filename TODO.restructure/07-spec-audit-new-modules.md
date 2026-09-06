**STATUS: DONE 2026-09-07 — bytes-input, wrong-type TypeError, closed-document specs; the closed-document spec caught a REAL use-after-free (XQuery on closed doc crashed) — fixed by the CompiledSource guard.**

# 07 — Spec audit: xquery.py, html.py surface (P2)

## Problem
The two newest modules landed with happy-path goldens; the
contract's edges (bytes input, wrong-type arguments, reuse-after-
close for engines) need explicit specs.

## Plan
- `XSLT(b"...")` / `XQuery(b"...")` bytes-input specs (the lifecycle
  decodes; pin it).
- `XPath()` on a non-Document/Element raises `TypeError` (pins the
  typed contract from item 01).
- `XQuery` evaluation against a CLOSED document raises (the engine
  seam must fail loudly, not probe silently).

## Acceptance
New specs green; full suite green.
