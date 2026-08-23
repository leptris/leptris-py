"""Serialization: tostring, write, canonical XML."""

import io

import pytest

from leptris import Document, c14n, fromstring, tostring
from leptris import LeptrisError

XML = "<a><b>1</b></a>"
COMMENT_XML = "<a><b>1</b><!-- note --></a>"


class TestTostring:
    def test_document_compact(self):
        assert tostring(Document.parse(XML)) == b"<a><b>1</b></a>"

    def test_element_subtree(self):
        root = fromstring("<r><a><b/></a></r>")
        assert tostring(root[0]) == b"<a><b/></a>"

    def test_unicode_mode(self):
        assert tostring(Document.parse(XML), encoding="unicode") == XML

    def test_encoding_implies_declaration(self):
        out = tostring(Document.parse(XML), encoding="utf-8")
        assert out.startswith(b"<?xml")
        assert out.endswith(b"<a><b>1</b></a>")

    def test_declaration_can_be_forced_or_suppressed(self):
        forced = tostring(Document.parse(XML), encoding="utf-8", xml_declaration=True)
        assert forced.startswith(b"<?xml")
        plain = tostring(Document.parse(XML), xml_declaration=True)
        assert plain.startswith(b"<?xml")
        none = tostring(Document.parse(XML), encoding="utf-8", xml_declaration=False)
        assert not none.startswith(b"<?xml")

    def test_pretty_print_indents(self):
        out = tostring(Document.parse(XML), pretty_print=True, encoding="unicode")
        assert "\n" in out and "  <b>" in out, out

    def test_round_trip(self):
        first = fromstring(XML)
        again = fromstring(tostring(first))
        assert again[0].text == "1"

    def test_type_error_on_garbage(self):
        with pytest.raises(TypeError):
            tostring("not-a-tree")

    def test_closed_document_raises(self):
        doc = Document.parse(XML)
        doc.close()
        with pytest.raises(LeptrisError):
            tostring(doc)


class TestWrite:
    def test_file_like(self):
        buffer = io.BytesIO()
        with Document.parse(XML) as doc:
            doc.write(buffer)
        assert buffer.getvalue() == b"<a><b>1</b></a>"

    def test_path(self, tmp_path):
        path = tmp_path / "out.xml"
        with Document.parse(XML) as doc:
            doc.write(str(path), pretty_print=True, xml_declaration=True)
        content = path.read_text()
        assert content.startswith("<?xml")
        assert "\n" in content

    def test_pathlib(self, tmp_path):
        path = tmp_path / "out.xml"
        with Document.parse(XML) as doc:
            doc.write(path)
        assert path.read_bytes() == b"<a><b>1</b></a>"

    def test_reparse_written_file(self, tmp_path):
        path = tmp_path / "out.xml"
        with Document.parse(XML) as doc:
            doc.write(path)
        with Document.parse_file(path) as doc2:
            assert doc2.xpath("count(//b)") == 1.0


class TestC14N:
    def test_strips_comments(self):
        out = c14n(Document.parse(COMMENT_XML))
        assert b"<!--" not in out
        assert b"<b>1</b>" in out

    def test_with_comments(self):
        out = c14n(Document.parse(COMMENT_XML), with_comments=True)
        assert b"<!-- note -->" in out

    def test_subtree(self):
        root = fromstring(COMMENT_XML)
        assert c14n(root[0]) == b"<b>1</b>"

    def test_exclusive_mode(self):
        out = c14n(Document.parse(COMMENT_XML), exclusive=True)
        assert b"<b>1</b>" in out

    def test_version_1_1(self):
        out = c14n(Document.parse(COMMENT_XML), version="1.1")
        assert b"<b>1</b>" in out

    def test_invalid_version(self):
        with pytest.raises(ValueError):
            c14n(Document.parse(XML), version="2.0")

    def test_type_error_on_garbage(self):
        with pytest.raises(TypeError):
            c14n("nope")

    def test_namespace_normalization(self):
        xml = "<x:a xmlns:x='urn:1' xmlns:y='urn:2'><x:b>1</x:b></x:a>"
        out = c14n(Document.parse(xml))
        # Canonical form renames prefixes to n0/n1 in namespace order.
        assert b"urn:1" in out and b"urn:2" in out
        assert b"<b>1</b>" in out
