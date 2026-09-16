"""RELAX NG validation (leptris.RelaxNG, libleptris 1.9.115+)."""

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
