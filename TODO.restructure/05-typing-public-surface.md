**STATUS: DONE 2026-09-07 — public signatures annotated across api/html/xquery/xslt.**

# 05 — Complete type annotations on the public surface (P2)

## Problem
Annotations are inconsistent across `api.py`, `xpath.py`, `xquery.py`,
`xslt.py`, `html.py` — the public contract is not machine-checkable.

## Plan
Annotate public function/method signatures and return types across
the five surface modules. Internal hot paths stay untouched (typing
churn there is noise, not contract).

## Acceptance
Public signatures annotated; suite green (annotations are inert).
