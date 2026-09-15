# 23 — conda-forge: the last zero-setup surface

pip wheels cover CPython everywhere; conda users still have no
canonical channel. Ship a conda-forge feedstock:

- recipe: build the PINNED libleptris (same cmake flags as the
  wheel vendor script) + the leptris sdist; runtests: pytest with
  the packaged lib on the PATH (LEPTRIS_LIB_PATH or staged lib).
- The bot picks up PyPI releases once the feedstock exists — zero
  per-release work after the initial PR.
- Verify at execution time that no leptris feedstock already
  exists (none as of this writing).

## Outcome (2026-09-15)

No existing feedstock (verified: anaconda.org + GitHub search).
Recipe committed at conda-forge/meta.yaml in-repo (source of
truth; the self-contained sdist makes it a plain pip build with
cmake+compilers); submitted as conda-forge/staged-recipes#34847.
After acceptance, the conda-forge bot tracks PyPI releases.
