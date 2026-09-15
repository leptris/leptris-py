# 21 — engine-wave adoption + measurement hygiene

Adoption is the standing cadence, and the pin is behind:
v1.9.166-171 are out; the wave includes our #1081 bytecode UAF fix
(#1079) and further #659 HTML conformance (after-frameset etc).

1. Adopt: pin bump, crash-loop 40x, drift gate, full suite; the
   thread-contract spec (tests/test_threading.py) re-validates the
   #1081 fix on the PINNED engine in CI (incl. the 3.14t leg).
2. Bench rows for the language engines — the matrix today covers
   parse/xpath/html/iter/serialize/plan only:
   - "xslt apply" (lxml XSLT comparison — the #682 context row)
   - "xquery eval" (no lxml equivalent; absolute numbers)
   - "sax parse" and "iterparse" (lxml has both — direct rows)
   - "c14n" (lxml has it)
   These keep the engine-walled claims honest and give upstream's
   #682/#565 lanes a binding-side scoreboard. No CI perf gates —
   runner noise (PerfRegression flake precedent) makes gates lie.

## Outcome (2026-09-15, shipped as 1.9.171.0)

- v1.9.166-171 adopted; the #1079 repro confirmed clean on the
  RELEASE build (no segfault).
- Rows live: plan 106 vs lxml 445 (4.2x ahead); xslt 113 vs 50
  (the #682 wall, quantified 2.3x); xquery 143 absolute; sax 194 vs
  245 (AFTER the item-22 C drain — was 840, 3.2x behind);
  iterparse 186 vs 258; c14n 167 vs 227. Every row at-or-ahead of
  lxml except xslt (engine-walled, now measured).
