# Changelog

## 1.4.1 — 2026-08-23

- `iter()` / `iterdescendants()` now delegate the subtree walk to the
  engine: one `descendant-or-self`/`descendant` XPath evaluation at C
  speed plus batch materialization, replacing ~2 FFI dispatches per
  element. Benchmark traversal: 291 → 58 µs vs lxml 21 (was 14×
  behind, now 2.7×). Same contract as lxml — self first, document
  order, `{uri}local` and `*` filters; results are materialized
  (not lazy). Non-QName tags keep filter semantics via a Python walk.

## 1.4.0 — 2026-08-23

- XPath nodesets materialize through `leptris_xpath_result_get_nodes`
  (one batch FFI call when every result node is an element; per-index
  fallback for mixed nodesets): `//book` (100 results) 30.4 → 16.4 µs
  vs lxml 11.8, `//author | //title` (200) 63.4 → 34.4 µs vs lxml
  27.1 (macOS arm64, py3.10, lxml 6.0.2)
- `leptris.libleptris_version()` — runtime version string of the
  loaded library; the benchmark matrix prints it alongside the pin.
  Note: libleptris 1.2.0 reports "0.26.8" (leptris/leptris#510)
- README: mutation row corrected — libleptris has partial mutation
  upstream (node content setters, `set_root`, `append_child`,
  `remove_children`), not surfaced in this binding yet
- Known upstream issue leptris/leptris#514: attribute nodes inside
  mixed (union) nodesets lose name/value (xfail test tracks it)

## 1.3.1 — 2026-08-23

Performance — binding wrapper overhead only, no API changes
(macOS arm64, py3.10, lxml 6.0.2; benchmark matrix before → after):

- XPath nodeset materialization: `//book` (100 results)
  47.9 → 30.4 µs, `//book[price > 50]` (49) 30.8 → 20.1 µs,
  `//author | //title` (200) 105.1 → 63.4 µs —
  `result_get`-first fast path (returns NULL exactly for non-element
  slots, so the kind query is only paid on fallback) and `__slots__`
- traversal 532 → 291 µs (−45%) — element-level sibling chains
  (`first_child_any`/`next_sibling_any`) skip text nodes; halved FFI
  calls per step
- `getnext`/`getprevious` are now single FFI calls
  (`leptris_element_previous_sibling_any` newly bound)
- `__slots__` on `Document`/`Element`/`Node`/attrib view: cheaper
  construction, no per-instance dict

Remaining gap to lxml on nodeset materialization (~0.29 µs/element)
and traversal needs C-side batch accessors — tracked upstream.

## 1.3.0 — 2026-08-23

Breaking: the API was redesigned to mirror lxml — the Ruby binding
mirrors Nokogiri, so the Python binding mirrors lxml. The package is
pre-adoption; the interim 1.2.0 API is replaced outright, not
deprecated.

- `Element`: `tag` in Clark notation, `text`/`tail` per the
  ElementTree model (adjacent text and CDATA runs merge, as lxml's
  default parser does), read-only `attrib` Mapping, `get`,
  `getparent`/`getnext`/`getprevious`, child indexing and slicing,
  `iter`/`iterdescendants`/`itertext`, `namespace`/`prefix`,
  `find`/`findall`/`findtext` (accepts full XPath 1.0 — a superset of
  ElementPath — including `{uri}local` names),
  `xpath(expr, namespaces=…, variables=…)`
- `Document`: `getroot`, `write` (path or file-like),
  `Document.parse_file`
- module-level `fromstring`/`XML`/`parse`/`tostring`/`c14n`
- `LeptrisError` base with `ParseError` and `XPathError` subclasses,
  messages sourced from libleptris
- `leptris.sax`: one-shot SAX parse and a streaming push parser
  (constant-memory, events emitted as chunks arrive)
- `benchmarks/matrix.py` vs lxml/ElementTree/minidom; `[bench]` extra
  pins lxml
- FFI drift gate: exports are now verified against the built library
  (catches declared-but-unexported symbols such as
  `leptris_document_last_error` in libleptris 1.2.0)
- packaging: PEP 639 SPDX license, classifiers, project URLs,
  `py.typed`; requires-python raised to 3.9 (3.8 is EOL and current
  setuptools no longer supports it)
- versioning: from 1.3.0 the package follows its own semver;
  `libleptris-version.txt` (1.2.0) pins the library release the
  binding is built and tested against

## 1.2.0 — 2026-08-23

First PyPI release (interim bespoke API; superseded by Unreleased).
Trusted publishing via `.github/workflows/release.yml`.
