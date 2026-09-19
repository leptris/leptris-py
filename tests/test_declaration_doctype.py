"""Document-level XML declaration and DOCTYPE removal
(libleptris 1.9.204+)."""

import pytest

from leptris import Document, tostring
from leptris.error import LeptrisError


DECL_DOC = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<!DOCTYPE r [\n<!ELEMENT r (#PCDATA)>\n]>\n"
    "<r>text</r>"
)


class TestClearDeclaration:
    def test_declaration_removed_from_output(self):
        doc = Document.parse(DECL_DOC)
        out = tostring(doc)
        assert out.startswith(b"<?xml ")
        doc.clear_declaration()
        assert b"<?xml" not in tostring(doc)

    def test_idempotent(self):
        doc = Document.parse(DECL_DOC)
        doc.clear_declaration().clear_declaration()
        assert b"<?xml" not in tostring(doc)

    def test_closed_document_raises(self):
        doc = Document.parse("<r/>")
        doc.close()
        with pytest.raises(LeptrisError, match="closed"):
            doc.clear_declaration()


class TestRemoveDoctype:
    def test_doctype_removed_from_output(self):
        doc = Document.parse(DECL_DOC)
        assert b"DOCTYPE" in tostring(doc)
        assert doc.remove_doctype() is True
        assert b"DOCTYPE" not in tostring(doc)

    def test_no_doctype_returns_false(self):
        doc = Document.parse("<r/>")
        assert doc.remove_doctype() is False

    def test_content_survives(self):
        doc = Document.parse(DECL_DOC)
        doc.remove_doctype()
        assert doc.root.tag == "r"
        assert doc.root.text == "text"

    def test_closed_document_raises(self):
        doc = Document.parse("<r/>")
        doc.close()
        with pytest.raises(LeptrisError, match="closed"):
            doc.remove_doctype()
