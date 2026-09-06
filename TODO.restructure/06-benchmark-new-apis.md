**STATUS: ROW DONE 2026-09-07 — `parse html` row wired vs lxml HTMLParser; FIRST RECORDING PENDING quiet window (loadavg guard; standing reason). 1.9.94 memo re-measure same window.**

# 06 — Benchmark coverage for the new APIs (P2)

## Problem
`benchmarks/matrix.py` predates `leptris.html` — HTML parse has no
comparative row although lxml's HTMLParser is the natural rival
(XQuery has no lxml counterpart; it stays out of the comparative
matrix).

## Plan
Add a `parse html` row (entity-light fixture, same iteration budget)
tracking leptris.html.fromstring vs lxml HTMLParser. Re-measure the
1.9.94 `get_document` memo effect in the same quiet window (deferred
from the adoption pass — machine was contended).

## Acceptance
Matrix emits the row; quiet-run recorded or the deferral noted with
the standing load-guard reason.
