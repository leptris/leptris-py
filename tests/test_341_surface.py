"""libleptris 1.9.341 surface: formatting-bearing plan serialization
(#425), result -> native-document materialization (#426), and the
#1647 indent_html fix."""

import pytest

from leptris import Document, Plan
from leptris.error import LeptrisError

CATALOG = {
    "element_name": "catalog",
    "attributes": {"id": {}},
    "children": [
        {"name": "item", "kind": "nested", "plan": {
            "element_name": "item",
            "attributes": {"n": {}},
            "children": [
                {"name": "title", "kind": "scalar"},
                {"name": "price", "kind": "scalar"},
            ],
        }},
    ],
}

# catalog = pool plan 0 (its item row = row 0); item = pool plan 1
# (title = row 0, price = row 1)
OPS = [
    ("element", 0, None), ("attr", "id", "c1"),
    ("element", 0, 0), ("attr", "n", "1"),
    ("scalar", "hello", 1, 0), ("scalar", "9.99", 1, 1),
    ("end",),
    ("element", 0, 0), ("attr", "n", "2"),
    ("scalar", "world", 1, 0),
    ("end",),
    ("end",),
]

COMPACT = (
    '<catalog id="c1">'
    '<item n="1"><title>hello</title><price>9.99</price></item>'
    '<item n="2"><title>world</title></item>'
    "</catalog>"
)


class TestSerializeIndent:
    # leptris_plan_serialize_ext (#425, 1.9.341+)

    def test_compact_default_unchanged(self):
        plan = Plan(CATALOG)
        assert plan.serialize_ops(OPS) == COMPACT

    def test_ops_indent_two(self):
        plan = Plan(CATALOG)
        assert plan.serialize_ops(OPS, indent=2) == (
            '<catalog id="c1">\n'
            "  <item n=\"1\">\n"
            "    <title>hello</title>\n"
            "    <price>9.99</price>\n"
            "  </item>\n"
            "  <item n=\"2\">\n"
            "    <title>world</title>\n"
            "  </item>\n"
            "</catalog>\n"
        )

    def test_ops_indent_unit_tab(self):
        plan = Plan(CATALOG)
        out = plan.serialize_ops(
            [("element", 0, None), ("element", 0, 0), ("end",),
             ("end",)],
            indent=1, indent_unit="\t",
        )
        assert out == "<catalog>\n\t<item/>\n</catalog>\n"

    def test_walk_serialize_indent(self):
        plan = Plan(CATALOG)
        with Document.parse(
            '<catalog id="z"><item n="a">'
            "<title>t1</title></item></catalog>"
        ) as doc:
            assert plan.serialize(doc, indent=3) == (
                '<catalog id="z">\n'
                '   <item n="a">\n'
                "      <title>t1</title>\n"
                "   </item>\n"
                "</catalog>\n"
            )

    def test_content_stays_inline(self):
        plan = Plan({
            "element_name": "r",
            "children": [
                {"name": "e", "kind": "nested", "plan": {
                    "element_name": "e",
                    "flags": {"mixed_content": True},
                    "children": [{"kind": "content"}],
                }},
            ],
        })
        with Document.parse("<r><e>plain text</e></r>") as doc:
            out = plan.serialize(doc, indent=2)
        # content runs block-indent (verbatim run content, own line)
        assert "  <e>\n    plain text\n  </e>" in out

    def test_indent_unit_requires_indent(self):
        # indent_unit without indent > 0 = the compact form
        plan = Plan(CATALOG)
        assert plan.serialize_ops(
            OPS, indent=0, indent_unit="\t"
        ) == COMPACT


