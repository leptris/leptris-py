# 20 — v3 audit: the binding-side program is essentially complete

Shipped across 1.9.162.2 → 1.9.165.2 (v1, v2, 13-final). Every hot
read path is one C call; zero-setup covers 17 artifacts (8 abi3 +
8 free-threaded cp314t + source-only sdist with bundled engine);
plain `pip install leptris` resolves correctly on every platform.

Verified-already (do NOT re-plan):
- attrib items/keys/values: C bulk (AttrSink walk in the accel)
- SAX transport: engine event recorder (lock-serialized share)
- itertext: C list. Tagged iter: C-cursor filtered.
- Plan: one C call, interned keys, differential-spec'd.
- 3.15 alpha canary green; FT contract spec on a real 3.14t.

What genuinely remains (four items):
- 21: adopt the engine wave (v1.9.166-171 already carries #1081
  and #659 slices) + language-engine bench rows so "engine-walled"
  stays measured, not asserted.
- 22: XQuery result materialization in one C call — CONDITIONAL on
  the new bench row showing binding-share worth taking.
- 23: conda-forge feedstock — the one zero-setup surface left.
- 24: decision record refresh (PyPy stance unchanged; API-mode cffi
  rejected; cp313t wheels deferred pending demand).
