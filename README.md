# leptris (Python) — bindings for libleptris

`leptris` wraps the [libleptris](https://github.com/leptris/leptris-py)
C API (XML 1.0 parsing, XPath 1.0) using `cffi` in ABI mode — the
`cdef` in `leptris/_ffi.py` mirrors libleptris's public headers.

The pinned libleptris version lives in `libleptris-version.txt`
(lockstep releases); CI builds it from the release tarball. The
binding loads the shared library from `LEPTRIS_LIB_PATH` or the
loader path.

## Requirements

- Python 3.8+
- `cffi` (`pip install cffi`)
- libleptris as a shared library (`libleptris.dylib` / `libleptris.so`)
  on the loader path, or pointed to by `LEPTRIS_LIB_PATH`. For a
  development checkout:

```bash
cmake -B build -S . -DLEPTRIS_BUILD_SHARED=ON
cmake --build build --target leptris_shared
export LEPTRIS_LIB_PATH=$PWD/build/src/libleptris.dylib
```

## Quick start

```python
from leptris import Document

doc = Document.parse("<library><book id='1'>Ulysses</book></library>")

doc.root.name                     # "library"
book = doc.root.first_child_element
book.name                         # "book"
book.attribute("id")              # "1"
book.text                         # "Ulysses"

doc.xpath("count(//book)")        # 1.0
[e.text for e in doc.xpath("//book")]   # ["Ulysses"]

doc.close()   # or: with Document.parse(xml) as doc: ...
```

## Layout

- `leptris/_ffi.py` — cdef + shared-library loading (single source
  of the C surface, mirroring the Ruby binding's `lib/leptris.rb`)
- `leptris/document.py`, `element.py`, `node.py`, `xpath.py`,
  `error.py` — typed wrappers
- `tests/` — pytest suite (run: `pytest` with `LEPTRIS_LIB_PATH` set)

## Memory model

The `Document` owns the whole tree and its pool. Accessor strings
are copied into Python `str` at the boundary, so nothing depends on
document lifetime after a call returns. Elements keep a reference to
their `Document`, so the pool cannot be freed while any wrapper is
alive. Prefer explicit `close()` / the context manager; `__del__` is
a refcounting safety net, not a contract.

## Versioning

The package version tracks libleptris (lockstep): library 1.1.0 ↔
leptris 1.1.0.

## Publishing

Releases publish to PyPI via `.github/workflows/release.yml`
on `v*` tags, using PyPI **trusted publishing** (no stored
credentials). One-time setup on pypi.org: project settings →
Publishing → add trusted publisher for the `leptris/leptris-py`
repo, the `release.yml` workflow, no environment. Until then, the wheel built
by CI is downloadable from the run's artifacts and installable
directly.

## Local development

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade build setuptools wheel pytest cffi
./.venv/bin/python -m build
LEPTRIS_LIB_PATH=../../build-shared/src/libleptris.dylib \
  ./.venv/bin/python -m pytest tests/ -q
```
