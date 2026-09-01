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
        # functions in stylesheet expressions are rejected. NOTE:
        # upper-case became a REAL XPath 2.0 function in 1.9.24 —
        # the probe uses a name no spec defines.
        with pytest.raises(Exception):
            XSLT(
                "<xsl:stylesheet version='1.0' "
                "xmlns:xsl='http://www.w3.org/1999/XSL/Transform'>"
                "<xsl:template match='/'><o>"
                "<xsl:value-of select=\"definitely-not-a-fn(1)\"/>"
                "</o></xsl:template></xsl:stylesheet>"
            )(fromstring("<r/>").document)

    def test_xpath20_upper_case(self):
        # libleptris 1.9.24: upper-case/lower-case are real XPath
        # 2.0 functions (they previously triggered the unknown-fn
        # rejection pinned above).
        style = """<xsl:stylesheet version="1.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><xsl:value-of select="upper-case(/r/t)"/></o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><t>shout</t></r>") as src:
            r = XSLT(style)(src)
            assert r.getroot().text == "SHOUT"
            r.close()

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


class TestXSLT30:
    """XSLT 3.0 / XPath 2.0+ features (libleptris 1.9.23-1.9.25) —
    they flow through leptris.XSLT with no binding change."""

    def test_if_then_else(self):
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o>
            <xsl:value-of select="if (count(//i) > 1) then 'many' else 'few'"/>
          </o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><i>a</i><i>b</i></r>") as src:
            r = XSLT(style)(src)
            assert r.getroot().text == "many"
            r.close()
        with Document.parse("<r><i>a</i></r>") as src:
            r = XSLT(style)(src)
            assert r.getroot().text == "few"
            r.close()

    def test_iterate(self):
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o>
            <xsl:iterate select="//i"><k><xsl:value-of select="."/></k></xsl:iterate>
          </o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><i>a</i><i>b</i></r>") as src:
            r = XSLT(style)(src)
            assert [k.text for k in r.getroot()] == ["a", "b"]
            r.close()

    def test_for_return_sequence(self):
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o>
            <xsl:value-of select="string-join(for $i in (1 to 3) return concat('n', $i), ',')"/>
          </o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r/>") as src:
            r = XSLT(style)(src)
            assert r.getroot().text == "n1,n2,n3"
            r.close()


class TestXSLT30Increment45:
    """libleptris 1.9.26-1.9.27: xsl:try/catch scaffolding and
    xsl:on-empty — pinned through the binding."""

    def test_try_non_error_path(self):
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o>
            <xsl:try><ok/><xsl:catch><c/></xsl:catch></xsl:try>
          </o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r/>") as src:
            r = XSLT(style)(src)
            assert [c.tag for c in r.getroot()] == ["ok"]
            r.close()

    def test_error_in_select_caught(self):
        # Fixed in libleptris 1.9.30 (leptris/leptris#669): in the
        # canonical form (catch as a child of try) error() inside a
        # value-of select runs the catch; $err:description carries
        # the message.
        for select in ("error('boom')", "error(concat('b','oom'))"):
            style = """<xsl:stylesheet version="3.0"
              xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
              <xsl:template match="/"><o>
                <xsl:try><xsl:value-of select="%s"/>
                  <xsl:catch><caught><xsl:value-of select="$err:description"/></caught></xsl:catch>
                </xsl:try>
              </o></xsl:template>
            </xsl:stylesheet>""" % select
            with Document.parse("<r/>") as src:
                r = XSLT(style)(src)
                caught = r.getroot()[0]
                assert caught.tag == "caught" and caught.text == "boom"
                r.close()

    def test_error_variable_argument_caught(self):
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o>
            <xsl:variable name="msg" select="'va boom'"/>
            <xsl:try><xsl:value-of select="error($msg)"/>
              <xsl:catch><caught><xsl:value-of select="$err:description"/></caught></xsl:catch>
            </xsl:try>
          </o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r/>") as src:
            r = XSLT(style)(src)
            caught = r.getroot()[0]
            assert caught.tag == "caught" and caught.text == "va boom"
            r.close()

    def test_misplaced_catch_is_compile_error(self):
        # leptris/leptris#669 follow-up (1.9.30): a catch anywhere
        # but a child of xsl:try is a compile error — Saxon's
        # XTSE0010. The old silently-skipped sibling form.
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o>
            <xsl:try><ok/></xsl:try><xsl:catch><c/></xsl:catch>
          </o></xsl:template>
        </xsl:stylesheet>"""
        from leptris.error import LeptrisError

        with pytest.raises(LeptrisError):
            XSLT(style)

    def test_on_empty_fallback(self):
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:template match="/"><o><e>
            <xsl:on-empty>fallback</xsl:on-empty>
          </e></o></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r/>") as src:
            r = XSLT(style)(src)
            assert r.getroot()[0].text == "fallback"
            r.close()


