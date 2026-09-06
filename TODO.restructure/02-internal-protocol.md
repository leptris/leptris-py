**STATUS: DONE 2026-09-07 — protocol table added to CLAUDE.md; zero sys.path/importlib hits (grep clean).**

# 02 — Codify the package-internal protocol (P1)

## Problem
Modules cooperate through underscore seams (`_cd()`, `_raw_addr`,
`_from_parts`, `_document`, `_accel.new_registry()`). Within one
package this is the internal contract, not an encapsulation break —
but it is undocumented, so every audit re-flags it and every new
module (RelaxNG is next) rediscovers it.

## Plan (codify, don't churn)
- Document the internal protocol in the repo CLAUDE.md architecture
  section: which seams exist, what each guarantees, who may call.
- NO renaming: `_cd()` sits on hot paths; renaming buys zero
  semantics (churn-negative per review #3/#4 precedent).
- Verify no `sys.path`/`importlib` path tricks (the Python analogue
  of the require_relative rule) — the package imports follow the
  documented cross-module-local convention that avoids cycles.

## Acceptance
CLAUDE.md carries the protocol table; grep clean of path hacks.
