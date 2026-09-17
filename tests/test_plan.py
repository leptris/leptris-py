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

    def test_same_name_rows_group_into_a_list(self):
        # Same-name rows (the #1115 shape) materialize as one list of
        # per-row values in declaration order — the namespace split.
        plan = Plan({
            "element_name": "r",
            "children": [
                {"name": "x", "kind": "scalar",
                 "ns": {"form": "exact", "uri": "urn:p"}},
                {"name": "x", "kind": "scalar"},
            ],
        })
        xml = (
            "<r xmlns:p='urn:p'><p:x>P</p:x><x>N</x>"
            "<p:x>Q</p:x></r>"
        )
        with Document.parse(xml) as doc:
            # row 1 (exact urn:p) takes its FIRST match — scalar rows
            # are first-wins like single rows (a scalar row matching
            # twice is a collection-shaped modeling error); row 2
            # binds the no-namespace N
            assert plan(doc)["children"]["x"] == ["P", "N"]

    def test_same_name_rows_absent_member_keeps_row_shape(self):
        plan = Plan({
            "element_name": "r",
            "children": [
                {"name": "x", "kind": "scalar",
                 "ns": {"form": "exact", "uri": "urn:none"}},
                {"name": "x", "kind": "scalar"},
            ],
        })
        with Document.parse("<r><x>N</x></r>") as doc:
            assert plan(doc)["children"]["x"] == [None, "N"]

    def test_same_name_collection_and_scalar_rows(self):
        plan = Plan({
            "element_name": "r",
            "children": [
                {"name": "x", "kind": "collection",
                 "ns": {"form": "exact", "uri": "urn:p"}},
                {"name": "x", "kind": "collection"},
            ],
        })
        xml = (
            "<r xmlns:p='urn:p'><p:x>P</p:x><x>N</x>"
            "<p:x>Q</p:x></r>"
        )
        with Document.parse(xml) as doc:
            assert plan(doc)["children"]["x"] == [
                ["P", "Q"],
                ["N"],
            ]


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


class TestRepeatedNested:
    def test_repeated_nested_row_is_a_list_single_is_a_dict(self):
        plan = Plan({
            "element_name": "r",
            "children": [
                {
                    "name": "i",
                    "kind": "nested",
                    "plan": {
                        "element_name": "i",
                        "attributes": {"n": {}},
                    },
                },
            ],
        })
        with Document.parse("<r><i n='1'/><i n='2'/></r>") as doc:
            data = plan(doc)
        items = data["children"]["i"]
        assert isinstance(items, list)
        assert [e["attributes"]["n"] for e in items] == ["1", "2"]
        with Document.parse("<r><i n='1'/></r>") as doc:
            single = plan(doc)["children"]["i"]
        assert isinstance(single, dict)
        assert single["attributes"]["n"] == "1"
        with Document.parse("<r/>") as doc:
            assert plan(doc)["children"]["i"] is None


