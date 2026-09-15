# 11 — v2: xpath-with-variables in one C call

Problem: Document.xpath(expr, variables={...}) (the plain path)
binds each variable via leptris_xpath_variable_set_* (one cffi call
per variable), evaluates via leptris_xpath_eval_with_vars_context,
then converts the result through leptris/_results.py — cffi per
node for nodesets. The compiled-XPath class already has
compiled_eval_vars all-C (Fns.xpath_compiled_eval_ns_vars); the
plain path deserves the same.

Design:
- accel.nodeset_vars(document_address, context_address, expression,
  bindings, vars_flat, document) mirroring nodeset_ns + the vars
  marshaling from compiled_eval (the flat [name, type, value]
  encoding exists there — reuse it verbatim).
- Element.xpath/Document.xpath: variables-present + no-accel-fallback
  routes through the new entry; _XPathEngine keeps the cffi path as
  fallback (closed documents, mixed nodesets, unbound accel).
- finish_result already handles scalar/all-element/mixed fallback.

Specs: red-first — the fast path must return identical results to
the engine path for string/number/bool vars incl. multiple vars and
nodeset results; mixed nodeset still falls back (existing spec).

Bench: the existing "xpath //book[@id=$id]" row (currently engine
path) — expect the binding share (~10us) to drop; engine #565
still caps the row overall. Report honestly.
