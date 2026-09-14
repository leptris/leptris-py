# 04 — runtime decision record

- PyPy/GraalPy: UNSUPPORTED. Single-mode (accelerator required) is
  deliberate; a pure-cffi fallback path contradicts the binding's
  purpose. Revisit only on real demand.
- Free-threaded CPython (3.13t/3.14t): abi3 wheels do not load.
  cp313t-abi3 wheels are possible (cibuildwheel cpython-freethreading)
  but need a Py_GIL_DISABLED audit of the binding's global state
  (Fns table, registries). Pending a decision + audit; documented
  unsupported meanwhile.
- CPython 3.15+: covered by design — cp39-abi3 loads on future
  CPython; verify at first beta.
