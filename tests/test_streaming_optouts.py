"""The streaming Door A opt-outs (leptris/leptris#1459, 1.9.284+):
skip_dup_detection / skip_source_positions on iterparse, sax.parse,
StreamingParser, and records — the same bits as the DOM-path
Document.parse options."""

import io

import pytest

from leptris import iterparse, sax
from leptris.error import ParseError

DUP = "<r><i a='1' a='2'/></r>"


class TestIterparseDupDetection:
    def test_plain_fails_the_walk(self):
        with pytest.raises(ParseError):
            list(iterparse(io.StringIO(DUP)))

    def test_flagged_admits_first_value(self):
        got = [(ev, el.tag, el.get("a"))
               for ev, el in iterparse(
                   io.StringIO(DUP), skip_dup_detection=True)]
        assert got == [("end", "i", "1")]

    def test_flagged_file_path(self, tmp_path):
        p = tmp_path / "dup.xml"
        p.write_text(DUP)
        got = [el.tag
               for _, el in iterparse(str(p), skip_dup_detection=True)]
        assert got == ["i"]

    def test_plain_file_path_still_fails(self, tmp_path):
        p = tmp_path / "dup.xml"
        p.write_text(DUP)
        with pytest.raises(ParseError):
            list(iterparse(str(p)))


class TestIterparsePositions:
    def test_flagged_parses_clean(self):
        doc = "<r>\n  <item id='1'>a</item>\n  <item id='2'>b</item>\n</r>"
        got = [(el.tag, el.get("id"), el.text)
               for _, el in iterparse(
                   io.StringIO(doc), skip_source_positions=True,
                   skip_dup_detection=True)]
        assert got == [("item", "1", "a"), ("item", "2", "b")]

    def test_both_flags_off_matches_default(self):
        doc = "<r><i v='1'/></r>"
        assert ([el.tag for _, el in iterparse(io.StringIO(doc))]
                == [el.tag for _, el in iterparse(
                    io.StringIO(doc), skip_dup_detection=True,
                    skip_source_positions=True)])


class TestSaxParse:
    def test_plain_reports_dup_attr(self):
        handler = sax.SAXHandler()
        with pytest.raises(ParseError):
            sax.parse(DUP, handler)

    def test_flagged_no_error(self):
        handler = sax.SAXHandler()
        sax.parse(DUP, handler, skip_dup_detection=True)
        assert handler.last_error is None

    def test_flagged_streaming(self):
        handler = sax.SAXHandler()
        parser = sax.StreamingParser(handler, skip_dup_detection=True)
        parser.feed(DUP, final=True)
        parser.close()
        assert handler.last_error is None

    def test_flagged_records_still_fails_dup(self):
        # 1.9.289 accepts the bits on clean input (#1472) but the
        # one-shot records face still fails the walk on a redefined
        # attribute — flagged sax.parse is the working skip path
        with pytest.raises(ParseError):
            sax.records(DUP, skip_dup_detection=True)

    def test_flagged_records_clean(self):
        recs = sax.records(
            "<r><i a='1'/></r>", skip_source_positions=True
        )
        elements = [r for r in recs if r.kind == "element"]
        assert [r.name for r in elements] == ["r", "i"]

    def test_flagged_parse_reuses_shared_recorder(self):
        # flags survive reset since #1472: flagged calls share one
        # recorder per combination like the unflagged path
        h = sax.SAXHandler()
        sax.parse(DUP, h, skip_dup_detection=True)
        first = sax._shared_flagged_recorders[8]
        sax.parse(DUP, h, skip_dup_detection=True)
        assert sax._shared_flagged_recorders[8] is first
