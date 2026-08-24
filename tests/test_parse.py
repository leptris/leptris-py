"""Parsing and document lifecycle."""

import io

import pytest

from leptris import Document, fromstring, parse
from leptris import LeptrisError, ParseError

XML = "<library><book id='1'>Ulysses</book></library>"


class TestFromString:
    def test_returns_root_element(self):
        root = fromstring(XML)
        assert root.tag == "library"
        assert root[0].tag == "book"

    def test_str_and_bytes_agree(self):
        assert fromstring(XML)[0].text == fromstring(XML.encode())[0].text

    def test_bytes_only_doctype(self):
        assert fromstring(b"<?xml version='1.0'?><r/>").tag == "r"

    def test_type_error_on_non_string(self):
        with pytest.raises(TypeError):
            fromstring(123)

    def test_parse_error_raises(self):
        with pytest.raises(ParseError):
            fromstring("<unclosed>")

    def test_parse_error_message_names_cause(self):
        with pytest.raises(ParseError, match="parse error"):
            fromstring("<a></b>")


class TestParse:
    def test_path(self, tmp_path):
        path = tmp_path / "doc.xml"
        path.write_text(XML)
        with parse(str(path)) as doc:
            assert doc.getroot().tag == "library"

    def test_pathlib_object(self, tmp_path):
        path = tmp_path / "doc.xml"
        path.write_text(XML)
        with parse(path) as doc:
            assert doc.getroot().tag == "library"

    def test_file_like(self):
        with parse(io.StringIO(XML)) as doc:
            assert doc.getroot().tag == "library"
        with parse(io.BytesIO(XML.encode())) as doc:
            assert doc.getroot().tag == "library"

    def test_missing_file(self):
        with pytest.raises(ParseError):
            parse("/nonexistent/doc.xml")


class TestDocument:
    def test_parse_classmethod(self):
        with Document.parse(XML) as doc:
            assert doc.getroot().tag == "library"
            assert doc.root.tag == "library"

    def test_comment_only_document_is_not_well_formed(self):
        # XML requires a root element.
        with pytest.raises(ParseError):
            Document.parse("<!-- nothing -->")

    def test_close_is_idempotent(self):
        doc = Document.parse("<r/>")
        doc.close()
        doc.close()
        assert doc.closed

    def test_context_manager_closes(self):
        with Document.parse("<r/>") as doc:
            assert not doc.closed
        assert doc.closed

    def test_elements_keep_document_alive(self):
        root = Document.parse("<r><a/></r>").getroot()
        assert root[0].getparent().tag == "r"

    def test_access_after_close_raises(self):
        doc = Document.parse("<r/>")
        root = doc.getroot()
        doc.close()
        with pytest.raises(LeptrisError):
            root.tag
        with pytest.raises(LeptrisError):
            doc.xpath("//r")


def test_libleptris_version():
    from leptris import libleptris_version

    assert isinstance(libleptris_version(), str)
    assert libleptris_version() != ""

class TestRecover:
    def test_malformed_raises_without_recover(self):
        with pytest.raises(ParseError):
            Document.parse("<broken")

    def test_recover_yields_rootless_document(self):
        doc = Document.parse("<broken", recover=True)
        assert doc.getroot() is None
        doc.close()

    def test_recover_accepts_valid_document(self):
        with Document.parse("<r><a/></r>", recover=True) as doc:
            assert doc.xpath("count(//a)") == 1.0

