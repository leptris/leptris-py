"""Binding hot-path faces from engine 1.9.216: the bulk attribute
face (#1254) and the fused plan materialize (#1269b)."""

import pytest

from leptris import Document, LeptrisError
from leptris.plan import Plan

DOC = (
    '<r a="1" b="2" c="3">'
    '<book id="7"><title>T</title></book>'
    "</r>"
)


class TestAttributePairs:
    def test_all_pairs_one_call(self):
        root = Document.parse(DOC).root
        assert root.attribute_pairs() == [("a", "1"), ("b", "2"), ("c", "3")]

    def test_empty_element(self):
        root = Document.parse("<r/>").root
        assert root.attribute_pairs() == []

    def test_matches_attrib(self):
        root = Document.parse(DOC).root
        assert dict(root.attribute_pairs()) == dict(root.attrib)

    def test_child(self):
        doc = Document.parse(DOC)
        assert doc.root[0].attribute_pairs() == [("id", "7")]

    def test_closed_document_raises(self):
        doc = Document.parse(DOC)
        root = doc.root
        doc.close()
        with pytest.raises(LeptrisError, match="closed"):
            root.attribute_pairs()


class TestPlanMaterialize:
    SPEC = {
        "element_name": "r",
        "children": [
            {
                "name": "book",
                "kind": "nested",
                "plan": {
                    "element_name": "book",
                    "children": [{"name": "title", "kind": "scalar"}],
                },
            }
        ],
    }

    def test_parity_with_walk(self):
        plan = Plan(self.SPEC)
        doc = Document.parse(DOC)
        walked = plan(doc)
        got = plan.materialize(DOC)
        assert got == walked
        assert got["children"]["book"]["children"]["title"] == "T"

    def test_bytes_input(self):
        plan = Plan(self.SPEC)
        assert plan.materialize(DOC.encode()) == plan.materialize(DOC)

    def test_parse_failure_raises(self):
        plan = Plan(self.SPEC)
        with pytest.raises(LeptrisError, match="materialize"):
            plan.materialize("<r><unclosed>")
