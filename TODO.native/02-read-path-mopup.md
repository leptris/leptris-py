# 02 — read-path mopup

1. Tag filter in the C subtree cursor: iter(tag)/iterdescendants(tag)
   take the Clark-notation tag into C; compare element name/namespace
   there instead of filtering per item in Python. Target: the tagged
   iter row from ~0.9x to >=1.3x vs lxml.
2. Serialize-with-options in one C call: fold indent/xml_declaration/
   encoding flags into the accelerator's serialize entry (build the
   engine options struct in C) instead of routing through cffi when
   options are present.

## Outcome notes

1. Tagged iter: the C cursor ALREADY filters ns+local (subtree_iter's
   cursor_matches); bare and Clark tags were never Python-filtered.
   The ~0.9x row was stale; quiet-window parity with lxml (both pay
   per-item wrapper allocation). lxml itself accepts no `p:local`
   form in iter(tag), so the Python fallback for prefixed tags is a
   convenience extra, not a perf row. NO CHANGE NEEDED.
2. Serialize-with-options: see below (implemented).