class TestXSLT30Increment6:
    """libleptris 1.9.28: xsl:accumulator (3.0 §18.2) — pinned
    through the binding."""

    def test_accumulator_depth(self):
        # libleptris 1.9.28 (sixth increment, 18.2): xsl:accumulator
        # before/after folds over the event stream; the mode's
        # use-accumulators gate makes the accumulator applicable.
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:mode use-accumulators="depth"/>
          <xsl:accumulator name="depth" initial-value="0">
            <xsl:accumulator-rule match="*" phase="start" select="$value + 1"/>
            <xsl:accumulator-rule match="*" phase="end" select="$value - 1"/>
          </xsl:accumulator>
          <xsl:template match="/"><out>
            <xsl:for-each select="//item"><i n="{@n}"
              b="{accumulator-before('depth')}" a="{accumulator-after('depth')}"/>
            </xsl:for-each>
          </out></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><a><item n='1'/><item n='2'/></a><b><item n='3'/></b></r>") as src:
            r = XSLT(style)(src)
            assert [(i.get("n"), i.get("b"), i.get("a")) for i in r.getroot()] == [
                ("1", "3", "2"), ("2", "3", "2"), ("3", "3", "2"),
            ]
            r.close()

    def test_accumulator_running_sum(self):
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:mode use-accumulators="total"/>
          <xsl:accumulator name="total" initial-value="0">
            <xsl:accumulator-rule match="item" select="$value + @n"/>
          </xsl:accumulator>
          <xsl:template match="/"><out>
            <xsl:for-each select="//item"><t n="{@n}"
              b="{accumulator-before('total')}" a="{accumulator-after('total')}"/>
            </xsl:for-each>
          </out></xsl:template>
        </xsl:stylesheet>"""
        with Document.parse("<r><a><item n='1'/><item n='2'/></a><b><item n='3'/></b></r>") as src:
            r = XSLT(style)(src)
            assert [(t.get("n"), t.get("b"), t.get("a")) for t in r.getroot()] == [
                ("1", "1", "1"), ("2", "3", "3"), ("3", "6", "6"),
            ]
            r.close()

    def test_accumulator_requires_mode_gate(self):
        # Without xsl:mode use-accumulators the accumulator is not
        # applicable to the principal document (XTDE3362).
        style = """<xsl:stylesheet version="3.0"
          xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
          <xsl:accumulator name="depth" initial-value="0">
            <xsl:accumulator-rule match="*" phase="start" select="$value + 1"/>
          </xsl:accumulator>
          <xsl:template match="/"><out>
            <xsl:value-of select="accumulator-before('depth')"/>
          </out></xsl:template>
        </xsl:stylesheet>"""
        from leptris.error import LeptrisError

        with Document.parse("<r/>") as src:
            with pytest.raises(LeptrisError):
                XSLT(style)(src)

class TestXSLTVersionCoverage:
    """Gap-coverage goldens for 2.0/3.0 constructs verified working
    through the binding on libleptris 1.9.32 (audit for #685)."""

    SRC = "<r><item v='1'>alpha</item><item v='5'>beta</item><item v='9'>gamma</item></r>"

    def _run(self, body, src=None):
        style = (
            '<xsl:stylesheet version="3.0"'
            ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
            "<xsl:template match=\"/\"><o>%s</o></xsl:template></xsl:stylesheet>" % body
        )
        with Document.parse(src or self.SRC) as d:
            out = XSLT(style)(d)
            result = tostring(out).decode()
            out.close()
            return result

    def test_for_each_group_group_by(self):
        assert self._run(
            '<xsl:for-each-group select="//item" group-by="@v">'
            "<g><xsl:value-of select='current-grouping-key()'/></g>"
            "</xsl:for-each-group>"
        ) == "<o><g>1</g><g>5</g><g>9</g></o>"

    def test_analyze_string_and_regex_group(self):
        assert self._run(
            "<xsl:analyze-string select=\"'ab12cd'\" regex=\"([0-9]+)\">"
            "<xsl:matching-substring><n><xsl:value-of select='regex-group(1)'/></n></xsl:matching-substring>"
            "<xsl:non-matching-substring><xsl:value-of select='.'/></xsl:non-matching-substring>"
            "</xsl:analyze-string>"
        ) == "<o>ab<n>12</n>cd</o>"

    def test_evaluate_literal_query(self):
        # xsl:evaluate (3.0 26.1): @xpath is the query itself here
        # (literal attribute text), evaluated against the context.
        assert self._run('<xsl:evaluate xpath="count(//item)"/>') == "<o>3</o>"

    def test_assert_passes(self):
        assert self._run(
            '<xsl:assert test="count(//item) = 3"/><ok/>'
        ) == "<o><ok/></o>"

    def test_where_populated_drops_all_content(self):
        # leptris/leptris#685: xsl:where-populated is a silent no-op
        # — it drops ALL content (empty and non-empty alike). Pinned
        # until the engine implements it.
        for body in (
            '<xsl:where-populated><xsl:value-of select="\'x\'"/></xsl:where-populated>',
            "<xsl:where-populated>lit</xsl:where-populated>",
            "<xsl:where-populated><e/></xsl:where-populated>",
        ):
            assert self._run(body + "|ok") == "<o>|ok</o>"

    def test_iterate_break(self):
        assert self._run(
            "<xsl:iterate select='//item'>"
            "<xsl:if test=\"position() = 2\"><xsl:break/></xsl:if><i/>"
            "</xsl:iterate>"
        ) == "<o><i/></o>"

    def test_number_letter_format(self):
        assert self._run(
            "<xsl:number value='5' format='A.1'/>"
        ) == "<o>E</o>"

    def test_value_of_separator_currently_ignored(self):
        # leptris/leptris#685: @separator on xsl:value-of is silently
        # ignored — the default space separator is used. Pinned until
        # the engine honors it.
        assert self._run(
            "<xsl:value-of select=\"(3,1,2)\" separator='|'/>"
        ) == "<o>3 1 2</o>"
