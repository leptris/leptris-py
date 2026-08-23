# Changelog

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
