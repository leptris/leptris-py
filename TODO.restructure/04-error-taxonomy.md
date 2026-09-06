**STATUS: DONE 2026-09-07 — XSLTError/XQueryError subclass LeptrisError; red-first specs; README row updated.**

# 04 — Semantic error taxonomy per engine (P1)

## Problem
Compile/apply failures of XSLT and XQuery raise bare `LeptrisError`.
lxml parity says `etree.XSLTError` exists — our taxonomy is missing
the domain layer (MECE gap: one error type per failure domain).

## Plan
- `XSLTError(LeptrisError)`, `XQueryError(LeptrisError)` in
  `error.py`; engines raise their domain type (compile and apply).
- Backward compatible: both subclass `LeptrisError`, so existing
  `except LeptrisError` code is unaffected.

## Acceptance
Red-first specs: XSLT compile failure raises `XSLTError`, XQuery
parse failure `XQueryError`; both still caught as `LeptrisError`.
