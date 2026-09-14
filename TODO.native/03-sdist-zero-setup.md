# 03 — sdist zero-setup (the last setup hole)

Wheels are zero-setup; `pip install leptris --no-binary leptris` is
not (needs LEPTRIS_LIB_PATH). Fix:

- The sdist BUNDLES the pinned libleptris source (extracted at sdist
  build time into vendor/libleptris/ — release workflow + a local
  script; MANIFEST grafts it; never committed to the binding repo,
  no binaries ever).
- setup.py build_ext: if leptris/_vendor/ is absent AND
  LEPTRIS_LIB_PATH is unset -> cmake-build the bundled source into
  leptris/_vendor/ before building the accel. LEPTRIS_LIB_PATH stays
  an explicit override.
- A source install already compiles the accelerator, so the
  prerequisite class does not change: compiler only, no external
  library to build by hand.
- Spec: build the sdist, pip install into a clean venv with no env
  vars (macOS + linux CI legs).
