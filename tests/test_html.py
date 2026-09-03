"""Tolerant HTML parsing (libleptris 1.9.75+, leptris/leptris#659)."""

import pytest

from leptris import html
from leptris.api import tostring
from leptris.error import ParseError


class TestHtmlParsing:
    def test_implied_end_tags_and_body(self):
        # Structure matches lxml's etree.HTMLParser: the wrapper is
        # synthesized, open tags closed.
        r = html.fromstring("<p>hello <b>world")
        assert tostring(r, encoding="unicode") == (
            "<html><head/><body><p>hello <b>world</b></p></body></html>"
        )

    def test_case_folding_and_unquoted_attrs(self):
        r = html.fromstring("<DIV CLASS=x>text</DIV>")
        assert r.tag == "html"
        div = r.find(".//div")
        assert div.get("class") == "x"

    def test_minimized_attribute_value(self):
        # leptris/leptris#813: a minimized attribute takes its own
        # name as the value (libxml2 gives the empty string).
        # Pinned until fixed.
        r = html.fromstring("<DIV CLASS=x a>text</DIV>")
        assert r.find(".//div").get("a") == "a"

    def test_void_elements_and_li(self):
        r = html.fromstring("<ul><li>a<li>b</ul><img src=x>")
        assert [e.tag for e in r.iter()] == [
            "html", "head", "body", "ul", "li", "li", "img",
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

    def test_empty_raises(self):
        with pytest.raises(ParseError):
            html.fromstring("")

    def test_document_context_manager_closes(self):
        with html.document("<p>x") as d:
            root = d.getroot()
        with pytest.raises(Exception):
            root.tag
