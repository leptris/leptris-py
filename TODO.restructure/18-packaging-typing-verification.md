**STATUS: DONE 2026-09-07 (verification only, no change needed) — `py.typed` present in `leptris/` AND confirmed inside the shipped PyPI wheel (1.9.103.0), wired via pyproject package-data. Round-1's public annotations are therefore visible to consumers.**

# 18 — Packaging: typed-marker verification (P2)

## Problem
Round 1 annotated the public surface and the repo carries
`leptris/py.typed` — but configured ≠ shipped. If the marker were
absent from wheels, every annotation would be invisible to
downstream type checkers (PEP 561).

## Plan
Download the current release wheel from PyPI and list its contents.

## Result
`leptris/py.typed` IS in the shipped wheel — no action. Recorded so
future audits don't re-derive it.
