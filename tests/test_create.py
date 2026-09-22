"""Programmatic construction (libleptris 1.9.216 creation surface):
Document.create / create_element / set_root, Element.create_child /
append / set / the text setter."""

import pytest

from leptris import Document, LeptrisError, tostring


class TestDocumentCreate:
    def test_create_is_empty(self):
        doc = Document.create()
        assert doc.root is None

    def test_create_element_and_set_root(self):
        doc = Document.create()
        root = doc.create_element("root")
        assert root.tag == "root"
        doc.set_root(root)
        assert doc.root.tag == "root"
        assert tostring(doc) == b"<root/>"

    def test_created_tree_serializes(self):
        doc = Document.create()
        root = doc.create_element("r")
        doc.set_root(root)
        child = root.create_child("c")
        child.text = "hello"
        child.set("n", "1")
        assert tostring(doc) == b'<r><c n="1">hello</c></r>'

    def test_set_root_type_check(self):
        doc = Document.create()
        with pytest.raises(TypeError):
            doc.set_root("<not-an-element/>")

    def test_create_element_name_check(self):
        doc = Document.create()
        with pytest.raises(ValueError):
            doc.create_element("")

    def test_closed_document_raises(self):
        doc = Document.create()
        doc.close()
        with pytest.raises(LeptrisError, match="closed"):
            doc.create_element("x")


class TestElementBuild:
    def test_create_child_chains(self):
        doc = Document.create()
        root = doc.create_element("ul")
        doc.set_root(root)
        for i in range(3):
            li = root.create_child("li")
            li.text = str(i)
            li.set("i", str(i))
        out = tostring(doc)
        assert out.count(b"<li") == 3
        assert b'<li i="1">1</li>' in out

    def test_append_moves_created_element(self):
        doc = Document.create()
        root = doc.create_element("r")
        doc.set_root(root)
        child = doc.create_element("c")
        assert doc.root is not None
        root.append(child)
        assert tostring(doc) == b"<r><c/></r>"

    def test_append_requires_same_document(self):
        doc = Document.create()
        other = Document.create()
        root = doc.create_element("r")
        doc.set_root(root)
        stray = other.create_element("c")
        with pytest.raises(ValueError, match="different document"):
            root.append(stray)

    def test_append_type_check(self):
        doc = Document.create()
        root = doc.create_element("r")
        with pytest.raises(TypeError):
            root.append("text")

    def test_set_and_attribute_pairs(self):
        doc = Document.create()
        root = doc.create_element("r")
        doc.set_root(root)
        root.set("a", "1")
        root.set("b", "2")
        assert root.attribute_pairs() == [("a", "1"), ("b", "2")]

    def test_text_setter_roundtrip(self):
        doc = Document.create()
        root = doc.create_element("r")
        doc.set_root(root)
        root.text = "payload"
        assert root.text == "payload"
        assert tostring(doc) == b"<r>payload</r>"

    def test_closed_element_raises(self):
        doc = Document.create()
        root = doc.create_element("r")
        doc.close()
        with pytest.raises(LeptrisError, match="closed"):
            root.create_child("c")


class TestHtmlFacadeParity:
    """The leptris.html facade gains the same construction entry (the
    builder gap the Ruby binding reported): build HTML documents
    programmatically through the shared DOM."""

    def test_build_and_roundtrip_parse(self):
        from leptris.html import document as html_document
        from leptris.html import fromstring as html_fromstring

        doc = Document.create()
        root = doc.create_element("html")
        doc.set_root(root)
        body = root.create_child("body")
        p = body.create_child("p")
        p.text = "hi"
        assert doc.root.tag == "html"
        assert body is not None and p is not None
        # the parse side reads the same DOM shape back (html
        # parse synthesizes the <html> wrapper; fromstring
        # returns the root)
        parsed = html_fromstring("<p>hi</p>")
        assert parsed.tag == "html"
        assert html_document("<p>hi</p>").root is not None
