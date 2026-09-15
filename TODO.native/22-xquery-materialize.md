# 22 — XQuery result materialization in one C call (CONDITIONAL)

XQuery results still convert through leptris/_results.py — per-node
cffi accessors (the tax plan_convert killed for Plan walks). The
mirror is exactly the proven shape: a C entry consuming the
LeptrisXPathResult nodeset batch (Fns.xpath_result_get_nodes) +
element_from_parts_reg, i.e. reuse finish_result's machinery for
the XQuery entry.

CONDITION: only build it if the new "xquery eval" bench row shows
the binding share (conversion) is a meaningful slice of the row —
XQuery is cold for most users and the engine dominates. Measure
first (item 21); ship only on evidence, else record the numbers
and close.

## Outcome (2026-09-15)

Both conditionals fired GO on measurement: XQuery conversion was
42% of the row (accel.xquery_eval: 201 -> 143us); the SAX drain —
measured while adding the rows — was 91% of the sax row
(accel.sax_drain: 840 -> 194us; leptris now AHEAD of lxml).
Shipped in 1.9.171.0. Port notes: SAX handler methods resolve
lazily per kind (the Python loop raises AttributeError only when
an event's method is missing — pinned by the protocol spec);
start_prefix_mapping carries (prefix, uri).
