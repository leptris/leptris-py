# Plan: adopt the lxml API as the primary Python API

Status: implemented 2026-08-23 (stages 1–4 complete). Mutation,
iterparse, compiled XPath and node positions remain upstream C asks.

House style: the Ruby binding mirrors Nokogiri; the Python binding mirrors
lxml. The package is effectively unreleased (1.2.0 has zero users), so the
bespoke API is deleted, not aliased. No shims, no dual vocabulary.

Scope boundary: every stage below uses C functions that already exist in
libleptris 1.2.0 headers. New-C work (mutation, iterparse, compiled XPath,
pull API, node/error positions) is tracked as C-repo enhancement asks, not
part of this plan.

## Stage 0 — decisions

- Yank-or-keep 1.2.0 on PyPI (maintainer call; default: keep, changelog
  marks the next release as the API-defining one).
- Ship as the next lockstep release (package version rides libleptris).
  Breaking change is acceptable pre-adoption.

## Stage 1 — lxml-shaped core (rename + recomputed semantics)

cdef additions (all in the C headers today): `leptris_element_child`,
`leptris_element_serialize`, `LeptrisSerializeOptions`,
`leptris_error_message`, `leptris_last_error`,
`leptris_document_last_error`, `leptris_parse_file`.

Element (replaces current names; old names deleted):

- `tag` (was `name`), `get(name, default)` (was `attribute`),
  `getparent()`, `getnext()`, `getprevious()` (element siblings, skipping
  text — lxml semantics, matches current `next_sibling_element`)
- `attrib`: read-only `collections.abc.Mapping` over the attribute-handle
  chain; `keys()`/`items()`/`in` work, mutation raises
- `__getitem__` = child indexing via `leptris_element_child`
  (**breaking**: was attribute lookup), `__len__` = `child_count`,
  `__iter__` = child elements (unchanged)
- `text` / `tail` computed from Node-level text+CDATA runs (lxml-exact:
  first-run text, not the C's concatenated `element_text`; adjacent
  text+CDATA merges — needs explicit tests), `itertext()`, `iter()`,
  `iterdescendants()`
- `xpath()` stays

Document → ElementTree analogue: `getroot()` (alias of `root`), `write()`
via serialize options, `parse`/`close`/context manager unchanged.

Module surface: `fromstring`/`XML`, `tostring(elem_or_doc, pretty_print=,
xml_declaration=, encoding=)` mapping onto `LeptrisSerializeOptions`,
`parse(path_or_file)` via `leptris_parse_file` + bytes fallback.

Exceptions: `LeptrisError` base; `ParseError`, `XPathError` subclasses,
messages from the C error trio.

Node layer unchanged — advanced DOM view (comments/CDATA/PI), and the
substrate for text/tail computation.

Tests: suite rewritten against lxml semantics. New cases: mixed-content
text/tail (incl. `<a>x<![CDATA[y]]>z</a>` → text `"xyz"`), attrib Mapping
protocol, child indexing errors, getnext skipping text, exception types.

## Stage 2 — bind the dormant surface

- `xpath(expr, namespaces={...})` via `leptris_xpath_ns_set_*`
- `find`/`findall`/`findtext`: XPath passthrough with `{uri}tag` →
  `prefix:tag` translation; documented as XPath-1.0 superset (lxml findall
  is a subset — same behavior class)
- `tostring` options wired through `LeptrisSerializeOptions` (Stage 1
  shape, full coverage here)
- `c14n(exclusive=, inclusive_ns_prefixes=)` incl. exclusive mode
- `parse` with `encoding=`; `write` via `leptris_document_save_file`
- XPath variables (`xpath(expr, variables={...})` via `eval_with_vars`) —
  leptris extension beyond lxml, flag-waved in docs

## Stage 3 — streaming + honest gaps

- `leptris.sax`: SAX handler struct via cffi callbacks (Ruby parity).
  Document the per-callback FFI overhead; note pull-API as the C ask.
- README "Migrating from lxml" table — three columns: supported /
  absent-with-reason (mutation, creation, `iterparse`, smart strings,
  per-parse options like `resolve_entities`) / different (read-only
  `attrib`, plain `str` results, `Document` lifetime management).
- Benchmark matrix (BENCHMARK_PROMPT.md) executes against the new API;
  same-code-shape comparison against lxml.

## Stage 4 — PyPI polish + release

- `py.typed` + full annotations; classifiers (3.8–3.13, Typing :: Typed),
  `project.urls`, PEP 639 SPDX license, changelog
- Update drift-gate `REQUIRED_CORE` for newly mirrored symbols
- Release rides the next libleptris version via the C repo's
  `workflow_call` (trusted publishing; versions in three places must agree)

## C-repo asks this plan depends on (file as issues)

None blocking. Post-plan value: `leptris_version()`, error line/col on the
DOM path, DOM namespace accessors, `node_line`, non-element XPath result
accessors; then mutation, incremental build (iterparse), compiled XPath,
pull API, per-parse options.
