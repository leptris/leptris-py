"""The 1.9.312 surface: WILDCARD catch-all child rows (#1552),
ns_prefix serialization (#1551), and Plan.serialize."""

import pytest

from leptris import Document, Plan
from leptris.error import LeptrisError

DOC = (
    "<mix><a>one</a><b x='1'/><a>two</a><c/><d>three</d></mix>"
)


class TestWildcard:
    def _plan(self, ns=None):
        row = {"name": "rest", "kind": "wildcard"}
        if ns is not None:
            row["ns"] = ns
        return Plan({
            "element_name": "mix",
            "children": [
                {"name": "a", "kind": "collection"},
                row,
            ],
        })

    def test_named_rows_win(self):
        with Document.parse(DOC) as doc:
            data = self._plan()(doc)
        assert data["children"]["a"] == ["one", "two"]
        # remainder members are RAW serialized subtrees, doc order
        assert data["children"]["rest"] == [
            '<b x="1"/>', "<c/>", "<d>three</d>"
        ]

    def test_empty_remainder_is_a_list(self):
        with Document.parse("<mix><a>only</a></mix>") as doc:
            data = self._plan()(doc)
        assert data["children"]["rest"] == []

    def test_wildcard_with_plan_walks_members(self):
        plan = Plan({
            "element_name": "mix",
            "children": [
                {"name": "a", "kind": "collection"},
                {"name": "rest", "kind": "wildcard",
                 "plan": {"element_name": "*",
                          "children": [{"name": "*", "kind": "scalar"}]}},
            ],
        })
        with Document.parse(DOC) as doc:
            data = plan(doc)
        # members walked through the plan; b carries its attribute
        rest = data["children"]["rest"]
        assert isinstance(rest, list) and len(rest) == 3

    def test_explicit_none_binds_no_namespace_only(self):
        XML = ('<m xmlns:n="urn:n"><n:x/><plain/></m>')
        plan = Plan({
            "element_name": "m",
            "children": [
                {"name": "rest", "kind": "wildcard",
                 "ns": {"form": "none"}},
            ],
        })
        with Document.parse(XML) as doc:
            data = plan(doc)
        assert len(data["children"]["rest"]) == 1

    def test_unset_ns_is_catch_all_any(self):
        XML = ('<m xmlns:n="urn:n"><n:x/><plain/></m>')
        plan = Plan({
            "element_name": "m",
            "children": [{"name": "rest", "kind": "wildcard"}],
        })
        with Document.parse(XML) as doc:
            data = plan(doc)
        assert len(data["children"]["rest"]) == 2


NS_DOC = ('<r xmlns:w="urn:w"><w:item w:id="7">text</w:item></r>')


class TestSerialize:
    def test_round_shape_with_prefixes(self):
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
                     "attributes": {"id": {
                         "kind": "scalar",
                         "ns": {"form": "exact", "uri": "urn:w"},
                         "ns_prefix": "w",
                     }},
                     "children": [{"kind": "content"}],
                 }},
            ],
        })
        with Document.parse(NS_DOC) as doc:
            out = plan.serialize(doc)
        assert 'xmlns:w="urn:w"' in out
        assert "w:item" in out
        assert 'w:id="7"' in out
        assert "text" in out
        # leptris/leptris#1565 fixed (1.9.316): content-row text
        # emits inline at every nesting level
        assert "<>text</>" not in out
        assert '<w:item w:id="7">text</w:item>' in out

    def test_walk_still_dict(self):
        # plain (no-ns) rows bind no-namespace elements only — the
        # documented default; use a bare document
        with Document.parse("<r><item>text</item></r>") as doc:
            plan = Plan({
                "element_name": "r",
                "children": [
                    {"name": "item", "kind": "collection"}
                ],
            })
            data = plan(doc)
        assert data["children"]["item"] == ["text"]

    def test_serialize_rejects_bad_input(self):
        plan = Plan({"element_name": "r"})
        with pytest.raises(TypeError):
            plan.serialize(42)


class TestUnqualifiedNs:
    # leptris/leptris#1560 (1.9.317+): binds the UNPREFIXED spelling
    # regardless of the effective namespace URI; element rows only

    def _plan(self, ns, root_ns=None):
        spec = {
            "element_name": "m",
            "children": [
                {"name": "x", "kind": "collection",
                 "ns": {"form": "exact", "uri": "urn:n"}},
                # row wire_name = the LOCAL name the form matches
                {"name": "y", "kind": "collection", "ns": ns},
            ],
        }
        if root_ns:
            spec["ns"] = root_ns
        return Plan(spec)

    def test_unprefixed_binds_under_default_xmlns(self):
        # the default xmlns puts m ITSELF in urn:def — the root row
        # binds it (exact); the unprefixed <y/> hits the unqualified
        # row by local name; the prefixed <n:x/> goes to the exact row
        XML = '<m xmlns="urn:def"><n:x/><y/></m>'
        root = {"form": "exact", "uri": "urn:def"}
        with Document.parse(XML) as doc:
            data = self._plan({"form": "unqualified"}, root)(doc)
        assert data["children"]["x"] == []
        # the unprefixed <y/> binds; the empty element's string
        # value is the collection member
        assert data["children"]["y"] == [""]

    def test_prefixed_spellings_never_bind(self):
        XML = '<m xmlns:n="urn:n"><n:y/></m>'
        with Document.parse(XML) as doc:
            data = self._plan({"form": "unqualified"})(doc)
        assert data["children"]["y"] == []

    def test_binds_namespace_less_documents_too(self):
        with Document.parse('<m><y>hi</y></m>') as doc:
            data = self._plan({"form": "unqualified"})(doc)
        assert data["children"]["y"] == ["hi"]

    def test_attr_rows_reject_unqualified(self):
        with pytest.raises(ValueError, match="element rows only"):
            Plan({
                "element_name": "r",
                "attributes": {"a": {
                    "kind": "scalar",
                    "ns": {"form": "unqualified"},
                }},
            })
