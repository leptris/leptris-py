# 12 — v2: interned-key cache for hot dict building

Problem: plan_convert (and any SetItemString loop) re-creates the
row/attr name string on EVERY walk — PyDict_SetItemString ->
PyUnicode_FromString per key per call. Repeated walks of the same
Plan rebuild the same key objects thousands of times.

Design (the yeptris-native pattern, proven there):
- The Plan shape handle already owns C storage per plan — extend it
  to hold a PyObject* per row/attr name, materialized ONCE at
  shape build (PyUnicode_FromString + incref).
- plan_convert switches to PyDict_SetItem with the cached key.
- Same treatment for the nodeset/attr paths if profiling shows key
  churn there (measure first — finish_result builds lists, not
  dicts; likely Plan-only).
- Cache rule from yeptris (keys <= 48 bytes benefit most; probe is
  pointer-equal after first use since dict compares cached-object
  identities) applies cleanly because Plan shapes are static.

Specs: differential specs already pin converter equality — they
cover this unchanged. Bench: plan-materialize row, repeated-walk
workload (walk same doc 1000x).
