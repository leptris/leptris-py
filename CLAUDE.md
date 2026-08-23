# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`leptris` — the Python binding for `libleptris` (C library: XML 1.0 parsing, XPath 1.0), built on `cffi` in **ABI mode**. The API mirrors **lxml** (the way the Ruby binding mirrors Nokogiri): read-path lxml code ports with an import change; mutation/creation/iterparse are deliberately absent (libleptris is read-only) and are documented in the README "Migrating from lxml" table. Sibling repos: `leptris/leptris` (the C library) and `leptris-ruby`.

**Lockstep versioning:** the package version tracks libleptris exactly. The version lives in three places that must agree at release time: `pyproject.toml`, `leptris/__init__.py` (`__version__`), and `libleptris-version.txt` (the pinned library version CI builds against).

## Prerequisite: the shared library

The binding does NOT bundle the C library. Tests and runtime need `libleptris` resolvable by the loader in `leptris/_ffi.py`:

- `LEPTRIS_LIB_PATH` must name the library **file**, not its directory — the loader `dlopen`s the path verbatim.
- CI builds the pinned tarball into `tmp/libleptris/` (same commands work locally).

## Commands

```bash
# full test suite (requires LEPTRIS_LIB_PATH set)
python -m pytest tests/ -q

# single test / single class
python -m pytest tests/test_element.py::TestTextModel::test_cdata_merges_into_text
python -m pytest tests/test_xpath.py::TestFind

# benchmark matrix vs lxml/ElementTree/minidom (needs pip install .[bench])
python -m benchmarks.matrix

# build sdist + wheel
python -m pip install build && python -m build

# FFI mirror drift gate (needs a libleptris checkout/tarball with src/include/;
# export check also runs when LEPTRIS_LIB_PATH is set)
python scripts/check_ffi_mirrors.py /path/to/libleptris
```

## Architecture

- `leptris/_ffi.py` — the ONLY place C is touched. The `cdef` mirrors libleptris's public headers (`src/include/leptris/` + the `leptris.h` umbrella in the C repo). Node-type / XPath-result / C14N constants live here.
- `leptris/document.py` — `Document` (the ElementTree analogue): owns the tree + pool; `parse`, `parse_file`, `getroot`/`root`, `xpath`, `write`, `process_xinclude`, `close`/context manager. Also `serialize_options()` (shared by `api.tostring` and `write`).
- `leptris/element.py` — `Element`: lxml-compatible (`tag` in Clark notation, `get`/`attrib` read-only Mapping, `getparent`/`getnext`/`getprevious`, child indexing/slices, `iter`/`iterdescendants`/`itertext`, `find`/`findall`/`findtext` with `{uri}local` translation, `namespace`/`prefix`) plus `_AttribMap`.
- `leptris/node.py` — `Node`: generic DOM view over ALL node types (text/comment/CDATA/PI); the substrate for `text`/`tail` computation.
- `leptris/xpath.py` — `XPath.evaluate` (namespaces via ns sets, variables via variable sets), result conversion (nodesets → `Element` list; attribute/text selections → plain `str`), and `expand_clark_names`.
- `leptris/api.py` — module surface: `fromstring`/`XML`/`parse`/`tostring`/`c14n`.
- `leptris/sax.py` — `SAXHandler`, one-shot `parse`, `StreamingParser` (push; call `set_streaming` before the first feed — the constructor guarantees this).
- `leptris/error.py` — `LeptrisError` base; `ParseError`, `XPathError`; `status_message`.

Cross-module imports are local inside functions where needed to avoid cycles (document → element, api → document).

### Key semantic decisions (lxml parity)

- `text`/`tail` are **computed from node-level text+CDATA runs** (first-run text, runs merge) — NOT the C `leptris_element_text`, which concatenates all descendant text (Nokogiri semantics).
- `elem[i]` is child indexing (never attribute lookup); `attrib` is read-only.
- `find*` passes through to full XPath 1.0 (a superset of ElementPath); `{uri}local` names get translated to generated prefixes.
- An undeclared XPath prefix evaluates to an empty nodeset (lxml raises) — documented difference.

### Memory model rules (the easy way to introduce segfaults/leaks)

- Strings returned by accessors are document-owned — always `ffi.string(...).decode()` into Python `str` at the boundary.
- `char*` returns from serialize/c14n/xpath-string must be released with `leptris_free_string`.
- `Document.close()` is the contract; elements raise `LeptrisError` on a closed document (`_check_alive`). Wrappers are created fresh per access — compare by name/attribute, never `is`.
- cffi callback structs (SAX) must keep every `ffi.callback` alive (the keepalive list pattern in `sax.py`).

### FFI mirror drift gate

`scripts/check_ffi_mirrors.py` fails CI on PHANTOM symbols (declared but not in headers), ARITY mismatches, missing REQUIRED_CORE symbols, and — when `LEPTRIS_LIB_PATH` is set — EXPORT failures (cdef symbols the built library doesn't ship; caught `leptris_document_last_error` being header-only in v1.2.0). When binding a new C function: match the header signature exactly, update tests, and extend REQUIRED_CORE if it's core.

## CI and publishing

- `.github/workflows/ci.yml` (push/PR): builds libleptris from the pinned tarball → drift gate → `pip install .[test]` → pytest, on ubuntu/macos/windows.
- `.github/workflows/release.yml`: PyPI **trusted publishing** (OIDC `id-token: write`, no credentials, no environment; the registered trusted publisher must match: owner `leptris`, repository `leptris-py`, workflow `.github/workflows/release.yml`).
  - Triggered by `workflow_dispatch` (ships the version in `pyproject.toml`) or `workflow_call` (with `inputs.publish: true`) from the C repo's release flow.
  - Gotcha: `github.event_name` propagates from the CALLER through `workflow_call` (the caller's release job runs on `pull_request closed`), so gates key on `inputs.publish`, never on `event_name == 'workflow_call'`.

## Repo conventions

- All changes via PR to `main` — never commit, push, or merge directly to main. Never push tags. No AI attribution in commits, PRs, or docs.
- `build/`, `dist/`, `tmp/`, `*.egg-info/`, `.pytest_cache/` are local artifacts; ignore them, don't commit them.
- Benchmark numbers on the website come only from the C repo's `python-benchmark` workflow artifacts — never from hand-run measurements.
