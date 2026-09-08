"""Tolerant HTML parsing (libleptris 1.9.75+, leptris/leptris#659)."""

import pytest

from leptris import html
from leptris.api import tostring
from leptris.error import ParseError


class TestHtmlParsing:
    def test_implied_end_tags_and_body(self):
        # Byte-exact lxml HTMLParser parity since 1.9.76 (#813):
        # synthesized wrapper, open tags closed, no empty <head/>.
        r = html.fromstring("<p>hello <b>world")
        assert tostring(r, encoding="unicode") == (
            "<html><body><p>hello <b>world</b></p></body></html>"
        )

    def test_case_folding_and_unquoted_attrs(self):
        r = html.fromstring("<DIV CLASS=x>text</DIV>")
        assert r.tag == "html"
        div = r.find(".//div")
        assert div.get("class") == "x"

    def test_minimized_attribute_value(self):
        # leptris/leptris#813 fixed in 1.9.76: minimized attributes
        # take the empty string (libxml2/Nokogiri parity).
        r = html.fromstring("<DIV CLASS=x a>text</DIV>")
        assert r.find(".//div").get("a") == ""

    def test_void_elements_and_li(self):
        r = html.fromstring("<ul><li>a<li>b</ul><img src=x>")
        assert [e.tag for e in r.iter()] == [
            "html", "body", "ul", "li", "li", "img",
        ]

    def test_table_no_implied_tbody(self):
        r = html.fromstring("<table><tr><td>c</td></tr></table>")
        assert [e.tag for e in r.find(".//table").iter()] == [
            "table", "tr", "td",
        ]

    def test_entities_and_script_raw_text(self):
        r = html.fromstring("a &amp; b<script>if (a<b) x()</script>")
        assert "a &amp; b" in tostring(r, encoding="unicode")
        script = r.find(".//script")
        assert script.text == "if (a<b) x()"

    def test_xpath_and_xslt_on_html_result(self):
        from leptris import XSLT

        with html.document("<td>c") as d:
            assert d.xpath("count(//td)") == 1.0
            out = XSLT(
                '<xsl:stylesheet version="1.0"'
                ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
                "<xsl:template match='/'><o>"
                "<xsl:value-of select=\"count(//td)\"/>"
                "</o></xsl:template></xsl:stylesheet>"
            )(d)
            assert tostring(out, encoding="unicode") == "<o>1</o>"
            out.close()

    def test_plain_text_degrades_to_text(self):
        r = html.fromstring("just text")
        assert r.tag == "html"
        assert r.find("body").text == "just text"

    def test_empty_input_is_document(self):
        # libleptris 1.9.90 (#659): empty-shape inputs parse to
        # the wrapper document instead of raising (whitespace-only
        # keeps its text).
        assert tostring(html.fromstring(""), encoding="unicode") == "<html><body/></html>"
        assert tostring(html.fromstring("  "), encoding="unicode") == (
            "<html><body>  </body></html>"
        )

    def test_document_context_manager_closes(self):
        with html.document("<p>x") as d:
            root = d.getroot()
        with pytest.raises(Exception):
            root.tag

    def test_pi_construct_data_includes_trailing_qmark(self):
        # leptris/leptris#846/#659: <?target data?> parses as a PI
        # but the trailing ? leaks into the data (serializes as
        # ??>). iter() is elements-only here, so pin via
        # serialization. Pinned until fixed.
        r = html.fromstring("<?php echo 1 ?><p>x</p>")
        assert tostring(r, encoding="unicode") == (
            "<html><body><?php echo 1 ??><p>x</p></body></html>"
        )

    def test_head_content_lift(self):
        # libleptris 1.9.84 (#659): leading title/meta/link/base
        # lift into a synthesized head — byte-exact lxml shape, and
        # a LATE title does not lift.
        assert tostring(
            html.fromstring("<title>T</title><p>x"), encoding="unicode"
        ) == "<html><head><title>T</title></head><body><p>x</p></body></html>"
        assert tostring(
            html.fromstring("<meta charset='utf-8'><p>x"),
            encoding="unicode",
        ) == (
            '<html><head><meta charset="utf-8"/></head>'
            "<body><p>x</p></body></html>"
        )
        assert tostring(
            html.fromstring("<p>a</p><title>late</title>"),
            encoding="unicode",
        ) == "<html><body><p>a</p><title>late</title></body></html>"


class TestHtmlTwoModes:
    # libleptris 1.9.104 (#659): the WHATWG engine lifted leading
    # script/style/template runs into head; leptris_parse_html4_string
    # keeps the Nokogiri/lxml shape. The binding's default is the
    # byte-parity html4 entry (TODO.restructure/16).

    SCRIPT_DOC = "<script>var x=1</script><p>y</p>"

    def test_html4_default_keeps_script_in_body(self):
        # Known divergence from lxml (reported on #659): lxml's
        # libxml2 lifts a leading script run into head; the html4
        # (Nokogiri-fragment) shape keeps it in body. Every other
        # pinned shape remains byte-identical to lxml.
        assert tostring(
            html.fromstring(self.SCRIPT_DOC), encoding="unicode"
        ) == "<html><body><script>var x=1</script><p>y</p></body></html>"

    def test_whatwg_lifts_leading_script_to_head(self):
        assert tostring(
            html.fromstring(self.SCRIPT_DOC, mode="whatwg"),
            encoding="unicode",
        ) == (
            "<html><head><script>var x=1</script></head>"
            "<body><p>y</p></body></html>"
        )

    def test_unknown_mode_raises_value_error(self):
        with pytest.raises(ValueError):
            html.document(self.SCRIPT_DOC, mode="nope")

    def test_whatwg_foster_parenting(self):
        # libleptris 1.9.105 (#659): stray text inside a table is
        # fostered BEFORE the table (WHATWG); html4 keeps it inside.
        doc = "<table>text<td>x</td></table>"
        assert tostring(
            html.fromstring(doc, mode="whatwg"), encoding="unicode"
        ) == "<html><body>text<table><td>x</td></table></body></html>"
        assert tostring(
            html.fromstring(doc), encoding="unicode"
        ) == "<html><body><table>text<td>x</td></table></body></html>"

    def test_whatwg_adoption_agency(self):
        # libleptris 1.9.106/1.9.107 (#659): the WHATWG adoption
        # algorithm — the formatting element re-opens for the
        # post-close run (libxml2's html4 shape differs: bare
        # text), and adopted clones carry their attributes.
        assert tostring(
            html.fromstring("<b>1<i>2</b>3</i>", mode="whatwg"),
            encoding="unicode",
        ) == "<html><body><b>1<i>2</i></b><i>3</i></body></html>"
        assert tostring(
            html.fromstring('<p a="1">x<b a="2">y</p>z</b>',
                            mode="whatwg"),
            encoding="unicode",
        ) == (
            '<html><body><p a="1">x<b a="2">y</b></p>z</body></html>'
        )
