"""The HTML builder, end to end (#1309/#1312): create_html
construction, HTML-by-default serialization for HTML documents,
forced/overridden methods, and save_html."""

import pytest

import leptris
from leptris import Document, LeptrisError, tostring
from leptris.html import create, document as html_document


class TestCreateHtml:
    def test_build_and_default_html_serialization(self):
        doc = create()
        root = doc.create_element("html")
        doc.set_root(root)
        body = root.create_child("body")
        p = body.create_child("p")
        p.text = "hi"
        p.create_child("br")
        # HTML documents serialize with void shapes by default
        assert leptris.tostring(doc) == b"<html><body><p>hi<br></p></body></html>"

    def test_build_empty(self):
        doc = create()
        assert doc.root is None

    def test_created_html_doc_is_independent(self):
        a, b = create(), create()
        a.set_root(a.create_element("html"))
        assert b.root is None


class TestMethodHtml:
    def test_forced_html_on_xml_document(self):
        doc = Document.parse("<r><a/></r>")
        assert tostring(doc, method="html") == b"<r><a></a></r>"

    def test_forced_html_on_element(self):
        doc = html_document("<p>hi<br>bye</p>")
        elem = doc.root[0]
        assert tostring(elem, method="html") == b"<body><p>hi<br>bye</p></body>"

    def test_xml_documents_stay_xml(self):
        doc = Document.parse("<r><a/></r>")
        assert tostring(doc) == b"<r><a/></r>"

    def test_parsed_html_serializes_html_by_default(self):
        doc = html_document("<p>hi<br>bye</p>")
        assert leptris.tostring(doc) == b"<html><body><p>hi<br>bye</p></body></html>"

    def test_unknown_method_rejected(self):
        doc = Document.parse("<r/>")
        with pytest.raises(ValueError, match="method"):
            tostring(doc, method="json")

    def test_write_method_html(self):
        import io

        doc = Document.parse("<r><a/></r>")
        buf = io.BytesIO()
        doc.write(buf, method="html")
        assert buf.getvalue() == b"<r><a></a></r>"


class TestSaveHtml:
    def test_save_html_writes_void_shapes(self, tmp_path):
        doc = Document.parse("<r><a/><br/></r>")
        path = tmp_path / "out.html"
        doc.save_html(str(path))
        assert path.read_bytes() == b'<r><a></a><br></r>'


def leptris_tostring(doc):
    return leptris.tostring(doc)
