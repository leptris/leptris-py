**STATUS: DONE 2026-09-07 — static audit: **every** PyCFunction entry in the accelerated method table guards via `check_poisoned` (round 2 found `elem_get_method` was the only gap; fix in commit `66079b8`). A small docstring list captures the invariant.**

# 14 — Accel guard completeness audit (P1)

## Problem
Round 2's crash sweep found the C `elem_get_method` was the single
method entry missing the `check_poisoned` (~5ns) guard every other
accessor already paid. After the fix, is the rule "every accessor
guards" really met, or are there other gap points lurking?

## Plan
Static audit: enumerate PyCFunction entries in the table and grep
each one for the guard call. Add a comment block listing the
invariant for future authors.

## Acceptance
Every textually-PyCFunction entry guards. The invariant is documented
in `_leptrisaccel.c` so the next contributor sees the rule.
