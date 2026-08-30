"""iterparse: bounded-memory incremental parsing."""

import io

import pytest

from leptris import iterparse
from leptris.error import ParseError

class TestIterparse:
    XML = "<root>" + "".join(f"<rec id='{i}'>v{i}</rec>" for i in range(5)) + "</root>"

    def test_yields_completed_top_level(self):
        from leptris import iterparse
        import io

        seen = [(e.get("id"), e.text) for _, e in iterparse(io.StringIO(self.XML))]
        assert seen == [(str(i), f"v{i}") for i in range(5)]

    def test_file_source(self, tmp_path):
        from leptris import iterparse

        path = tmp_path / "doc.xml"
        path.write_text(self.XML)
        tags = [e.tag for _, e in iterparse(str(path))]
        assert tags == ["rec"] * 5

    def test_subtree_content(self):
        from leptris import iterparse
        import io

        # Elements are borrowed: inspect within the iteration (the
        # engine releases each subtree on the next yield).
        xml = "<r><rec><a>1</a><b x='2'/></rec></r>"
        checked = []
        for _, element in iterparse(io.StringIO(xml)):
            checked.append(
                (element.tag, element[0].text, element[1].get("x"))
            )
        assert checked == [("rec", "1", "2")]

    def test_borrowed_until_next(self):
        from leptris import iterparse
        import io

        # Only the CURRENT element may be inspected; iteration runs
        # to exhaustion without holding references.
        count = 0
        for _, element in iterparse(io.StringIO(self.XML)):
            assert element.tag == "rec"
            count += 1
        assert count == 5

    def test_repeat_is_stable(self):
        from leptris import iterparse
        import io

        for _ in range(10):
            assert len(list(iterparse(io.StringIO(self.XML)))) == 5

    def test_only_end_events(self):
        from leptris import iterparse
        import io

        with pytest.raises(ValueError):
            iterparse(io.StringIO(self.XML), events=("start", "end"))
        list(iterparse(io.StringIO(self.XML), events="end"))

    def test_missing_file(self):
        from leptris import iterparse
        from leptris.error import ParseError

        with pytest.raises(ParseError):
            iterparse("/nonexistent/doc.xml")


class TestErrorChannel:
    # libleptris 1.9.4 (#586): iterparse reports parse failures instead
    # of ending iteration silently on truncated input.
    def test_truncated_input_raises(self):
        with pytest.raises(ParseError):
            for _ in iterparse(io.BytesIO(b"<root><item>1</item><item>2</it")):
                pass

    def test_mismatched_tag_raises(self):
        with pytest.raises(ParseError):
            for _ in iterparse(io.BytesIO(b"<root><a></b></root>")):
                pass

    def test_wellformed_does_not_raise(self):
        events = list(iterparse(io.BytesIO(b"<root><a/></root>")))
        assert len(events) == 1


class TestFullDocumentMode:
    def test_yields_every_element_in_completion_order(self):
        xml = b"<r><a><b/></a><c/></r>"
        tags = [el.tag for _, el in iterparse(io.BytesIO(xml), full_document=True)]
        assert tags == ["b", "a", "c", "r"]

    def test_top_level_default_unchanged(self):
        xml = b"<r><a><b/></a><c/></r>"
        tags = [el.tag for _, el in iterparse(io.BytesIO(xml))]
        assert tags == ["a", "c"]


class TestFullDocumentErrorMode:
    def test_fulldoc_clean_drain_no_raise(self):
        tags = list(iterparse(io.BytesIO(b"<r><a/></r>\n"), full_document=True))
        assert tags

    def test_fulldoc_malformed_raises(self):
        # Fixed in libleptris 1.9.15 (#592): the full-document error
        # channel reports real errors without spurious truncation.
        with pytest.raises(ParseError):
            list(iterparse(io.BytesIO(b"<r><a></b></r>"), full_document=True))


class TestNamespaceResolution:
    # libleptris 1.9.4 iterparse v2: borrowed elements carry namespace
    # resolution — Clark-notation tags, prefix, namespace, attributes.
    def test_namespaced_elements_resolve(self):
        xml = b"<x:catalog xmlns:x='urn:x'><x:book id='1'>T</x:book><plain/></x:catalog>"
        seen = [(el.tag, el.prefix, el.namespace) for _, el in iterparse(io.BytesIO(xml))]
        assert seen == [
            ("{urn:x}book", "x", "urn:x"),
            ("plain", None, None),
        ]

    def test_attributes_and_text_on_borrowed(self):
        for _, el in iterparse(io.BytesIO(b"<r><a x='1'>hello</a></r>")):
            assert (el.tag, el.get("x"), el.text) == ("a", "1", "hello")
