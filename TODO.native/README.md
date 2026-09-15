# TODO.native — the acceleration + zero-setup arc

Law: the FFI tax is per-call marshaling and per-node wrapping.
Every win collapses loops of FFI calls into one C call that returns
finished Python structures.

- 00 — benchmark rows (measure first)
- 01 — Plan result accelerator (one C call per walk)
- 02 — read-path mopup (tagged iter, serialize-options)
- 03 — sdist zero-setup (bundle lib source, build at install)
- 04 — runtime decisions (PyPy, free-threaded, 3.15+)

- 10 — v2 audit (what actually remains; the honest short list)
- 11 — v2: plain xpath-with-variables in one C call
- 12 — v2: interned-key cache for Plan dict building
- 13 — v2: free-threaded decision + 3.15 leg + SAX drain stretch
