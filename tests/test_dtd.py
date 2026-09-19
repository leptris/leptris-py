"""DTD validation (libleptris 1.9.202+): standalone DTDs,
document internal subsets, external subsets and parameter-entity
loaders (application-owned I/O)."""

import pytest

from leptris import DTDError, DTDErrorEntry, Document, DTD, fromstring


BOOK_DTD = """<!ELEMENT book (title, author+, isbn?)>
<!ATTLIST book id ID #REQUIRED>"""

BOOK_DOC = '<book id="b1"><title>T</title><author>A</author></book>'


class TestStandaloneDTD:
    def test_valid_document(self):
        dtd = DTD(BOOK_DTD)
        assert dtd.validate(fromstring(BOOK_DOC)) is True
        assert dtd.error_log == []

    def test_missing_required_attribute(self):
        dtd = DTD(BOOK_DTD)
        doc = fromstring(
            "<book><title>T</title><author>A</author></book>"
        )
        assert dtd.validate(doc) is False
        (entry,) = dtd.error_log
        assert isinstance(entry, DTDErrorEntry)
        assert "id" in entry.message or "attribute" in entry.message.lower()

    def test_content_model_violation(self):
        dtd = DTD(BOOK_DTD)
        doc = fromstring(
            '<book id="x"><title>T</title></book>'
        )
        assert dtd.validate(doc) is False
        (entry,) = dtd.error_log
        assert entry.element == "book"
        assert "author" in entry.message

    def test_element_argument_uses_its_document(self):
        # RelaxNG parity: an Element resolves to its document and
        # the whole document is validated
        dtd = DTD(BOOK_DTD)
        doc = fromstring(BOOK_DOC)
        assert dtd.validate(doc[0]) is True

    def test_from_file(self, tmp_path):
        path = tmp_path / "book.dtd"
        path.write_text(BOOK_DTD)
        assert DTD.from_file(str(path)).validate(fromstring(BOOK_DOC))

    def test_accepts_bytes_and_bytearray(self):
        assert DTD(BOOK_DTD.encode()).validate(fromstring(BOOK_DOC))
        assert DTD(bytearray(BOOK_DTD.encode())).validate(
            fromstring(BOOK_DOC)
        )

    def test_rejects_other_types(self):
        with pytest.raises(TypeError):
            DTD(42)

    def test_closed_document_raises(self):
        dtd = DTD(BOOK_DTD)
        doc = Document.parse(BOOK_DOC)
        doc.close()
        with pytest.raises(DTDError, match="closed"):
            dtd.validate(doc)

    def test_error_entry_repr(self):
        dtd = DTD(BOOK_DTD)
        dtd.validate(fromstring("<book><title>T</title></book>"))
        (entry,) = dtd.error_log
        assert "DTDErrorEntry(" in repr(entry)


class TestInternalSubset:
    DOC_VALID = """<?xml version="1.0"?>
<!DOCTYPE book [
<!ELEMENT book (title, author)>
<!ATTLIST book id ID #REQUIRED>
]>
<book id="x"><title>T</title><author>A</author></book>"""

    def test_document_dtd_validates(self):
        doc = Document.parse(self.DOC_VALID)
        assert DTD.from_document(doc).validate(doc) is True

    def test_document_dtd_invalidates(self):
        text = self.DOC_VALID.replace('<book id="x">', "<book>")
        doc = Document.parse(text)
        dtd = DTD.from_document(doc)
        assert dtd.validate(doc) is False
        assert dtd.error_log[0].element == "book"

    def test_pins_the_owning_document(self):
        # from_document on a temporary: the wrapper must keep the
        # document (and its DTD) alive or the handle dangles
        dtd = DTD.from_document(Document.parse(self.DOC_VALID))
        doc = Document.parse(self.DOC_VALID)
        assert dtd.validate(doc) is True


class TestExternalSubset:
    DOC = """<?xml version="1.0"?>
<!DOCTYPE note [
<!ELEMENT note (to)>
]>
<note><to>You</to></note>"""

    def test_merge_extends_the_internal_subset(self):
        doc = Document.parse(self.DOC)
        dtd = DTD.from_document(doc)
        dtd.parse_external_subset(
            "<!ELEMENT to (#PCDATA)><!ELEMENT from (#PCDATA)>"
        )
        assert dtd.validate(doc) is True

    def test_first_declaration_wins(self):
        doc = Document.parse(self.DOC)
        dtd = DTD.from_document(doc)
        dtd.parse_external_subset(
            "<!ELEMENT to (#PCDATA)><!ELEMENT note EMPTY>"
        )
        # the internal subset's note (to) survives the external
        # <!ELEMENT note EMPTY> — first declaration wins
        assert dtd.validate(doc) is True


class TestPELoader:
    DOC = """<!DOCTYPE d [
<!ELEMENT d (e)>
]>
<d><e>hi</e></d>"""

    EXT = '<!ENTITY % model SYSTEM "m.ent"><!ELEMENT e %model;>'

    def test_loader_supplies_the_model(self):
        doc = Document.parse(self.DOC)
        dtd = DTD.from_document(doc)
        calls = []
        dtd.set_pe_loader(
            lambda sys_id: (calls.append(sys_id), b"EMPTY")[1]
        )
        dtd.parse_external_subset(self.EXT)
        assert calls == ["m.ent"]
        assert dtd.validate(doc) is False  # <e>hi</e> vs EMPTY
        (entry,) = dtd.error_log
        assert "EMPTY" in entry.message

    def test_loader_none_skips_the_reference(self):
        doc = Document.parse(self.DOC)
        dtd = DTD.from_document(doc)
        dtd.set_pe_loader(lambda sys_id: None)
        dtd.parse_external_subset(self.EXT)
        assert dtd.validate(doc) is True  # lenient: model unresolved

    def test_clearing_the_loader(self):
        doc = Document.parse(self.DOC)
        dtd = DTD.from_document(doc)
        dtd.set_pe_loader(lambda sys_id: b"EMPTY")
        dtd.set_pe_loader(None)
        dtd.parse_external_subset(self.EXT)
        assert dtd.validate(doc) is True  # cleared: unresolved again
