# 13 — v2: the last platform (free-threaded) + 3.15 verification

1. Free-threaded CPython (cp313t/cp314t) — DECISION + audit:
   - Audit the accel's global state under Py_GIL_DISABLED:
     * Fns table: written once at bind() then read-only — safe IF
       bind happens-before any threaded use (module import order
       guarantees it today; document as a contract).
     * bound flag: int, set-once — fine.
     * Registries: per-document linked lists MUTATED on element
       creation — the real hazard. Options: per-registry mutex
       (small, contention only across threads sharing a document —
       which free-threading users shouldn't do anyway per the
       one-doc-per-thread contract), or document the contract and
       rely on it.
   - Build: Py_LIMITED_API 0x030D + Py_GIL_DISABLED, cibuildwheel
     CIBW_ENABLE=cpython-freethreading, separate cp313t-abi3 wheels.
   - Gate: a contention bench (8 threads, one doc per thread) must
     show no corruption AND no regression on the GIL build.
   - Until decided: README already documents unsupported.

2. CPython 3.15: cp39-abi3 wheels load on future CPython by design.
   Add a CI verification leg at first 3.15 beta (allowed-failure
   until GA), so a stable-API break is caught before users do.

3. SAX drain (stretch): records buffer decode is a Python loop;
   a C-side drain dispatching handler methods via the C API could
   take it 2-3x. Only if streaming users ask — measure first.

## Audit result (2026-09-15, shipped with 1.9.165.1)

- **Fns table**: written once at `bind()` during `leptris.element`
  import, read-only afterwards. Import-order guarantees
  happens-before any thread touches the binding — recorded in the
  accelerator header comment as a CONTRACT, not an accident.
- **`bound` flag**: int, set-once at bind — benign.
- **Registries**: per-document linked lists, MUTATED on every
  element wrapper creation and invalidated wholesale on close().
  This is the free-threading hazard. The binding's documented
  concurrency contract is one-document-per-thread; under that
  contract each registry is single-threaded and a mutex is pure
  overhead. RECOMMENDATION: ship cp313t wheels gated on a
  contention bench that ENFORCES the one-doc-per-thread contract
  (8 threads x own doc), plus a mutex behind an #ifdef
  Py_GIL_DISABLED if the audit later finds shared-document
  mutation. Awaiting go/no-go — wheels NOT shipped yet.
- **3.15 canary**: live in ci.yml (`future-python` job,
  3.15.0-alpha.3, continue-on-error — a forward-compat tripwire,
  never a merge gate).

## Decision (2026-09-15): SHIPPED

cp314t wheels on all 8 platforms (release matrix `ft-*` legs,
CIBW_ENABLE=cpython-freethreading; version-specific builds — the
3.9 limited API predates free-threading). The CI 3.14t leg runs
the full suite + tests/test_threading.py (the contract spec).
Found and fixed while shipping:

- sax.py's shared recorder raced under threads (cffi RELEASES the
  GIL around C calls — the "safe because GIL" assumption was wrong
  on every build); now lock-serialized.
- leptris/leptris#1079: engine twin-compile freed the bytecode the
  caller then ran (segfault in vm_run via eval_with_vars_context;
  ~1/3 runs of the 16-thread repro). Fixed upstream (PR #1081);
  the binding thread spec re-verifies on adoption.
