"""Plan: tree-shaped schema-descriptor materialization
(leptris/leptris#1039, libleptris 1.9.162+). Mirrors the engine's
conformance specs (test/abi/test_descriptor.cpp)."""

import pytest

from leptris import Document, Plan, PlanCallback

DOC_XML = (
    "<doc lang='en'><title>Hello</title>"
    "<item>a</item><item>b</item>"
    "<meta><k>v</k></meta>"
    "<skip/></doc>"
)

CATALOG_SPEC = {
    "element_name": "doc",
    "attributes": {"lang": {"type_tag": 7}},
    "children": [
        {"name": "title", "kind": "scalar", "type_tag": 1},
        {"name": "item", "kind": "collection", "type_tag": 2},
        {
            "name": "meta",
            "kind": "nested",
            "type_tag": 3,
            "plan": {
                "element_name": "meta",
                "children": [{"name": "k", "kind": "scalar"}],
            },
        },
        {"name": "absent", "kind": "scalar", "type_tag": 4},
    ],
}


class TestPlanWalk:
    def test_nested_scalars_attributes_collections(self):
        plan = Plan(CATALOG_SPEC)
        with Document.parse(DOC_XML) as doc:
            data = plan(doc)
        assert data["attributes"] == {"lang": "en"}
        # shape-stable: absent scalar row is None, collection is a list
        assert data["children"]["title"] == "Hello"
        assert data["children"]["item"] == ["a", "b"]
        assert data["children"]["absent"] is None
        meta = data["children"]["meta"]
        assert meta["attributes"] == {}
        assert meta["children"]["k"] == "v"
        assert "skip" not in data["children"]

    def test_walk_from_element_context(self):
        plan = Plan({
            "element_name": "meta",
            "children": [{"name": "k", "kind": "scalar"}],
        })
        with Document.parse(DOC_XML) as doc:
            meta = doc.getroot().xpath("//meta")[0]
            assert plan(meta)["children"]["k"] == "v"


class TestRawCallbackContent:
    XML = (
        "<p>intro <b>bold</b> mid"
        "<![CDATA[ cdata run ]]>tail"
        "<ref><inner x='1'/></ref>"
        "<stamp>xyz</stamp></p>"
    )

    def test_raw_serializes_subtree(self):
        plan = Plan({
            "element_name": "p",
            "children": [{"name": "ref", "kind": "raw", "type_tag": 5}],
        })
        with Document.parse(self.XML) as doc:
            data = plan(doc)
        assert '<inner x="1"/>' in data["children"]["ref"]

    def test_callback_carries_position_and_tag(self):
        plan = Plan({
            "element_name": "p",
            "children": [
                {"name": "stamp", "kind": "callback", "type_tag": 6}
            ],
        })
        with Document.parse(self.XML) as doc:
            data = plan(doc)
        stamp = data["children"]["stamp"]
        assert isinstance(stamp, PlanCallback)
        assert stamp.value == "xyz"
        assert stamp.type_tag == 6
        assert stamp.position > 0

    def test_content_rows_keep_document_order(self):
        plan = Plan({
            "element_name": "p",
            "flags": {"mixed_content": True, "cdata": True},
            "children": [
                {"name": "b", "kind": "scalar"},
                {"kind": "content"},
                {"name": "ref", "kind": "raw"},
            ],
        })
        with Document.parse(self.XML) as doc:
            data = plan(doc)
        assert data["children"]["b"] == "bold"
        assert data["children"][""] == [
            "intro ", " mid", " cdata run ", "tail",
        ]


class TestValidation:
    def test_unknown_kind(self):
        with pytest.raises(ValueError, match="kind"):
            Plan({
                "element_name": "r",
                "children": [{"name": "x", "kind": "explode"}],
            })

    def test_nested_row_needs_plan(self):
        with pytest.raises(ValueError, match="nested"):
            Plan({
                "element_name": "r",
                "children": [{"name": "x", "kind": "nested"}],
            })

    def test_exact_ns_needs_uri(self):
        with pytest.raises(ValueError, match="uri"):
            Plan({"element_name": "r", "ns": {"form": "exact"}})

    def test_duplicate_row_names_rejected(self):
        with pytest.raises(ValueError, match="duplicate"):
            Plan({
                "element_name": "r",
                "children": [
                    {"name": "x", "kind": "scalar"},
                    {"name": "x", "kind": "raw"},
                ],
            })


class TestLifecycle:
    def test_close_and_context_manager(self):
        plan = Plan(CATALOG_SPEC)
        with Document.parse(DOC_XML) as doc:
            assert plan(doc)["children"]["title"] == "Hello"
        plan.close()
        plan.close()  # idempotent

    def test_result_outlives_document_strings_copied(self):
        plan = Plan({
            "element_name": "doc",
            "children": [{"name": "title", "kind": "scalar"}],
        })
        doc = Document.parse(DOC_XML)
        # convert eagerly inside __call__; nothing lazily references
        # the document afterwards
        data = plan(doc)
        doc.close()
        assert data["children"]["title"] == "Hello"

    def test_walk_on_closed_document_raises(self):
        plan = Plan(CATALOG_SPEC)
        doc = Document.parse(DOC_XML)
        doc.close()
        with pytest.raises(Exception):
            plan(doc)
