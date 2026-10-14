"""libleptris 1.9.353 surface: the element attributes snapshot
(#1689) — one crossing for names, values, and ns lanes."""

from leptris import Document


class TestAttributePairsNs:
    XML = ('<r xmlns="urn:def" xmlns:w="urn:w" w:id="7" lang="x" '
           'xml:lang="en" w:sub="1"><c w:x="y"/></r>')

    def test_plain_pairs_unchanged(self):
        with Document.parse(self.XML) as doc:
            r = doc.getroot()
            assert r.attribute_pairs() == [
                ("w:id", "7"), ("lang", "x"),
                ("xml:lang", "en"), ("w:sub", "1"),
            ]

    def test_ns_pairs_resolve_in_scope(self):
        with Document.parse(self.XML) as doc:
            r = doc.getroot()
            assert r.attribute_pairs(ns=True) == [
                ("w:id", "7", "w", "urn:w"),
                ("lang", "x", None, None),
                ("xml:lang", "en", "xml",
                 "http://www.w3.org/XML/1998/namespace"),
                ("w:sub", "1", "w", "urn:w"),
            ]

    def test_ns_pairs_on_child(self):
        with Document.parse(self.XML) as doc:
            c = doc.getroot()[0]
            assert c.attribute_pairs(ns=True) == [
                ("w:x", "y", "w", "urn:w"),
            ]

    def test_no_namespace_attributes(self):
        with Document.parse('<r a="1" b="2"/>') as doc:
            r = doc.getroot()
            assert r.attribute_pairs(ns=True) == [
                ("a", "1", None, None),
                ("b", "2", None, None),
            ]

    def test_empty_attributes(self):
        with Document.parse("<r/>") as doc:
            assert doc.getroot().attribute_pairs(ns=True) == []
            assert doc.getroot().attribute_pairs() == []

    def test_order_matches_document_order(self):
        with Document.parse(
            '<r z="1" m="2" a="3"/>'
        ) as doc:
            r = doc.getroot()
            assert [p[0] for p in r.attribute_pairs(ns=True)] == [
                "z", "m", "a"
            ]
