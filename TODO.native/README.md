# TODO.native — the acceleration + zero-setup arc

Law: the FFI tax is per-call marshaling and per-node wrapping.
Every win collapses loops of FFI calls into one C call that returns
finished Python structures.

- 00 — benchmark rows (measure first)
- 01 — Plan result accelerator (one C call per walk)
- 02 — read-path mopup (tagged iter, serialize-options)
- 03 — sdist zero-setup (bundle lib source, build at install)
- 04 — runtime decisions (PyPy, free-threaded, 3.15+)
