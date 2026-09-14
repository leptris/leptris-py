# 00 — benchmark rows (measure first)

Add to benchmarks/matrix.py, quiet window, min-of-N:

- plan-materialize: #185 document shape (150 records x 3 nodes,
  attrs + content). Compile Plan once; measure plan(doc) end-to-end
  and converter-only (separate timeit of _convert vs the whole call).
- tagged-iter: `for e in root.iter("item")` vs lxml (the ~0.9x row).

No numbers are claimed anywhere public from hand runs.
Status: see git history.
