"""SAX: one-shot parse, streaming feed, error handling."""

import pytest

from leptris import sax
from leptris.error import ParseError


class Recorder(sax.SAXHandler):
    def __init__(self):
        self.events = []

    def start_document(self):
        self.events.append(("start_document",))

    def end_document(self):
        self.events.append(("end_document",))

    def start_element(self, name, attributes):
        self.events.append(("start", name, attributes))

    def end_element(self, name):
        self.events.append(("end", name))

    def characters(self, text):
        self.events.append(("text", text))

    def comment(self, text):
        self.events.append(("comment", text))

    def cdata(self, text):
        self.events.append(("cdata", text))

    def processing_instruction(self, target, data):
        self.events.append(("pi", target, data))

    def start_prefix_mapping(self, prefix, uri):
        self.events.append(("ns-start", prefix, uri))

    def end_prefix_mapping(self, prefix):
        self.events.append(("ns-end", prefix))


class TestSaxParse:
    def test_document_events(self):
        handler = Recorder()
        sax.parse("<r/>", handler)
        assert handler.events == [("start_document",), ("start", "r", {}), ("end", "r"), ("end_document",)]

    def test_attributes_dict(self):
        handler = Recorder()
        sax.parse("<r k='v' n='2'/>", handler)
        start = handler.events[1]
        assert start[2] == {"k": "v", "n": "2"}

    def test_text_and_cdata_are_separate(self):
        handler = Recorder()
        sax.parse("<r>t<![CDATA[w]]></r>", handler)
        assert ("text", "t") in handler.events
        assert ("cdata", "w") in handler.events

    def test_entities_expand_in_text(self):
        handler = Recorder()
        sax.parse("<r>a &amp; b</r>", handler)
        assert ("text", "a & b") in handler.events

    def test_comment_and_pi(self):
        handler = Recorder()
        sax.parse("<r><!--c--><?pi go?></r>", handler)
        assert ("comment", "c") in handler.events
        assert ("pi", "pi", "go") in handler.events

    def test_namespace_mappings(self):
        handler = Recorder()
        sax.parse("<x:r xmlns:x='urn:x'><x:a/></x:r>", handler)
        assert ("ns-start", "x", "urn:x") in handler.events
        assert ("ns-end", "x") in handler.events

    def test_error_raises_parse_error(self):
        handler = Recorder()
        with pytest.raises(ParseError) as exc_info:
            sax.parse("<unclosed>", handler)
        assert "line" in str(exc_info.value)

    def test_accepts_bytes(self):
        handler = Recorder()
        sax.parse(b"<r/>", handler)
        assert ("start", "r", {}) in handler.events


class TestStreaming:
    def test_chunked_feed(self):
        handler = Recorder()
        with sax.StreamingParser(handler) as parser:
            for index, chunk in enumerate(["<r>", "<a>te", "xt</a>", "</r>"]):
                parser.feed(chunk, final=index == 3)
        kinds = [event[0] for event in handler.events]
        assert kinds[0] == "start_document"
        assert kinds[-1] == "end_document"
        assert ("start", "a", {}) in handler.events
        assert ("end", "a") in handler.events

    def test_characters_may_split_across_chunks(self):
        # The C contract: text spanning a chunk boundary arrives in
        # multiple characters() calls that concatenate.
        handler = Recorder()
        with sax.StreamingParser(handler) as parser:
            parser.feed("<r>ab")
            parser.feed("cd</r>", final=True)
        texts = [event[1] for event in handler.events if event[0] == "text"]
        assert "".join(texts) == "abcd"

    def test_whole_document_in_one_feed(self):
        handler = Recorder()
        with sax.StreamingParser(handler) as parser:
            parser.feed("<r><a/></r>", final=True)
        assert ("end", "r") in handler.events

    def test_missing_final_leaves_document_open(self):
        handler = Recorder()
        with sax.StreamingParser(handler) as parser:
            parser.feed("<r><a/></r>")  # never finalized
        assert ("end_document",) not in handler.events

    def test_error_raises(self):
        handler = Recorder()
        with pytest.raises(ParseError):
            with sax.StreamingParser(handler) as parser:
                parser.feed("<r><a></r>", final=True)

    def test_feed_after_close_raises(self):
        handler = Recorder()
        parser = sax.StreamingParser(handler)
        parser.close()
        with pytest.raises(ParseError):
            parser.feed("<r/>", final=True)


class TestHandlerContract:
    def test_base_class_is_all_noops(self):
        sax.parse("<r>x</r>", sax.SAXHandler())

    def test_custom_error_recording(self):
        class Tolerant(sax.SAXHandler):
            def __init__(self):
                self.seen = None

            def error(self, message, line, column):
                self.seen = (message, line, column)

        handler = Tolerant()
        with pytest.raises(ParseError):
            sax.parse("<broken", handler)
        assert handler.seen is not None and handler.seen[1] >= 1

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


class TestCompiledXPath:
    def test_scalar(self):
        from leptris import XPath, fromstring

        root = fromstring("<r><a>1</a><a>2</a></r>")
        query = XPath("count(//a)")
        assert query(root) == 2.0
        assert query(root) == 2.0  # reusable

    def test_nodeset(self):
        from leptris import XPath, fromstring

        root = fromstring("<r><a id='1'>x</a><a id='2'>y</a></r>")
        query = XPath("//a[@id='2']")
        assert query(root)[0].text == "y"

    def test_document_argument(self):
        from leptris import XPath, Document

        with Document.parse("<r><a/></r>") as doc:
            assert len(XPath("//a")(doc)) == 1

    def test_context_element(self):
        from leptris import XPath, fromstring

        root = fromstring("<r><b id='1'/><b id='2'/></r>")
        assert XPath("string(@id)")(root[1]) == "2"

    def test_namespaces(self):
        from leptris import XPath, fromstring

        root = fromstring("<x:r xmlns:x='urn:x'><x:a/></x:r>")
        query = XPath("count(//x:a)")
        assert query(root, namespaces={"x": "urn:x"}) == 1.0

    def test_invalid_expression_raises(self):
        from leptris import XPath
        from leptris.error import XPathError

        with pytest.raises(XPathError):
            XPath("///[")

    def test_repr(self):
        from leptris import XPath

        assert repr(XPath("//a")) == "<XPath '//a'>"

