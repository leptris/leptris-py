# 10 — v2 audit: what actually remains after the v1 arc

Verified against the code (not memory):

ALREADY DONE (no action):
- SAX uses the engine event-recorder transport (sax.py; the ~2.5us
  libffi-callback cost was killed pre-v1). Residual: the Python
  drain loop over cffi records — real but second-order.
- itertext is C (list returned from C, wrapped in iter).
- Tagged iter filtered in the C cursor. Serialize-with-options in C.
- Plan conversion one C call (3.3x ahead of lxml).
- Wheels vendored on 9 platforms; sdist compiles the bundled engine
  (build hook before build_py); DEFAULT pip resolve fixed (the
  interim 1.2.0-1.27.1 line yanked — PEP 440 ordering bug).

REMAINING (binding-side, in expected-value order):
1. xpath-with-variables plain path: per-variable cffi set_* calls +
   cffi per-node result conversion (the no-vars path is all-C; the
   compiled-class vars path is all-C; the PLAIN path is not).
2. Mixed nodesets bail to the cffi engine path (rare).
3. Allocation micro-cost: PyDict_SetItemString re-creates key
   strings on every Plan walk + nodeset conversion (yeptris's
   interned-key cache pattern: 8-byte-prefix cache, keys <= 48
   bytes; probe is memcmp, no unicode introspection — 3.9 floor).
4. SAX drain loop (see above).
5. Free-threaded CPython wheels (cp313t) — the ONE missing platform.
6. CPython 3.15 verification leg.

ENGINE-WALLED (upstream's lane, adopt when fixed — do NOT re-litigate):
#563 iterparse fixed cost, #564 ns eval ~18x raw, #565 variables
~79x raw, #682 key() 0.51-0.59x + pattern dispatch ~2.6x vs
libxslt, #1066 xsl:iterate param correctness.
