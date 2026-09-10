"""Schematron validation (leptris.Schematron, libleptris 1.9.126+)."""

import pytest

from leptris import Document, Schematron
from leptris.error import SchematronError

SCHEMA = """<schema xmlns='http://purl.oclc.org/dsdl/schematron' queryBinding='xslt'>
  <pattern>
    <rule context='item'>
      <assert test='@n &lt;= 3'>n too big</assert>
    </rule>
  </pattern>
</schema>"""


def test_valid_and_invalid_verdicts():
    sch = Schematron(SCHEMA)
    assert sch.is_valid(Document.parse("<r><item n='2'/></r>")) is True
    assert sch.is_valid(Document.parse("<r><item n='9'/></r>")) is False


def test_validate_returns_svrl_document():
    sch = Schematron(SCHEMA)
    svrl = sch.validate(Document.parse("<r><item n='9'/></r>"))
    assert svrl is not None
    assert float(svrl.xpath(
        "count(//*[local-name()='schematron-output'])")) == 1
    assert float(svrl.xpath(
        "count(//*[local-name()='failed-assert'])")) == 1
    assert svrl.xpath(
        "(//*[local-name()='failed-assert'])"
        "[1]/@location") == ["/r/item"]
    assert "n too big" in svrl.xpath(
        "string((//*[local-name()='failed-assert'])"
        "[1]/*[local-name()='text'])")


def test_reports_do_not_invalidate():
    sch = Schematron("""<schema xmlns='http://purl.oclc.org/dsdl/schematron' queryBinding='xslt'>
      <pattern><rule context='item'><report test='@n'>has n</report></rule></pattern>
    </schema>""")
    doc = Document.parse("<r><item n='9'/></r>")
    assert sch.is_valid(doc) is True
    assert float(sch.validate(doc).xpath(
        "count(//*[local-name()='successful-report'])")) == 1


def test_phase_selection():
    sch = Schematron.from_phase("""<schema xmlns='http://purl.oclc.org/dsdl/schematron' queryBinding='xslt'>
      <phase id='quick'><active pattern='p1'/></phase>
      <pattern id='p1'><rule context='a'><assert test='@v'>a needs v</assert></rule></pattern>
      <pattern id='p2'><rule context='b'><assert test='@w'>b needs w</assert></rule></pattern>
    </schema>""", phase="quick")
    svrl = sch.validate(Document.parse("<r><a/><b/></r>"))
    assert "a needs v" in svrl.xpath(
        "string((//*[local-name()='failed-assert'])"
        "[1]/*[local-name()='text'])")
    assert float(svrl.xpath(
        "count(//*[local-name()='failed-assert'])")) == 1


def test_schema_errors_raise_with_detail():
    with pytest.raises(SchematronError, match="queryBinding"):
        Schematron("""<schema xmlns='http://purl.oclc.org/dsdl/schematron' queryBinding='xpath2'>
          <pattern><rule context='/'><assert test='true()'/></rule></pattern>
        </schema>""")


def test_from_file(tmp_path):
    path = tmp_path / "schema.sch"
    path.write_text(SCHEMA)
    sch = Schematron.from_file(path)
    assert sch.is_valid(Document.parse("<r><item n='9'/></r>")) is False
