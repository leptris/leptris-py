# leptris (Python) — lxml-shaped bindings for libleptris

`leptris` wraps the [libleptris](https://github.com/leptris/leptris)
C API (XML 1.0 parsing, XPath 1.0) using `cffi` in ABI mode, with a
required C accelerator for Element allocation and the hot accessors
(`tag`, `text`, `attrib`, `get`, indexing, sibling navigation and
plain-path XPath evaluation). Wheels ship it compiled; sdist builds
require a C compiler.

The pinned libleptris version lives in `libleptris-version.txt`
(lockstep releases); CI builds it from the release tarball. The
binding loads the shared library from `LEPTRIS_LIB_PATH` or the
loader path.

## Requirements

- Python 3.9+
- `cffi` (installed automatically)
- libleptris **1.9.3+** as a shared library (1.9.1 has an options-struct ABI break — leptris/leptris#568)
- libleptris as a shared library (`libleptris.dylib` / `.so` /
  `.dll`) on the loader path, or pointed to by `LEPTRIS_LIB_PATH`
  (which must name the library **file** — the loader `dlopen`s it
  verbatim). For a development checkout:

```bash
cmake -B build -S /path/to/leptris -DLEPTRIS_BUILD_SHARED=ON
cmake --build build --target leptris_shared
export LEPTRIS_LIB_PATH=/path/to/leptris/build/src/libleptris.dylib
```

## Quick start

```python
from leptris import fromstring, tostring

root = fromstring("<library><book id='1' lang='en'>Ulysses</book></library>")

root.tag                                # "library"
root[0].get("id")                       # "1"
root[0].attrib                          # {"id": "1", "lang": "en"}
root[0].text                            # "Ulysses"

root.xpath("count(//book)")             # 1.0
[b.text for b in root.findall("book")]  # ["Ulysses"]

tostring(root[0], encoding="unicode")   # "<book id=\"1\" lang=\"en\">Ulysses</book>"
```

Documents own the tree; use the context manager or `close()`:

```python
from leptris import parse

with parse("catalog.xml") as doc:
    doc.xpath("//book[@lang='en']")
```

Namespaces, variables, canonical XML and streaming:

```python
root.xpath("//x:item", namespaces={"x": "urn:ex"})
root.xpath("//book[@id=$id]", variables={"id": "2"})
c14n(root, exclusive=True)

from leptris import sax
sax.parse(xml, handler)                       # one-shot
with sax.StreamingParser(handler) as parser:  # push, constant memory
    parser.feed(chunk, final=last)
```

## Migrating from lxml

| lxml | leptris | Notes |
|---|---|---|
| `etree.fromstring` / `etree.XML` | `fromstring` / `XML` | |
| `etree.parse` | `parse` | paths and file-likes; **no URLs** |
| `etree.tostring(elem, …)` | `tostring(elem, …)` | bytes by default, `encoding="unicode"` for str |
| `elem.tag` / `.text` / `.tail` | same | `tag` uses `{uri}local` Clark notation; CDATA merges into text (lxml's default parser behavior) |
| `elem.attrib` / `.get()` / `.keys()` / `.items()` | same | `attrib` is a **read-only** Mapping |
| `elem.getparent/getnext/getprevious` | same | |
| `elem[i]`, `len(elem)`, iteration, slices | same | indexing is child indexing, never attribute lookup |
| `elem.iter()` / `.iterdescendants()` / `.itertext()` | same | elements only (ElementTree semantics); lxml's `iter()` also yields comments/PIs |
| `elem.find/findall/findtext` | same | accepts full XPath 1.0 — a superset of ElementPath — including `{uri}local` names |
| `elem.xpath(expr, namespaces=…)` | same | plus `variables={…}` (leptris extension) |
| `etree.c14n` / `etree.XInclude` | `c14n(…)` / `doc.process_xinclude()` | |
| `etree.XMLSyntaxError` | `ParseError` | XPath failures raise `XPathError`; both subclass `LeptrisError` |
| `etree.Element`, `SubElement`, `append`, `set`, `remove` | **not exposed** | libleptris has partial mutation upstream (node content setters, `set_root`, `remove_children`) — not surfaced here; build trees elsewhere |
| document-level comments / PIs | `doc.toplevel_comments()` / `doc.toplevel_pis()` | prolog then epilog; requires libleptris 1.9.3+ |
| `etree.iterparse` | `leptris.iterparse(source, full_document=False)` | bounded by the largest subtree; yields `("end", element)`; elements borrowed until the next yield; tags resolve namespaces (Clark notation, libleptris 1.9.4+). **Truncated or malformed input raises ParseError** (libleptris 1.9.4 error channel). `full_document=True` yields every element in completion order — error detection is unreliable in that mode pending leptris/leptris#592. Still ~2× slower than lxml's iterparse (leptris/leptris#563) |
| smart strings | plain `str` | XPath string/attribute results |
| `elem.nsmap` | **absent** | use `elem.namespace` / `elem.prefix` and `xpath(namespaces=…)` |
| `etree.XPath` compiled objects | `leptris.XPath(expression)` | compile once, evaluate many; contexts, namespaces, and variables supported |
| parser options (`resolve_entities`, …) | **absent** | libleptris 1.2.0 has no per-parse options |
| `elem.sourceline` | same | requires libleptris 1.3.0+ |
| undeclared XPath prefix | raises in lxml | evaluates to an empty nodeset here |

## Layout

- `leptris/_ffi.py` — cdef mirror of the public headers + loader
  (the only place libleptris is declared)
- `leptris/_leptrisaccel.c` — the C accelerator (abi3): allocates
  Elements and runs the hot accessors, subtree iteration, the parse
  and serialization seams, and the per-document element registry;
  bound to libleptris by the positional protocol in `element.py`
- `leptris/element.py`, `document.py`, `node.py`, `xpath.py` —
  the Python surface: queries, walks, documents; `node.py` exposes
  the full DOM (comments, CDATA, PIs) beneath the ElementTree shape
- `leptris/api.py` — `fromstring`/`parse`/`tostring`/`c14n`/
  `iterparse`
- `leptris/sax.py` — SAX one-shot and streaming
- `tests/` — pytest suite (`pytest` with `LEPTRIS_LIB_PATH` set)
- `benchmarks/` — matrix vs lxml/ElementTree/minidom (`pip install
  .[bench]`, then `python -m benchmarks.matrix`)

## Memory model

The `Document` owns the whole tree and its pool. Accessor strings
are copied into Python `str` at the boundary, so nothing depends on
document lifetime after a call returns. Elements keep a reference to
their `Document`, so the pool cannot be freed while any wrapper is
alive. Prefer explicit `close()` / the context manager; `__del__` is
a refcounting safety net, not a contract. Using an element after its
document is closed raises `LeptrisError`.

## Versioning

`libleptris-version.txt` pins the library release the binding is
built and tested against. From 1.3.0 the package follows its own
semver: 1.2.0 shipped an interim bespoke API to no adopters, and
1.3.0 replaces it with the lxml-shaped API (breaking, but
pre-adoption). `pyproject.toml` and `leptris/__init__.py` must agree
at release time.

## Publishing

Releases publish to PyPI via `.github/workflows/release.yml`, using
PyPI **trusted publishing** (no stored credentials). The workflow
runs on manual dispatch (ships the version in `pyproject.toml`) and
is called by the libleptris release flow (`publish: true`), so every
libleptris release ships the wheel.

## Local development

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade build pytest cffi
./.venv/bin/pip install -e .[test,bench]
LEPTRIS_LIB_PATH=/path/to/libleptris.dylib ./.venv/bin/python -m pytest tests/ -q
```
