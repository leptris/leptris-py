"""The 1.9.289 surface: XSLT apply-time top-level params (#1478
follow-up) and attribute-level namespace forms in plans (#1486)."""

import pytest

from leptris import Document, Plan, XSLT, tostring
from leptris.error import XSLTError

PARAM_STYLESHEET = """\
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:param name="n" select="1"/>
  <xsl:template match="/"><out><xsl:value-of select="$n"/></out></xsl:template>
</xsl:stylesheet>
"""


class TestXsltParams:
    def test_default_unchanged(self):
        with Document.parse("<r/>") as doc:
            assert b"<out>1</out>" in tostring(XSLT(PARAM_STYLESHEET)(doc))

    def test_expression_param(self):
        with Document.parse("<r><v>7</v></r>") as doc:
            # values are XPath expressions over the source document
            out = XSLT(PARAM_STYLESHEET)(doc, params={"n": "//v + 1"})
            assert b"<out>8</out>" in tostring(out)

    def test_string_literal_prequoted(self):
        with Document.parse("<r/>") as doc:
            out = XSLT(PARAM_STYLESHEET)(doc, params={"n": "'text'"})
            assert b"<out>text</out>" in tostring(out)

    def test_string_params_serialize(self):
        # values stay XPath expressions; "string" is the OUTPUT face
        # (apply_string_params = apply_params + apply_string)
        with Document.parse("<r/>") as doc:
            out = XSLT(PARAM_STYLESHEET)(
                doc, string_params={"n": "'hello'"}
            )
            assert isinstance(out, str)
            assert "<out>hello</out>" in out

    def test_params_and_string_params_exclusive(self):
        with Document.parse("<r/>") as doc:
            with pytest.raises(TypeError):
                XSLT(PARAM_STYLESHEET)(
                    doc, params={"a": "1"}, string_params={"b": "2"}
                )

    def test_bad_expression_raises(self):
        with Document.parse("<r/>") as doc:
            with pytest.raises(XSLTError):
                XSLT(PARAM_STYLESHEET)(doc, params={"n": "///nope"})

    def test_unspecified_param_keeps_default(self):
        with Document.parse("<r/>") as doc:
            out = XSLT(PARAM_STYLESHEET)(doc, params={"other": "9"})
            assert b"<out>1</out>" in tostring(out)


ATTR_NS_XML = (
    '<r xmlns:a="urn:a" xmlns:b="urn:b">'
    '<i a:id="A" id="bare" b:id="B"/>'
    "</r>"
)


class TestPlanAttrNs:
    def _value(self, ns):
        plan = Plan({
            "element_name": "i",
            "attributes": {"id": {"kind": "scalar", "ns": ns}},
        })
        with Document.parse(ATTR_NS_XML) as doc:
            data = plan(doc.getroot()[0])
            return data["attributes"]["id"]

    def test_none_is_wire_name(self):
        assert self._value({"form": "none"}) == "bare"

    def test_exact_binds_only_that_uri(self):
        assert self._value({"form": "exact", "uri": "urn:a"}) == "A"
        assert self._value({"form": "exact", "uri": "urn:b"}) == "B"

    def test_exact_misses_bare(self):
        assert self._value({"form": "exact", "uri": "urn:other"}) is None

    def test_exact_needs_uri(self):
        with pytest.raises(ValueError):
            Plan({
                "element_name": "i",
                "attributes": {"id": {
                    "kind": "scalar", "ns": {"form": "exact"}
                }},
            })

    def test_unknown_form_rejected(self):
        with pytest.raises(ValueError):
            Plan({
                "element_name": "i",
                "attributes": {"id": {
                    "kind": "scalar", "ns": {"form": "prefix"}
                }},
            })

    def test_any_binds_first(self):
        assert self._value({"form": "any"}) in ("A", "bare", "B")

    def test_string_shorthand(self):
        assert self._value("none") == "bare"

    def test_nested_attr_ns_binds(self):
        # leptris/leptris#1490 fixed (1.9.291): attr ns forms work
        # in child plans — any non-zero ns_form dropped the child
        plan = Plan({
            "element_name": "r",
            "children": [
                {"name": "i", "kind": "nested",
                 "plan": {"element_name": "i",
                          "attributes": {"id": {
                              "kind": "scalar",
                              "ns": {"form": "exact",
                                     "uri": "urn:a"}}}}},
            ],
        })
        with Document.parse(ATTR_NS_XML) as doc:
            data = plan(doc)
        assert data["children"]["i"]["attributes"]["id"] == "A"
