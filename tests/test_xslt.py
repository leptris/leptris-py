"""XSLT 1.0 transformation via the engine's compiled stylesheets."""

import pytest

from leptris import Document, XSLT, tostring, fromstring

IDENTITY = """<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="@* | node()">
    <xsl:copy><xsl:apply-templates select="@* | node()"/></xsl:copy>
  </xsl:template>
</xsl:stylesheet>"""

SELECT = """<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="/">
    <out><xsl:for-each select="//book[@price > 50]">
      <title><xsl:value-of select="title"/></title>
    </xsl:for-each></out>
  </xsl:template>
</xsl:stylesheet>"""


class TestXSLT:
    def test_identity_transform(self):
        # the serializer normalizes attribute quotes to double
        # quotes; compare trees, not bytes
        transform = XSLT(IDENTITY)
        with Document.parse(
            "<catalog><book id='1'>A</book></catalog>"
        ) as source:
            result = transform(source)
            root = result.getroot()
            assert root.tag == "catalog"
            assert root[0].tag == "book" and root[0].get("id") == "1"
            assert root[0].text == "A"
            result.close()

    def test_selection_produces_result_tree(self):
        transform = XSLT(SELECT)
        with Document.parse(
            "<catalog>"
            "<book price='10'><title>Cheap</title></book>"
            "<book price='90'><title>Pricey</title></book>"
            "</catalog>"
        ) as source:
            result = transform(source)
            root = result.getroot()
            assert root.tag == "out"
            assert [t.text for t in root] == ["Pricey"]
            result.close()

    def test_reusable_across_documents(self):
        transform = XSLT(IDENTITY)
        for xml in (b"<a/>", b"<b><c/></b>"):
            with Document.parse(xml) as source:
                result = transform(source)
                assert result.getroot().tag == xml.decode()[1]
                result.close()

    def test_element_argument_uses_its_document(self):
        transform = XSLT(IDENTITY)
        root = fromstring("<r><x/></r>")
        result = transform(root)
        got = result.getroot()
        assert got.tag == "r" and got[0].tag == "x"
        result.close()

    def test_bad_stylesheet_raises(self):
        with pytest.raises(Exception):
            XSLT("<not-a-stylesheet/>")

    def test_exslt_math_function(self):
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
          xmlns:math="http://exslt.org/math" exclude-result-prefixes="math">
          <xsl:template match="/">
            <out><xsl:value-of select="math:max(/r/v)"/></out>
          </xsl:template>
        </xsl:stylesheet>"""
        transform = XSLT(style)
        with Document.parse("<r><v>3</v><v>9</v><v>4</v></r>") as source:
            result = transform(source)
            assert result.getroot().text == "9"
            result.close()


class TestUpstreamV199Conformance:
    def test_xsl_copy_excludes_attributes(self):
        # libleptris 1.9.12 (bug-32-): xsl:copy copies the element
        # and namespaces but NOT attributes — they flow only through
        # apply-templates/@* (XSLT 7.5).
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><out>
            <xsl:for-each select="/r/e"><xsl:copy/></xsl:for-each>
          </out></xsl:template>
        </xsl:stylesheet>"""
        transform = XSLT(style)
        with Document.parse("<r><e a='1'>t</e></r>") as source:
            result = transform(source)
            copied = result.getroot()[0]
            assert copied.tag == "e" and copied.get("a") is None
            result.close()

    def test_apply_templates_text_rule(self):
        # libleptris 1.9.12 (bug-161): apply-templates over a
        # selected text item applies the built-in TEXT rule.
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><out>
            <xsl:apply-templates select="/r/t/text()"/>
          </out></xsl:template>
        </xsl:stylesheet>"""
        transform = XSLT(style)
        with Document.parse("<r><t>kept</t></r>") as source:
            result = transform(source)
            assert result.getroot().text.strip() == "kept"
            result.close()
