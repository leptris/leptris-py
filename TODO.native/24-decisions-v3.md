# 24 — v3 decision record

- PyPy/GraalPy: UNSUPPORTED, unchanged. Single-mode (accelerator
  required) is the product; a pure-cffi fallback would fork every
  hot path for a runtime nobody has asked for.
- API-mode cffi (compile the cdef at wheel-build time to drop the
  runtime cffi dep + import-time cdef parse): REJECTED — the
  remaining cffi surface is cold-path only, import time is already
  at lxml parity, and API-mode couples the wheel build to the
  engine headers for zero measured gain.
- cp313t wheels: DEFERRED — CPython recommends 3.14t for
  free-threading; revisit only on user demand.
- Engine-walled rows (#563/#564/#565/#682/#1066): upstream's lane;
  the binding play is adopt-fast, measure (item 21 rows), and file
  with repros — all of which now has precedent (#1079/#1081).
