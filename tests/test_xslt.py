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


class TestGoldenTransforms:
    """Golden outputs for representative XSLT constructs — chosen from
    a differential audit against lxml (11/12 constructs identical;
    the 12th, unknown-function handling, is leptris/leptris#625)."""

    def test_for_each_sort_descending(self):
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:for-each select="//book">
            <xsl:sort select="@price" data-type="number" order="descending"/>
            <b><xsl:value-of select="t"/></b>
          </xsl:for-each></o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse(
            "<r><book price='10'><t>A</t></book>"
            "<book price='90'><t>B</t></book>"
            "<book price='50'><t>C</t></book></r>"
        ) as src:
            r = XSLT(style)(src)
            assert [b.text for b in r.getroot()] == ["B", "C", "A"]
            r.close()

    def test_choose_when_otherwise(self):
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:for-each select="//b">
            <xsl:choose><xsl:when test="@p > 50">H</xsl:when>
            <xsl:otherwise>L</xsl:otherwise></xsl:choose>
          </xsl:for-each></o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><b p='10'/><b p='99'/><b p='50'/></r>") as src:
            r = XSLT(style)(src)
            assert r.getroot().text == "LHL"
            r.close()

    def test_apply_templates_with_mode(self):
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:apply-templates select="//i" mode="m"/></o></xsl:template>
          <xsl:template match="i" mode="m"><t><xsl:value-of select="@id"/></t></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><i id='a'/><i id='b'/></r>") as src:
            r = XSLT(style)(src)
            assert [t.text for t in r.getroot()] == ["a", "b"]
            r.close()

    def test_copy_of_deep_copies(self):
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:copy-of select="//e[2]"/></o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><e a='1'>x<c/></e><e a='2'>y<d/></e></r>") as src:
            r = XSLT(style)(src)
            e = r.getroot()[0]
            assert e.tag == "e" and e.get("a") == "2" and e[0].tag == "d"
            r.close()

    def test_position_and_last(self):
        # Fixed in libleptris 1.9.15 (#628): last() carries the
        # for-each context size.
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:for-each select="//b">
            <p><xsl:value-of select="concat(position(), '/', last())"/></p>
          </xsl:for-each></o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><b/><b/><b/></r>") as src:
            r = XSLT(style)(src)
            assert [p.text for p in r.getroot()] == ["1/3", "2/3", "3/3"]
            r.close()

    def test_unknown_function_raises(self):
        # Fixed in libleptris 1.9.15 (#627): unknown unprefixed
        # functions in stylesheet expressions are rejected.
        with pytest.raises(Exception):
            XSLT(
                "<xsl:stylesheet version='1.0' "
                "xmlns:xsl='http://www.w3.org/1999/XSL/Transform'>"
                "<xsl:template match='/'><o>"
                "<xsl:value-of select=\"upper-case('ab')\"/>"
                "</o></xsl:template></xsl:stylesheet>"
            )(fromstring("<r/>").document)

    def test_pretty_print_parity_with_lxml(self):
        # libleptris 1.9.16 (#633): comments and PIs under non-mixed
        # parents get their own indented line — byte-identical to
        # libxml2's xmlIndentTreeOutput.
        xml = b"<r><!-- c --><a/><!-- d --><b>t</b><!-- e --></r>"
        with Document.parse(xml) as doc:
            out = tostring(doc, pretty_print=True, encoding="unicode")
        # libxml2 appends a trailing newline after the root close;
        # the engine does not — the one byte-level difference
        assert out == (
            "<r>\n  <!-- c -->\n  <a/>\n  <!-- d -->\n  <b>t</b>\n  <!-- e -->\n</r>"
        )

    def test_call_template_with_param(self):
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:call-template name="emit">
            <xsl:with-param name="v" select="//b[1]/@id"/></xsl:call-template></o></xsl:template>
          <xsl:template name="emit"><xsl:param name="v"/>
            <e><xsl:value-of select="$v"/></e></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><b id='7'/></r>") as src:
            r = XSLT(style)(src)
            assert r.getroot()[0].text == "7"
            r.close()

    def test_attribute_construction(self):
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:for-each select="//b">
            <b id="{@id}"><xsl:attribute name="dyn">
              <xsl:value-of select="@p"/></xsl:attribute>t</b>
          </xsl:for-each></o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><b id='1' p='9'/></r>") as src:
            r = XSLT(style)(src)
            b = r.getroot()[0]
            assert b.get("id") == "1" and b.get("dyn") == "9" and b.text == "t"
            r.close()

    def test_nested_for_each_with_predicates(self):
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:for-each select="//b[@c='x']">
            <g><xsl:for-each select="../b[@c='y']"><k/></xsl:for-each></g>
          </xsl:for-each></o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><b c='x'/><b c='y'/><b c='y'/></r>") as src:
            r = XSLT(style)(src)
            g = r.getroot()[0]
            assert len(r.getroot()) == 1 and len(g) == 2
            r.close()
