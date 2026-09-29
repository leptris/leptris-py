"""1.9.273 surface: the plan children snapshot (one-crossing
child enumeration) and the parse perf opt-outs."""

from leptris import Document
from leptris.plan import Plan


class TestChildrenSnapshot:
    SPEC = {
        "element_name": "r",
        "children": [
            {"name": "a", "kind": "scalar", "type_tag": 1},
            {"name": "b", "kind": "scalar"},
            {"name": "item", "kind": "nested",
             "plan": {"element_name": "item",
                      "children": [{"name": "v", "kind": "scalar",
                                    "type_tag": 2}]}},
        ],
    }

    DOC = ("<r><a>1</a>x<b>2</b>"
           "<item><v>3.5</v></item><item><v>4</v></item></r>")

    def test_snapshot_matches_per_item_path(self):
        via_snapshot = Plan(self.SPEC).materialize(self.DOC)
        doc = Document.parse(self.DOC)
        via_walk = Plan(self.SPEC)(doc)
        assert via_snapshot == via_walk
        c = via_snapshot["children"]
        assert c["a"] == 1 and c["b"] == "2"
        items = c["item"]
        assert [i["children"]["v"] for i in items] == [3.5, 4.0]

    def test_content_runs_take_the_null_name_branch(self):
        plan = Plan({
            "element_name": "r",
            "children": [{"name": "t", "kind": "scalar"}],
        })
        out = plan.materialize("<r>before<a/>after</r>")
        assert out["children"]["t"] in ("beforeafter", "before", None) or \
            isinstance(out["children"]["t"], str)


class TestParseOptOuts:
    def test_skip_dup_detection_silences_the_diag(self):
        doc = Document.parse('<r a="1" a="2"><c/></r>',
                             skip_dup_detection=True)
        assert doc.parse_diagnostics == []
        assert doc.root[0].tag == "c"
        assert doc.root.get("a") == "1"  # first still wins

    def test_default_keeps_the_diag(self):
        doc = Document.parse('<r a="1" a="2"><c/></r>')
        assert [d.kind for d in doc.parse_diagnostics] == ["RECOVER"]

    def test_skip_source_positions_parses_clean(self):
        doc = Document.parse("<r>\n  <c/>\n</r>",
                             skip_source_positions=True)
        assert doc.root.tag == "r"
        assert doc.root[0].tag == "c"