class TestDifferential:
    """The C converter (accelerator) and the Python converter must
    produce identical structures for the same walk result."""

    CASES = [
        # (spec, xml)
        (CATALOG_SPEC, DOC_XML),
        (
            {
                "element_name": "p",
                "flags": {"mixed_content": True, "cdata": True},
                "children": [
                    {"name": "b", "kind": "scalar"},
                    {"kind": "content"},
                    {"name": "ref", "kind": "raw"},
                    {"name": "stamp", "kind": "callback", "type_tag": 6},
                ],
            },
            "<p>intro <b>bold</b> mid<![CDATA[ cdata ]]>tail"
            "<ref><inner x='1'/></ref><stamp>xyz</stamp></p>",
        ),
        (
            {
                "element_name": "r",
                "children": [
                    {"name": "e", "kind": "nested", "plan": {
                        "element_name": "e",
                        "attributes": {"n": {}},
                    }},
                ],
            },
            "<r><e n='1'/><e n='2'/><e n='3'/></r>",
        ),
        (
            {
                "element_name": "r",
                "children": [
                    {"name": "one", "kind": "nested", "plan": {
                        "element_name": "one"}},
                    {"name": "many", "kind": "collection"},
                    {"name": "missing", "kind": "scalar"},
                ],
            },
            "<r><one/><many>a</many><many/><many>b</many></r>",
        ),
        (
            {
                "element_name": "r",
                "children": [
                    {"name": "x", "kind": "collection",
                     "ns": {"form": "exact", "uri": "urn:p"}},
                    {"name": "x", "kind": "scalar"},
                    {"name": "x", "kind": "nested", "ns": "any",
                     "plan": {"element_name": "x",
                              "attributes": {"n": {}}}},
                ],
            },
            "<r xmlns:p='urn:p'><p:x>P</p:x><x>N</x>"
            "<p:x>Q</p:x><x n='1'/></r>",
        ),
        (
            {
                "element_name": "outer",
                "ns": {"form": "exact", "uri": "urn:x"},
                "children": [
                    {"name": "deep", "kind": "nested", "plan": {
                        "element_name": "deep",
                        "ns": {"form": "any"},
                        "children": [
                            {"name": "leaf", "kind": "scalar"},
                        ],
                    }},
                ],
            },
            "<o:outer xmlns:o='urn:x'><o:deep xmlns:p='urn:y'>"
            "<p:leaf>v</p:leaf><leaf>w</leaf></o:deep></o:outer>",
        ),
    ]

    def _walk(self, plan, doc):
        from leptris import _ffi

        ffi = _ffi.ffi
        status = ffi.new("LeptrisStatus*")
        result = _ffi.lib.leptris_plan_walk(
            doc._cd(), doc.getroot()._cd(), plan._handle, status
        )
        assert result != ffi.NULL
        return result

    @pytest.mark.parametrize("spec,xml", CASES)
    def test_converters_agree(self, spec, xml):
        from leptris import Document
        from leptris import _ffi
        from leptris.element import _accel
        from leptris.plan import _convert

        if _accel is None:
            pytest.skip("accelerator unavailable")
        plan = Plan(spec)
        with Document.parse(xml) as doc:
            result = self._walk(plan, doc)
            try:
                c_result = _accel.plan_convert(
                    int(_ffi.ffi.cast("uintptr_t", result)), plan._shape
                )
                py_result = _convert(result, plan._elements, 0)
            finally:
                _ffi.lib.leptris_plan_result_free(result)
        assert c_result == py_result

class TestPlanRowNamespace:
    """Row-level ns forms (#1115, libleptris 1.9.178+): the row's
    'ns' selects which same-local-name children it binds."""

    XML = (
        "<r xmlns:p='urn:p'><p:item>P</p:item>"
        "<item>N</item><p:item>Q</p:item></r>"
    )

    def _run(self, row):
        plan = Plan({"element_name": "r", "children": [row]})
        with Document.parse(self.XML) as doc:
            return plan(doc)["children"]["item"]

    def test_exact_uri_binds_only_namespaced(self):
        assert (
            self._run(
                {
                    "name": "item",
                    "kind": "scalar",
                    "ns": {"form": "exact", "uri": "urn:p"},
                }
            )
            == "P"
        )

    def test_any_binds_first_match_as_scalar(self):
        assert (
            self._run({"name": "item", "kind": "scalar", "ns": "any"})
            == "P"
        )

    def test_collection_any_merges_namespaces_in_document_order(self):
        assert self._run(
            {"name": "item", "kind": "collection", "ns": "any"}
        ) == ["P", "N", "Q"]

    def test_unset_binds_only_no_namespace(self):
        assert self._run({"name": "item", "kind": "scalar"}) == "N"

    def test_exact_requires_uri(self):
        with pytest.raises(ValueError, match="needs a uri"):
            Plan(
                {
                    "element_name": "r",
                    "children": [
                        {
                            "name": "item",
                            "kind": "scalar",
                            "ns": {"form": "exact"},
                        }
                    ],
                }
            )

    def test_unknown_form_rejected(self):
        with pytest.raises(ValueError, match="unknown ns form"):
            Plan(
                {
                    "element_name": "r",
                    "children": [
                        {
                            "name": "item",
                            "kind": "scalar",
                            "ns": {"form": "wildcard"},
                        }
                    ],
                }
            )

    def test_same_name_rows_are_supported(self):
        plan = Plan(
            {
                "element_name": "r",
                "children": [
                    {
                        "name": "item",
                        "kind": "scalar",
                        "ns": {"form": "exact", "uri": "urn:p"},
                    },
                    {"name": "item", "kind": "scalar"},
                ],
            }
        )
        xml = "<r xmlns:p='urn:p'><p:item>P</p:item><item>N</item></r>"
        with Document.parse(xml) as doc:
            assert plan(doc)["children"]["item"] == ["P", "N"]
