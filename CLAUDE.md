# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`leptris` — the Python binding for `libleptris` (C library: XML 1.0 parsing, XPath 1.0), built on `cffi` in **ABI mode**. Split out of the C repo (`leptris/leptris`, formerly its `bindings/python/`). Sibling repos: `leptris/leptris` (the C library itself) and `leptris-ruby` (the Ruby binding twin — its `benchmark/` matrix is the model for the pending Python benchmark matrix).

**Lockstep versioning:** the package version tracks libleptris exactly (library 1.2.0 ↔ package 1.2.0). The version lives in three places that must agree at release time: `pyproject.toml`, `leptris/__init__.py` (`__version__`), and `libleptris-version.txt` (the pinned library version CI builds against).

## Prerequisite: the shared library

The binding does NOT bundle the C library. Tests and runtime need `libleptris` (`libleptris.dylib` / `.so` / `.dll`) resolvable by the loader in `leptris/_ffi.py`:

- `LEPTRIS_LIB_PATH` must name the library **file**, not its directory — the loader `dlopen`s the path verbatim.
- Fallbacks: plain install names (`libleptris.dylib` etc.), then `../../../build/src/` relative to the package (a C-repo checkout build).

Build from a C-repo checkout:

```bash
cmake -B build-shared -S /path/to/leptris -DLEPTRIS_BUILD_SHARED=ON
cmake --build build-shared --target leptris_shared
export LEPTRIS_LIB_PATH=/path/to/leptris/build-shared/src/libleptris.dylib
```

Or as CI does — fetch the release tarball pinned in `libleptris-version.txt` and build it (see `.github/workflows/ci.yml`, "Build libleptris from the pinned release tarball").

## Commands

```bash
# full test suite (requires LEPTRIS_LIB_PATH set)
python -m pytest tests/ -q

# single test / single class
python -m pytest tests/test_binding.py::TestXPath::test_count
python -m pytest tests/test_binding.py::TestElement

# build sdist + wheel
python -m pip install build && python -m build

# FFI mirror drift gate (needs a libleptris checkout/tarball with src/include/)
python scripts/check_ffi_mirrors.py /path/to/libleptris
```

## Architecture

Single cdef mirror, thin typed wrappers:

- `leptris/_ffi.py` — the ONLY place C is touched. The `cdef` hand-mirrors libleptris's public headers (`src/include/leptris/` in the C repo). Also defines node-type and XPath-result-type constants (`NODE_ELEMENT`, `XPATH_NODESET`, …).
- `leptris/document.py` — `Document`: owns the whole tree + memory pool. `parse()`, `root`, `serialize()`, `process_xinclude()`, `xpath()`, `close()`.
- `leptris/element.py` — `Element`: typed view for element nodes; never freed directly (the Document owns them). Keeps a `_document` reference so the pool cannot be freed while any wrapper is alive.
- `leptris/node.py` — `Node`: generic traversal over ALL node types (text/comment/CDATA/PI); `as_element()` converts to the typed view.
- `leptris/xpath.py` — `XPath.evaluate`: nodesets → `list[Element]`, number → `float`, string → `str`, boolean → `bool`.
- `leptris/error.py` — `LeptrisError`, the single exception type.

Cross-module imports are done locally inside methods (e.g. `from .element import Element` in `document.py`) to avoid circular imports.

### Memory model rules (the easy way to introduce segfaults/leaks)

- Strings returned by accessors are document-owned and die with the document — always `ffi.string(...).decode()` at the boundary into a Python `str`.
- `char*` returns from `leptris_document_serialize` / `leptris_xpath_result_string` are separately allocated and must be released with `leptris_free_string`.
- `Document.close()` is the contract; `__del__` is only a CPython refcounting safety net. Tests use the context manager (`with Document.parse(...) as doc:`).
- Wrappers are created fresh on every access — no identity caching, so compare by name/attribute, not `is`.

### FFI mirror drift gate

`scripts/check_ffi_mirrors.py` parses the C public headers (source of truth) and the cdef in `_ffi.py`, failing CI on PHANTOM symbols (declared but not in headers), ARITY mismatches, or missing REQUIRED_CORE symbols. When binding a new C function: update the cdef to match the header signature exactly, and extend the test suite. The gate runs in CI against the pinned tarball's headers.

## CI and publishing

- `.github/workflows/ci.yml` (push/PR): builds libleptris from the pinned tarball → drift gate → `pip install .[test]` → pytest, on ubuntu/macos/windows.
- `.github/workflows/release.yml`: PyPI **trusted publishing** (OIDC `id-token: write`, no stored credentials, no environment). The registered trusted publisher must match exactly: owner `leptris`, repository `leptris-py`, workflow `.github/workflows/release.yml`, no environment.
  - Triggered by `workflow_dispatch` (ships the version in `pyproject.toml`) or `workflow_call` (with `inputs.publish: true`) from the C repo's release flow — that's how each libleptris release ships the wheel.
  - Gotcha: `github.event_name` propagates from the CALLER through `workflow_call` (the caller's release job runs on `pull_request closed`), so gates key on `inputs.publish`, never on `event_name == 'workflow_call'`.

## Repo conventions

- All changes via PR to `main` — never commit, push, or merge directly to main. Never push tags.
- No AI attribution in commits, PRs, or docs.
- `build/`, `dist/`, `*.egg-info/`, `.pytest_cache/` are local artifacts; ignore them, don't commit them.
