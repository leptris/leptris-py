"""Tier-2 plan surface (#1272 predicates, #1273 order spine,
#1269a typed values — engine 1.9.216+)."""

import pytest

from leptris import Document
from leptris.error import LeptrisError
from leptris.plan import Plan


class TestTypedValues:
    """#1269a: rows with type_tag 1/2/3 execute the type in-pass —
    results surface native int/float/bool (soft-fail to str)."""

    SPEC = {
        "element_name": "r",
        "children": [
            {"name": "n", "kind": "scalar", "type_tag": 1},
            {"name": "f", "kind": "scalar", "type_tag": 2},
            {"name": "b", "kind": "scalar", "type_tag": 3},
            {"name": "s", "kind": "scalar"},
        ],
    }

    def test_native_types(self):
        plan = Plan(self.SPEC)
        out = plan.materialize(
            "<r><n>42</n><f>2.5</f><b>true</b><s>keep</s></r>"
        )
        c = out["children"]
        assert c["n"] == 42 and type(c["n"]) is int
        assert c["f"] == 2.5 and type(c["f"]) is float
        assert c["b"] is True
        assert c["s"] == "keep"

    def test_typed_collection(self):
        plan = Plan({
            "element_name": "r",
            "children": [{"name": "t", "kind": "collection",
                          "type_tag": 1}],
        })
        out = plan.materialize("<r><t>1</t><t>2</t></r>")
        assert out["children"]["t"] == [1, 2]

    def test_soft_fail_keeps_string(self):
        plan = Plan({
            "element_name": "r",
            "children": [{"name": "n", "kind": "scalar",
                          "type_tag": 1}],
        })
        out = plan.materialize("<r><n>not-a-number</n></r>")
        assert out["children"]["n"] == "not-a-number"


class TestPredicates:
    """#1272: same-wire rows with disjoint predicates partition
    the match space (scalar rows verified against the engine's own
    Plan1272 spec)."""

    def test_partition_same_wire_siblings(self):
        plan = Plan({
            "element_name": "root",
            "children": [
                {"name": "comp", "kind": "scalar", "type_tag": 1,
                 "predicates": {"type": "guidance"}},
                {"name": "comp", "kind": "scalar", "type_tag": 2,
                 "predicates": {"type": "purpose"}},
            ],
        })
        out = plan.materialize(
            "<root><comp type='guidance'>G1</comp>"
            "<comp type='purpose'>P1</comp></root>"
        )
        c = out["children"]
        assert c["comp"] == ["G1", "P1"]

    def test_attr_predicates_accepted(self):
        # attribute-row predicates are part of the #1272 surface;
        # the engine applies them on attribute rows
        plan = Plan({
            "element_name": "r",
            "attributes": {"status": {"type_tag": 1,
                                      "predicates": {"live": "yes"}}},
        })
        out = plan.materialize("<r status='draft'/>")
        assert isinstance(out, dict)


class TestOrderSpine:
    def test_order_spine_flag_accepted(self):
        plan = Plan({
            "element_name": "r",
            "flags": {"order_spine": True},
            "children": [{"name": "a", "kind": "scalar"}],
        })
        out = plan.materialize("<r>pre<a>x</a>post</r>")
        assert isinstance(out, dict)

    def test_unknown_flag_rejected(self):
        with pytest.raises(ValueError, match="unknown flag"):
            Plan({"element_name": "r", "flags": {"bogus": True},
                  "children": []})
