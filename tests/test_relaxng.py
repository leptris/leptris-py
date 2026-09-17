"""RELAX NG validation (leptris.RelaxNG, libleptris 1.9.115+)."""

import sys

import pytest

from leptris import Document, RelaxNG
from leptris.error import LeptrisError, RelaxNGError

SCHEMA = """<element name='library' xmlns='http://relaxng.org/ns/structure/1.0'>
  <oneOrMore><element name='book'>
    <attribute name='id'><data type='nonNegativeInteger'/></attribute>
    <optional><element name='title'><text/></element></optional>
    <element name='author'><text/></element>
  </element></oneOrMore>
</element>"""

VALID = "<library><book id='1'><title>T</title><author>A</author></book></library>"
VALID_OPTIONAL_OMITTED = "<library><book id='1'><author>A</author></book></library>"
INVALID_MISSING_REQUIRED = "<library><book id='1'><title>T</title></book></library>"
INVALID_WRONG_ROOT = "<catalog/>"


class TestRelaxNG:
    def test_valid_documents(self):
        v = RelaxNG(SCHEMA)
        for doc in (VALID, VALID_OPTIONAL_OMITTED):
            with Document.parse(doc) as d:
                assert v.validate(d) is True
                assert v.error_log == []

    def test_invalid_documents_report_errors(self):
        v = RelaxNG(SCHEMA)
        with Document.parse(INVALID_MISSING_REQUIRED) as d:
            assert v.validate(d) is False
            (entry,) = v.error_log
            assert entry.line == 1
            assert entry.message == (
                'element "book" incomplete; missing required element '
                '"author"'
            )
        with Document.parse(INVALID_WRONG_ROOT) as d:
            assert v.validate(d) is False
            (entry,) = v.error_log
            assert entry.message == (
                'element "catalog" not allowed anywhere; expected '
                'element "library"'
            )

    def test_error_log_accumulates_with_jing_positions(self):
        # libleptris 1.9.179+ (#878): every failure from the last
        # validate call, Jing-compatible line/column + vocabulary.
        rng = (
            "<element name='r' "
            "xmlns='http://relaxng.org/ns/structure/1.0'>"
            "<choice><element name='a'/><element name='b'/></choice>"
            "<element name='c'/></element>"
        )
        v = RelaxNG(rng)
        with Document.parse("<r><c/><c/><z/></r>") as d:
            assert v.validate(d) is False
        assert [(e.line, e.column, e.message) for e in v.error_log] == [
            (1, 8, 'element "c" not allowed yet; missing required element "a"'),
            (1, 12, 'element "c" not allowed here; expected the element end-tag'),
            (1, 16, 'element "z" not allowed anywhere; expected the element end-tag'),
        ]

    def test_error_log_resets_between_validations(self):
        v = RelaxNG(SCHEMA)
        with Document.parse(INVALID_WRONG_ROOT) as d:
            assert v.validate(d) is False
            assert v.error_log
        with Document.parse(VALID) as d:
            assert v.validate(d) is True
            assert v.error_log == []

    def test_schema_parse_error_raises(self):
        with pytest.raises(RelaxNGError) as info:
            RelaxNG("<not-a-schema")
        assert isinstance(info.value, LeptrisError)

    def test_from_file(self):
        import tempfile, os

        with tempfile.NamedTemporaryFile(
            "w", suffix=".rng", delete=False
        ) as f:
            f.write(SCHEMA)
            path = f.name
        try:
            assert RelaxNG.from_file(path).validate(
                Document.parse(VALID)
            ) is True
        finally:
            os.unlink(path)

    def test_validate_on_closed_document_raises(self):
        v = RelaxNG(SCHEMA)
        with Document.parse(VALID) as d:
            pass
        with pytest.raises(RelaxNGError):
            v.validate(d)

class TestRelaxNGV188:
    """v1.9.187/188 engine features: externalRef, anyName, and
    foreign-namespace annotation skipping."""

    def _tmp_schema(self, files, main="main.rng"):
        import tempfile, os

        d = tempfile.mkdtemp()
        for name, text in files.items():
            with open(os.path.join(d, name), "w") as f:
                f.write(text)
        return os.path.join(d, main), d

    def test_external_ref_bare_root(self):
        # bare-<element> schema with nested externalRef (the #1155
        # engine fix; grammar-root schemas worked from the start)
        path, d = self._tmp_schema({
            "main.rng": (
                "<element name='library' "
                "xmlns='http://relaxng.org/ns/structure/1.0'>"
                "<oneOrMore><externalRef href='book.rng'/>"
                "</oneOrMore></element>"
            ),
            "book.rng": (
                "<element name='book' "
                "xmlns='http://relaxng.org/ns/structure/1.0'>"
                "<attribute name='id'><text/></attribute>"
                "<element name='title'><text/></element></element>"
            ),
        })
        try:
            v = RelaxNG.from_file(path)
            with Document.parse(
                "<library><book id='1'><title>T</title></book>"
                "<book id='2'><title>U</title></book></library>"
            ) as doc:
                assert v.validate(doc) is True
            with Document.parse("<library><book id='1'/></library>") as doc:
                assert v.validate(doc) is False
                (entry,) = v.error_log
                assert entry.message == (
                    'element "book" incomplete; missing required '
                    'element "title"'
                )
        finally:
            import shutil

            shutil.rmtree(d)

    def test_any_name_elements_and_attributes(self):
        rng = (
            "<element name='bag' "
            "xmlns='http://relaxng.org/ns/structure/1.0'>"
            "<zeroOrMore><element><anyName/>"
            "<zeroOrMore><attribute><anyName/></attribute>"
            "</zeroOrMore><text/></element></zeroOrMore></element>"
        )
        v = RelaxNG(rng)
        with Document.parse(
            "<bag><x a='1'>t</x><y>u</y></bag>"
        ) as doc:
            assert v.validate(doc) is True


    def test_attribute_group_behind_ref(self):
        # v1.9.191: attribute lists behind a <ref> are consumed —
        # documents carrying the referenced attributes validate
        # (190 rejected them). The omitted-required-attribute verdict
        # is still upstream (leptris/leptris#1164) — not pinned here.
        rng = (
            "<grammar xmlns='http://relaxng.org/ns/structure/1.0'>"
            "<define name='attrs'>"
            "<attribute name='id'><text/></attribute>"
            "<attribute name='lang'><text/></attribute>"
            "</define><start><element name='doc'>"
            "<ref name='attrs'/>"
            "<element name='body'><text/></element>"
            "</element></start></grammar>"
        )
        v = RelaxNG(rng)
        with Document.parse(
            "<doc id='1' lang='en'><body>b</body></doc>"
        ) as doc:
            assert v.validate(doc) is True
            assert v.error_log == []
        # extra attributes beyond the referenced list still fail
        with Document.parse(
            "<doc id='1' lang='en' bogus='x'><body>b</body></doc>"
        ) as doc:
            assert v.validate(doc) is False

    def test_foreign_namespace_annotations_skipped(self):
        rng = (
            "<element name='doc' "
            "xmlns='http://relaxng.org/ns/structure/1.0' "
            "xmlns:a='urn:ann'>"
            "<a:note>annotation content</a:note>"
            "<element name='body'><text/></element></element>"
        )
        v = RelaxNG(rng)
        with Document.parse("<doc><body>b</body></doc>") as doc:
            assert v.validate(doc) is True
