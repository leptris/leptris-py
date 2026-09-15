"""Document-level contract specs."""

import pytest

from leptris import Document
from leptris.error import LeptrisError




class TestDocumentDoctype:
    def test_xml_doctype_with_ids(self):
        doc = b"<!DOCTYPE r PUBLIC '-//X//Y//EN' 'y.dtd'><r/>"
        with Document.parse(doc) as d:
            assert d.doctype == ("r", "-//X//Y//EN", "y.dtd")

    def test_absent_doctype_is_none(self):
        with Document.parse("<r/>") as d:
            assert d.doctype is None


class TestDeclarationReads:
    """Document.version/.standalone (node-surface parity, lib
    1.9.176+ / engine #1094)."""

    def test_version_present(self):
        with Document.parse(
            b'<?xml version="1.1"?><r/>'
        ) as doc:
            assert doc.version == "1.1"

    def test_version_absent(self):
        with Document.parse("<r/>") as doc:
            # no declaration -> engine default "1.0"
            assert doc.version in ("1.0", None)

    def test_standalone_yes(self):
        with Document.parse(
            b'<?xml version="1.0" standalone="yes"?><r/>'
        ) as doc:
            assert doc.standalone is True

    def test_standalone_no(self):
        with Document.parse(
            b'<?xml version="1.0" standalone="no"?><r/>'
        ) as doc:
            assert doc.standalone is False

    def test_standalone_absent(self):
        with Document.parse("<r/>") as doc:
            assert doc.standalone is None

    def test_closed_document_raises(self):
        doc = Document.parse("<r/>")
        doc.close()
        with pytest.raises(LeptrisError):
            doc.version
