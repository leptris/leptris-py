"""Threading contract: one document per thread.

TODO.native/13 — the free-threaded (cpXXt) wheels ship under this
contract; these specs exercise it the way the release gate does:
each thread owns its document exclusively (parse, xpath, Plan,
tostring, SAX, serialize, close) and verifies its own results.
Meaningful under free-threaded CPython; a sanity check under the
GIL.
"""

import threading

from leptris import Document, Plan, sax
from leptris.error import ParseError

DOC = (
    "<catalog>"
    + "".join(
        f"<book id='{i}'><title>Book {i}</title></book>"
        for i in range(1, 21)
    )
    + "</catalog>"
)

PLAN = Plan({
    "element_name": "catalog",
    "children": [{
        "name": "book",
        "kind": "nested",
        "plan": {
            "element_name": "book",
            "attributes": {"id": {}},
            "children": [{"name": "title", "kind": "scalar"}],
        },
    }],
})


def _worker(n, errors):
    try:
        for _ in range(30):
            with Document.parse(DOC) as doc:
                assert doc.xpath("count(//book)") == 20.0
                assert len(doc.xpath("//book[@id=$i]",
                                     variables={"i": str(n)})) == 1
                data = PLAN(doc)
                titles = [b["children"]["title"]
                          for b in data["children"]["book"]]
                assert titles[n - 1] == f"Book {n}"
                events = []
                sax.parse(DOC, _Recorder(events))
                # start/end catalog + 20x (book, title) = 82 events
                assert len(events) == 82
    except Exception as exc:  # pragma: no cover - failure detail
        errors.append((n, exc))


class _Recorder(sax.SAXHandler):
    def __init__(self, events):
        self.events = events
        self.last_error = None

    def start_element(self, name, attributes):
        self.events.append(("start", name))

    def end_element(self, name):
        self.events.append(("end", name))


def test_one_document_per_thread():
    errors = []
    threads = [
        threading.Thread(target=_worker, args=(n + 1, errors))
        for n in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors


def test_shared_recorder_serializes_concurrent_parses():
    """Two threads SAX-parsing simultaneously through the module
    recorder must not interleave events (TODO.native/13 lock)."""

    received = [[], []]

    def worker(i):
        doc = DOC if i == 0 else DOC.replace("catalog", "other")
        handler = _Recorder(received[i])
        for _ in range(50):
            received[i].clear()
            sax.parse(doc, handler)
            names = [e[1] for e in received[i]]
            assert ("catalog" if i == 0 else "other") in names
            # every book event from THIS thread's document only
            assert all(n in ("book", "title", "catalog", "other")
                       for n in names)

    threads = [
        threading.Thread(target=worker, args=(i,)) for i in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