class TestDocumentOps:
    # leptris_document_from_plan_result (#426, 1.9.341+)

    def test_materializes_native_tree(self):
        plan = Plan(CATALOG)
        doc = plan.document_ops(OPS)
        root = doc.getroot()
        assert root.tag == "catalog" and root.get("id") == "c1"
        assert [c.get("n") for c in root] == ["1", "2"]
        assert root[0][0].tag == "title"
        assert root[0][0].text == "hello"
        assert root[0][1].tag == "price"
        assert root[0][1].text == "9.99"
        # the document is a first-class tree: walks work
        assert len(list(root.iterdescendants())) > 0
        doc.close()

    def test_write_round_trip(self):
        plan = Plan(CATALOG)
        with plan.document_ops(OPS) as doc:
            assert doc.xpath("/catalog/item/@n") == ["1", "2"]

    def test_root_ns_rides_as_xmlns_attribute(self):
        plan = Plan({
            "element_name": "r",
            "ns": {"form": "exact", "uri": "urn:w"},
            "ns_prefix": "w",
            "children": [
                {"name": "item", "kind": "nested",
                 "ns": {"form": "exact", "uri": "urn:w"},
                 "ns_prefix": "w",
                 "plan": {
                     "element_name": "item",
                     "ns": {"form": "exact", "uri": "urn:w"},
                     "children": [
                         {"name": "t", "kind": "scalar"},
                     ],
                 }},
            ],
        })
        with plan.document_ops([
            ("element", 0, None),
            ("element", 0, 0), ("scalar", "x", 1, 0), ("end",),
            ("end",),
        ]) as doc:
            root = doc.getroot()
            assert root.tag == "r"
            # declarations ride as xmlns ATTRIBUTES (wire spellings;
            # no ns table on minted elements)
            assert root.attrib["xmlns:w"] == "urn:w"
            assert root[0].tag == "item"
            assert root[0][0].tag == "t"
            assert root[0][0].text == "x"

    def test_attributes_carry_verbatim(self):
        # wire spellings, not the row's match name
        plan = Plan({
            "element_name": "r",
            "attributes": {"id": {}},
        })
        with plan.document_ops([
            ("element", 0, None), ("attr", "w:id", "7"), ("end",),
        ]) as doc:
            assert doc.getroot().attrib["w:id"] == "7"

    def test_scalar_default_row_index(self):
        # ("scalar", v) on the root plan's row 0 materializes that
        # row (the #408 collection-member shape)
        plan = Plan({
            "element_name": "r",
            "children": [{"name": "item", "kind": "collection"}],
        })
        with plan.document_ops([
            ("element", 0, None),
            ("scalar", "alpha"), ("scalar", "beta"),
            ("end",),
        ]) as doc:
            assert doc.xpath("/r/item/text()") == [
                "alpha", "beta"
            ]

    def test_unbalanced_program_raises(self):
        plan = Plan({"element_name": "r"})
        with pytest.raises(LeptrisError):
            plan.document_ops([
                ("element", 0, None), ("scalar", "dangling"),
            ])

    def test_bad_plan_index_raises_not_crashes(self):
        # out-of-pool indices reject at the boundary (defense in
        # depth — the engine also validates since 1.9.343, #1654)
        plan = Plan({"element_name": "r"})
        with pytest.raises(ValueError, match="plan pool"):
            plan.serialize_ops([
                ("element", 0, None), ("scalar", "x", 9, 0),
                ("end",),
            ])
        with pytest.raises(ValueError, match="plan pool"):
            plan.document_ops([
                ("element", 0, None), ("scalar", "x", 9, 0),
                ("end",),
            ])


class TestToDocument:
    # the Document twin of serialize (walk -> native tree)

    def test_plain_walk(self):
        plan = Plan({
            "element_name": "r",
            "children": [{"name": "item", "kind": "nested", "plan": {
                "element_name": "item",
                "children": [{"name": "t", "kind": "scalar"}],
            }}],
        })
        with Document.parse("<r><item><t>x</t></item></r>") as doc:
            out = plan.to_document(doc)
            root = out.getroot()
            assert root.tag == "r" and len(root) == 1
            assert root[0].tag == "item"
            assert root[0][0].tag == "t"
            assert root[0][0].text == "x"

    def test_prefixed_walk_declarations_once(self):
        plan = Plan({
            "element_name": "r",
            "ns": {"form": "exact", "uri": "urn:w"},
            "ns_prefix": "w",
            "children": [
                {"name": "item",
                 "ns": {"form": "exact", "uri": "urn:w"},
                 "ns_prefix": "w",
                 "kind": "nested",
                 "plan": {
                     "element_name": "item",
                     "ns": {"form": "exact", "uri": "urn:w"},
                     "flags": {"mixed_content": True},
                     "children": [{"kind": "content"}],
                 }},
            ],
        })
        with Document.parse(
            '<r xmlns:w="urn:w"><w:item>text</w:item></r>'
        ) as doc:
            out = plan.to_document(doc)
            root = out.getroot()
            assert root.tag == "r"
            assert root.attrib["xmlns:w"] == "urn:w"
            assert root[0].tag == "item"
            assert root[0].text == "text"

    def test_rejects_bad_input(self):
        plan = Plan({"element_name": "r"})
        with pytest.raises(TypeError):
            plan.to_document(42)
