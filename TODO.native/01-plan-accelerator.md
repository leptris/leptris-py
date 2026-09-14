# 01 — Plan result accelerator

Problem: Plan._convert walks the LeptrisPlanResult tree through 5-6
cffi accessor calls per node (value_at/kind/name/string/count/
value_attribute) plus a Python row_matches per row — the exact
per-node FFI tax the accelerator exists to kill.

Design:
- accel.plan_shape_build(spec_tables) -> opaque shape handle. C
  copies per-plan attr-name lists + ordered rows
  {name, kind, child_index}; owned by the Plan object (freed with
  plan_shape_free).
- accel.plan_convert(result_address, shape_handle) -> finished
  nested dict/list/PlanCallback structure, built entirely in C via
  the Fns engine accessor table (9 new slots: value kind/name/
  type_tag/string/length/position/count/at/attribute). One C call
  per walk; zero Python-level marshaling.
- PlanCallback constructed in C from a cached type reference
  (passed at bind time; PyObject_CallFunctionObjArgs).
- Python converter STAYS as the reference + fallback (unaccelerated
  or engine-cold paths). Semantics ported verbatim: row-order
  correlation, unnamed collection wrappers, repeated-nested =
  implicit collection (1 -> dict, many -> list), absent row
  defaults (scalar None, collection []).

Correctness: differential specs — both converters over the same
walk result for every fixture + adversarial shapes; assert equal.

Target: >=3x on the 450-node converter bench.
