**STATUS: DONE 2026-09-07 — README Layout + CLAUDE.md architecture list carry `_engine.py`/`_results.py`; the #875 advisory REMOVED (fix adopted in 1.9.97, golden shipped). Declined-with-reason ledger appended below.**

# 11 — Documentation sync + declined-alternatives ledger (P2)

## Reviewed and declined (do not re-litigate without new evidence)
- **Parse-options flags object** (`Document.parse(**opts)` → a
  composed flags value): three booleans, fixed lxml surface; an
  options object adds a layer without a fourth consumer.
- **Moving the Fns bind machinery out of `element.py`**: the attach
  is deliberately adjacent to the C type creation; relocation is
  churn-negative (review #3 precedent).
- **Coverage tooling in CI**: the spec surface is audited per-module
  (reviews #4-#8, 10, this file); a threshold gate would be
  ceremony, not signal.
