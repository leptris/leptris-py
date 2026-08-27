# Changelog


## 1.16.1 — 2026-08-27

Finishing the iterparse v2 surface (libleptris 1.9.4):

- borrowed iterparse elements resolve namespaces — Clark-notation
  tag, prefix, namespace, attributes, text all work; the README's
  stale "names are QNames as written" caveat is corrected and the
  behavior pinned by regression tests
- `StreamingParser(streaming=False)` now emits DeprecationWarning:
  the event recorder always streams and the legacy buffering mode
  the kwarg selected no longer exists (it was a silent no-op since
  1.16.0)


## 1.16.0 — 2026-08-27

Adopts libleptris 1.9.4 — the event recorder and iterparse v2:

- **SAX on the recorder**: `sax.parse` and `StreamingParser` drain
  buffered events in bulk (records + packed arena, one transfer per
  chunk) instead of one libffi callback per event — measured
  ~5.5x faster (246 -> 44 ms for 10k items / 90k events); event
  semantics pinned unchanged by the existing suite
- **iterparse error channel**: truncated or malformed input now
  raises ParseError instead of ending iteration silently
  (red-first tests); full-document mode's channel reports a
  spurious error on clean drains (filed leptris/leptris#592) —
  the binding skips the check there until fixed
- **iterparse full_document=True**: yields every element in
  completion order (children before parents)
- iterparse perf is unchanged (~2x behind lxml, leptris/leptris#563)
- pin 1.9.3 -> 1.9.4; cdef +recorder/iterparse_ex/error symbols


## 1.15.1 — 2026-08-27

SAX one-shot parse routed through the streaming state machine:

- `leptris.sax.parse` now drives `StreamingParser` in ~8 KB chunks
  instead of the engine's legacy `leptris_sax_parse` (which buffers
  the whole document) — ~2.3x faster for byte-identical events
  (verified: event streams and error behavior match exactly)
- one SAX code path remains instead of two (the module's own
  deletion test)
- the remaining SAX deficit vs lxml (~4x) is the per-event libffi
  callback tax the module docstring documents — not binding-side


## 1.15.0 — 2026-08-27

Adopts libleptris 1.9.3:

- `Document.toplevel_comments()` — prolog and epilog comments
  outside the root (engine #578); serialization already preserved
  them, and the binding now exposes the content list
- `Document.toplevel_pis()` — document-level processing
  instructions as `(target, data)` pairs; `data` is `None` for a
  dataless `<?target?>` (engine #577)
- attribute-value normalization (XML 1.0 §3.3.3, engine #576):
  newlines and tabs in attribute values become spaces — regression
  test pinned
- cdef: `document_comment_count` / `document_comment_content`


## 1.14.3 — 2026-08-27

Error text and verification (review #14):

- ParseError messages no longer double the generic text: the
  thread-local detail usually starts with it ("XML parse error:
  XML parse error at byte N") — the more specific detail now
  stands alone
- verified-surface additions (no code change): peak RSS on a
  1.8 MB document is ~35% below lxml (38 vs 58 MB) and a full
  iter() pass adds no growth; deep-nesting behavior is at parity
  with lxml (both engines reject depth 300+), now pinned by a
  boundary test


## 1.14.2 — 2026-08-27

Adopts libleptris 1.9.2 (pin 1.9.0 -> 1.9.2; no binding changes):

- 1.9.1 appended fields to the public LeptrisSerializeOptions
  struct; FFI callers allocating the frozen 1.9.0 layout got
  read-past-buffer — tostring(doc, pretty_print=True) segfaulted
  or silently dropped indentation (leptris/leptris#568, blocked
  the 1.9.1 adoption). Fixed upstream in #569: the struct is
  frozen with a compile-time size pin; extended settings moved
  behind an internal seam
- verified against the v1.9.2 tag build: 178/178 tests, drift
  gate clean (230 public symbols), all repro shapes produce
  correctly indented output; no new leptris_* API functions
- README prerequisite now says 1.9.2+ and warns off 1.9.1


## 1.14.1 — 2026-08-27

find(): correctness and a 6.5x speedup (review #11):

- **bug**: find("name") on a namespaced document returned the
  NAMESPACED element while findall("name") correctly returned
  nothing — find_first compared the local name without requiring
  no-namespace (ElementTree/lxml semantics). Fixed with a red-
  first test; find() and findall() now agree everywhere
- multi-step find("a/b/c") walks in C (`_accel.find_path`): a
  first-match DFS over plain-name steps instead of materializing
  the whole result list through findall. find("book/title"):
  8.23 -> 1.27 µs — was 5.8x SLOWER than lxml, now 1.29x faster;
  find("book") 1.01 -> 0.72 µs
- engine finding filed as leptris/leptris#565: evaluation with a
  variable set costs 53.3 µs raw vs 0.67 µs for the literal
  equivalent (~79x) — with #563 (iterparse) and #564 (namespaced
  eval) this brackets the third and last engine-side perf wall;
  the binding's own share there is ~10 µs of 63.5


## 1.14.0 — 2026-08-26

Compiled XPath rejoins the fast path (review #10):

- the compiled `XPath` class still converted results through
  the pre-1.12 Python path (cffi buffer, per-node unpack,
  Python materialize, per-call ns marshaling) — 34.8 µs vs
  lxml's 8.3 for a namespaced query, 32.5 µs even for an EMPTY
  result. `_accel.compiled_eval` now evaluates and converts in
  one C call through the same finish_result as every other
  query shape (Fns protocol 43 -> 45; the compiled address is
  cached at construction). Compiled-with-namespaces now runs at
  parity with the plain path (was 1.7x slower than our own)
- new regression test: compiled-with-ns matches plain-with-ns
- engine finding filed as leptris/leptris#564: namespaced
  evaluation costs 17.5 µs raw vs 0.95 µs un-namespaced for the
  same scan (~18x) — the remaining query-shaped loss to lxml is
  engine-side, like #563 (iterparse)


## 1.13.3 — 2026-08-26

Memory-safety fix (review #7 — deep-read of the last never-read
module):

- `Node.as_element()` created its Element OUTSIDE the per-document
  registry, so `Document.close()` could not poison it: accessing
  the element after close read freed memory instead of raising
  LeptrisError (proven before fixing). It now goes through the
  same `_make` seam as every other Element creation, and was the
  package's only direct construction site


## 1.13.2 — 2026-08-26

SAX correctness (review #5 — the module no review had read):

- `sax.parse()` and `StreamingParser` clear
  `handler.last_error` before starting: a REUSED handler
  previously raised the previous document's error on a valid
  re-parse (proven by a failing test, then fixed)
- `StreamingParser` gains the `__del__` last-resort safety net
  (house pattern; an unclosed parser leaks engine memory)
- README Layout now names the C accelerator (half the codebase
  was undocumented in the module map) and api.py's iterparse


## 1.13.1 — 2026-08-25

Thin pass (review #4; two probed candidates, everything else declined):

- bytes-direct parse: the `y#` format unit works under the 3.9
  limited API (PyBytes_AsStringAndSize is in the stable ABI —
  probed before proposing), so `_accel.parse(data, recover)` takes
  the bytes buffer directly and `Document.parse` drops the
  bytearray/from_buffer/cast ceremony and the empty-input special
  case; parse small 3.81 -> ~3.0 µs (2.0x -> ~2.6x vs lxml)
- xpath.py keeps a single Python result converter
  (`_XPathEngine.evaluate` now returns through `_convert` instead
  of carrying an identical inline copy — a drift hazard)


## 1.13.0 — 2026-08-25

Document joins Element's raw-address pattern; one home per accessor.

- `_accel.parse`/`parse_file`: parse + #550 promote-touch +
  registry creation in ONE C call returning an address; Fns grows
  to 43 entries (parse_string, parse_string_ex, parse_file,
  document_root, document_free)
- Document stores the raw address; the cffi handle is created
  lazily (`_cd()`) for cold paths (write-to-file, XInclude, c14n,
  engine XPath); `close()` runs through a bound `document_free`;
  closed-document guards added at every `_cd()` entry
- leptris/leptris#561 filed: parse_string_inplace measured 8-42%
  SLOWER than parse_string at every scale (header claims 3-5x
  faster) — the binding keeps parse_string
- element.py purge: the seventeen Python accessors shadowed by the
  C type (tag/text/tail/namespace/prefix/sourceline/attrib/get/
  keys/items/values/getparent/getnext/getprevious/__len__/
  __getitem__) and their orphaned helpers (_AttribMap, _run_at,
  _iter_attributes, dead imports) are deleted — each accessor has
  exactly one home now (462 -> 275 lines)
- benchmarks/matrix.py records loadavg and marks runs CONTENDED
  above 2x CPU count (a loadavg-247 machine produced a garbage
  matrix earlier today; the guard makes such runs self-labeling)


## 1.12.0 — 2026-08-25

Performance pass: subtree walks never touch the XPath engine.

- C subtree cursor (`SubtreeIterator` in the accelerator):
  `Element.iter()`/`iterdescendants()` walk
  first-child/next-sibling/parent directly in C and stream
  elements instead of building an expression string, evaluating
  it, and materializing the whole subtree as a list; name and
  namespace are matched in C (the tag is split once, in Python)
- child iteration (`for child in element`) is a single C call
  returning a presized list (`_accel.children`)
- `Element.__iter__`'s two Python paths (chain generator, bulk
  FFI fill) are gone
- nodeset results are presized (`PyList_New` + `SetItem`) and
  mixed nodesets bail to the engine path before any object is
  built
- the XPath adapter (`_c_evaluate`) is imported once at module
  scope instead of inside every `xpath()`/`findall()` call;
  findall's duplicated namespace-merge branch is folded
- `Document.xpath()` goes straight to the all-C adapter when no
  variables are bound (it previously detoured through the Python
  engine wrapper even on the fast path)
- `tostring(document)`/`Document.write(fileobj)` defaults run
  `leptris_document_serialize` in one C call (`_accel.serialize_doc`,
  Fns entry #38); option-carrying paths are unchanged
- the #557 workaround (self-match + `descendant::` detour) is no
  longer load-bearing for iter() — the cursor compares name and
  namespace directly, so engine fix or not, iter() is correct
- bind protocol: FN_COUNT is single-sourced in the accelerator
  (the count check and the fill loop share one constant)
- new tests: mid-iteration close raises LeptrisError (both
  iterators), deep-tree document order, broken Clark tags yield
  nothing, wildcard iterdescendants
- README: iter()/iterdescendants() documented as elements-only
  (ElementTree semantics; lxml also yields comments/PIs)


## 1.11.1 — 2026-08-25

Architecture deepening pass, no API changes:

- positional bind seam: the accelerator is bound by passing 37
  function addresses in `Fns` declaration order (one tuple in
  element.py, one slot array in _leptrisaccel.c); count mismatches
  fail loudly instead of mis-binding
- self-describing method attach: `_ElementMethods` members attach
  only where the C type provides nothing beyond object's default —
  the hand-maintained skip-set is gone
- `_c_evaluate` adapter in xpath.py is the single bridge to all-C
  nodeset evaluation; `Element.xpath`, `findall` and the engine
  fast path all go through it
- `_BorrowedDocument` (iterparse sentinel owner) hoisted out of the
  closure
- test split: iterparse tests live in tests/test_iterparse.py,
  compiled-XPath tests folded into tests/test_xpath.py

Engine-bug workarounds (filed upstream):

- leptris/leptris#550 (flat-path promote, extends to XPath):
  `Document.parse` touches the root once so fresh documents
  serialize and evaluate XPath correctly without a prior getroot()
- leptris/leptris#557 (descendant-or-self omits a namespaced root
  for prefixed name tests): `Element.iter(tag)` matches self in
  Python and walks `descendant::` instead


Legacy purge (the binding is single-mode now):

- the pure-Python Element fallback and `LEPTRIS_PURE` are gone —
  the C accelerator is a required component; sdist builds without a
  toolchain fail loudly instead of degrading
- the legacy static `XPath` wrapper is gone; `leptris.XPath` is the
  precompiled class
- the libleptris-1.2.0 error-message fallback is gone (XPath errors
  use `leptris_document_last_error`)
- CI pure-mode leg removed; the plan document (implemented 1.3.0)
  deleted

Also with libleptris 1.6.0: mixed-nodeset attribute payloads are
correct (#514) — the xfail test is now a hard assertion; same-parent
move corruption (#518) fixed upstream.

## 1.11.0 — 2026-08-24

Adopts libleptris 1.9.0 (1.8.0 + 1.9.0 surface):

- `Document.parse(..., recover=True)` — malformed input yields an
  empty rootless Document instead of raising ParseError (#547
  engine mode; partial-tree recovery not yet implemented upstream)
- `Element.get("{uri}local")` — Clark-notation attribute lookup via
  `leptris_element_attribute_ns` (lxml semantics), implemented in
  the C accelerator
- element serialization passes options through
  `leptris_element_serialize_into` directly (1.9.0 options support);
  the allocating fallback is gone, and declarations now carry the
  UTF-8 encoding the engine requires to emit them
- cdef: `node_children`, both `serialize_into` variants (5-arg),
  `attribute_ns`/`has_attribute_ns`, `ParseOptions` +
  `parse_string_ex`
- filed upstream leptris/leptris#550: raw-API
  `document_serialize` fails on fresh flat-path documents (TODO 139
  Phase D promote) — the binding is unaffected (it touches
  `document_root` first)

## 1.10.0 — 2026-08-24

Adopts libleptris 1.7.0 (includes 1.6.2's mixed-content
pretty-print fix, #534):

- element serialization uses `leptris_element_serialize_into` —
  zero-copy into a pre-sized buffer (~15% off `tostring(elem)`,
  which is at or ahead of lxml)
- `leptris_node_children` and the `_serialize_into` pair declared in
  the FFI surface (batch node access available to advanced users of
  the cdef)
- drift gate verified against 1.7.0 headers (86 declarations /
  220 public symbols)

## 1.9.0 — 2026-08-24

Adopts libleptris 1.6.0 (pin bump from 1.3.0; 1.5.x folded in):

- `leptris.iterparse(source)` — incremental parsing with memory
  bounded by the largest subtree (lxml parity for the top use case).
  Yields `("end", element)` per completed top-level child; elements
  are borrowed until the next yield. File or file-like input;
  only "end" events.
- `leptris.XPath(expression)` — precompiled XPath (lxml's
  `etree.XPath`): compile once, evaluate many times, with element
  contexts and namespaces.
- element serialization fixed upstream (#523): `tostring(elem)`
  went from ~12x behind lxml to parity (engine 7.8 us -> 0.35 us);
  wrapper trimmed accordingly
- unprefixed XPath name tests no longer match namespaced elements
  (upstream correctness fix — lxml semantics)

## 1.8.0 — 2026-08-24

Full-surface accessor sweep: every remaining Python+cffi path moved
into the accelerator. Previously-behind operations, before -> after
(vs lxml, macOS arm64, py3.10):

- `tail` 74x behind -> 83 ns, faster
- `keys`/`values`/`items` 18-22x -> faster
- slice indexing 15x -> faster
- `itertext` 13x -> 3.9x faster
- `find` 12x -> 0.48 us vs 0.91 (C child-chain first-match walk, no
  XPath); `findtext` faster
- `prefix`/`namespace`/`sourceline` 8-10x -> faster
- `getprevious` -> tie; namespaced `xpath` -> faster (C ns-set eval
  with the document address cached at parse)
- element serialization routes through C with NULL options (the
  engine's options-struct path is slower even for defaults)

Known engine-bound residuals (filed upstream): element-level
serialization carries a ~18 us constant cost vs document
serialization at a tenth of it; namespaced bulk findall remains
~2x behind lxml's compiled ElementPath.

## 1.7.0 — 2026-08-24

C-level hot accessors in the accelerator (libleptris function
addresses bound once; no FFI per access):

- `tag`/`text`/`attrib`/`get`/`len`/`elem[i]`/`getparent`/`getnext`
  run in C — 50-100 ns each, at or faster than lxml (previously
  5-35x behind through cffi)
- `attrib` is a cached read-only dict snapshot; `tag` and the
  parent/next-sibling wrappers are cached per element (documents
  are immutable)
- use-after-close safety moved from a per-access check (~60 ns) to
  lxml-style invalidation: a per-document registry poisons element
  pointers in one pass at `Document.close()`
- all-C evaluation path for plain XPath/findall: eval, batch fill
  and element construction in one call, scalars converted in C —
  `//book` 6.4 -> 4.0 µs, traversal 18 -> 12.7 µs vs lxml 11.7/19.5
- accessor benchmark vs lxml: tag ties, and get/text/len/index/
  attrib/getnext/findall/iter are all faster; getparent is within
  10 ns

## 1.6.1 — 2026-08-23

- adds the manylinux aarch64 wheel: 1.6.0's build silently skipped
  it (cross-arch emulation not configured); the release workflow now
  builds it natively on an `ubuntu-24.04-arm` runner

## 1.6.0 — 2026-08-23

C-accelerated Element allocation (`leptris._leptrisaccel`, abi3):
instance creation happens in C while the whole API surface stays in
Python (methods attach onto the C heap type). Wheels ship compiled;
without a toolchain the package degrades to the equivalent
pure-Python class (`LEPTRIS_PURE=1` forces it).

Benchmark matrix, macOS arm64, py3.10, lxml 6.0.2 — every operation
now beats lxml: `//book` 14.8 → 6.4 µs (lxml 12.0), union 31.1 →
19.2 (lxml 27.9), traversal 50.7 → 18.0 (lxml 21.6); parse, scalar
XPath, predicates and serialization already won.

## 1.5.0 — 2026-08-23

Adopts libleptris 1.3.0 (now the pinned build in CI):

- `Element.sourceline` — 1-based source line (lxml parity), via
  `leptris_node_line`
- child iteration uses `leptris_element_children` bulk fill from 4
  children up (2x on wide elements, measured)
- nodeset materialization via `ffi.unpack` + `map` (13-18% off the
  wrapper loop): `//book` 16.2 → 14.8 µs vs lxml 12, union 33.6 →
  31.1 vs 27.9, traversal 58 → 50.7 vs 19.9
- XPath errors prefer the document-scoped
  `leptris_document_last_error` (immune to concurrent operations on
  other documents); requires libleptris >= 1.3.0

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
