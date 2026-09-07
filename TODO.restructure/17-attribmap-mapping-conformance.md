**STATUS: DONE 2026-09-07 — Mapping registration + full protocol method set + read-only contract pinned (`TestAttribMapMappingConformance`).**

# 17 — _AttribMap Mapping conformance (P2)

## Problem
`Element.attrib` is documented as a read-only Mapping but the
protocol conformance (isinstance registration, derived methods,
mutability rejection) was never spec'd.

## Plan
Specs: `isinstance(attrib, collections.abc.Mapping)`; len/iter/
getitem/keys/values/items/get/in; TypeError on item assignment and
deletion.

## Acceptance
Specs green; the Mapping contract cannot silently regress.
