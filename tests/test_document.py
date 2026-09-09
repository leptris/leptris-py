"""Document-level contract specs."""

from leptris import Document




class TestDocumentDoctype:
    def test_xml_doctype_with_ids(self):
        doc = b"<!DOCTYPE r PUBLIC '-//X//Y//EN' 'y.dtd'><r/>"
        with Document.parse(doc) as d:
            assert d.doctype == ("r", "-//X//Y//EN", "y.dtd")

    def test_absent_doctype_is_none(self):
        with Document.parse("<r/>") as d:
            assert d.doctype is None
