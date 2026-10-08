"""XSD tier 1 (libleptris 1.9.319+, #1075): schema compilation and
lexical validation of built-in and user simple types."""

import pytest

from leptris import XSD
from leptris.error import XSDError

SCHEMA = """\
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="root"/>
  <xs:simpleType name="score">
    <xs:restriction base="xs:integer">
      <xs:minInclusive value="0"/>
      <xs:maxInclusive value="100"/>
    </xs:restriction>
  </xs:simpleType>
  <xs:simpleType name="code">
    <xs:restriction base="xs:string">
      <xs:pattern value="[A-Z]{3}"/>
    </xs:restriction>
  </xs:simpleType>
</xs:schema>
"""


class TestCompile:
    def test_valid_schema(self):
        xsd = XSD(SCHEMA)
        assert xsd.declaration_count >= 3
        assert xsd.error() is None
        xsd.close()

    def test_invalid_schema_raises(self):
        with pytest.raises(XSDError):
            XSD("<not-a-schema/>")

    def test_error_carrying_handle_message(self):
        # xsd_compile returns an error-carrying handle; the error
        # detail surfaces in the raised message
        with pytest.raises(XSDError) as exc:
            XSD("<not-a-schema/>")
        assert str(exc.value)


class TestBuiltinValid:
    def test_integers(self):
        xsd = XSD(SCHEMA)
        assert xsd.valid_builtin("xs:integer", "42") is True
        assert xsd.valid_builtin("xs:integer", "-7") is True
        assert xsd.valid_builtin("xs:integer", "4.5") is False
        assert xsd.valid_builtin("xs:integer", "nope") is False

    def test_other_builtins(self):
        xsd = XSD(SCHEMA)
        assert xsd.valid_builtin("xs:boolean", "true") is True
        assert xsd.valid_builtin("xs:boolean", "1") is True
        assert xsd.valid_builtin("xs:boolean", "yes") is False
        assert xsd.valid_builtin("xs:date", "2026-10-08") is True

    def test_unknown_builtin_returns_none(self):
        xsd = XSD(SCHEMA)
        assert xsd.valid_builtin("xs:not-a-type", "1") is None

    def test_reference_spelling_required(self):
        xsd = XSD(SCHEMA)
        # the "xs:NAME" reference spelling is the documented form;
        # a bare name is not in the tier-1 table
        assert xsd.valid_builtin("integer", "42") is None


class TestSimpleValid:
    def test_facet_range(self):
        xsd = XSD(SCHEMA)
        assert xsd.valid("score", "0") is True
        assert xsd.valid("score", "100") is True
        assert xsd.valid("score", "-1") is False
        assert xsd.valid("score", "101") is False

    def test_facet_pattern(self):
        xsd = XSD(SCHEMA)
        assert xsd.valid("code", "ABC") is True
        assert xsd.valid("code", "AB") is False
        assert xsd.valid("code", "abcd") is False

    def test_unknown_type_returns_none(self):
        xsd = XSD(SCHEMA)
        assert xsd.valid("no-such-type", "1") is None

    def test_context_manager(self):
        with XSD(SCHEMA) as xsd:
            assert xsd.valid("score", "50") is True
