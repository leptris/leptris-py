"""The SAX records tape (libleptris 1.9.226+): whole-document
parse into a flat record table in one crossing."""

import pytest

from leptris.error import ParseError
from leptris.sax import records


class TestRecords:
    def test_parse_iterate_kinds_and_names(self):
        tape = records("<r><a>1</a>mid<b/></r>")
        got = [(r.kind, r.name if r.kind == "element" else r.text)
               for r in tape]
        assert got == [
            ("element", "r"),
            ("element", "a"),
            ("text", "1"),
            ("text", "mid"),
            ("element", "b"),
        ]

    def test_tree_links(self):
        tape = records("<r><a/><b><c/></b></r>")
        recs = list(tape)
        by_name = {r.name: r for r in recs if r.kind == "element"}
        assert by_name["a"].parent == 0      # the root record
        assert by_name["c"].parent == 2  # <b> is record 2
        assert by_name["a"].next_sibling == 2  # <b> follows

    def test_attrs(self):
        tape = records("<r x='1' y='2'><a k='v'/></r>")
        recs = list(tape)
        assert recs[0].attrs == [("x", "1"), ("y", "2")]
        assert recs[1].attrs == [("k", "v")]

    def test_self_closing_and_len(self):
        tape = records("<r><a/></r>")
        assert len(tape) == 2
        recs = list(tape)
        assert recs[1].self_closing is True
        assert recs[0].self_closing is False

    def test_lines_populated(self):
        tape = records("<r>\n  <a/>\n</r>")
        recs = list(tape)
        assert recs[1].line >= 1

    def test_context_manager_and_explicit_free(self):
        with records("<r/>") as tape:
            assert len(tape) == 1
        tape.free()  # idempotent

    def test_parse_failure_raises(self):
        with pytest.raises(ParseError):
            records("<r><unclosed>")

    def test_comments_unsupported_rejected(self):
        # the tape grammar is entity-free elements + text only
        with pytest.raises(ParseError):
            records("<r><!--c--></r>")

    def test_bytes_input(self):
        assert len(records(b"<r/>")) == 1

    def test_bad_type(self):
        with pytest.raises(TypeError):
            records(42)
