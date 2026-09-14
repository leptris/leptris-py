"""Tree-shaped schema-descriptor materialization (libleptris 1.9.162+,
leptris/leptris#1039).

Compile a plan tree once, materialize whole documents against it in
one native pass — the shape hosts such as lutaml-model consume
directly, with no per-element Python calls:

    from leptris import Document, Plan

    catalog = Plan({
        "element_name": "catalog",
        "children": [
            {"name": "item", "kind": "collection", "plan": {
                "element_name": "item",
                "attributes": {"id": {}, "price": {}},
                "children": [{"name": "title"}],
            }},
            {"name": "note", "kind": "raw"},
        ],
    })
    with Document.parse(xml) as doc:
        data = catalog(doc)

Output is SHAPE-STABLE: every row of the plan appears in the result
— a scalar row yields a ``str`` or ``None``, a collection/content row
always a ``list``, a nested row a ``dict`` or ``None``. Nested
elements come back as ``{"attributes": {...}, "children": {...}}``
keyed by wire name. CALLBACK rows yield
``PlanCallback(value, position, type_tag)`` for host-side dispatch;
RAW rows yield the serialized subtree; content rows (mixed content,
``kind="content"``) yield the ordered text runs.
"""

from __future__ import annotations

from collections import namedtuple
from typing import Optional

from . import _ffi
from .error import LeptrisError

_PLAN_ABI_VERSION = 1

_KINDS = {
    "scalar": _ffi.lib.LEPTRIS_PLAN_KIND_SCALAR,
    "collection": _ffi.lib.LEPTRIS_PLAN_KIND_COLLECTION,
    "nested": _ffi.lib.LEPTRIS_PLAN_KIND_NESTED,
    "raw": _ffi.lib.LEPTRIS_PLAN_KIND_RAW,
    "content": _ffi.lib.LEPTRIS_PLAN_KIND_CONTENT,
    "callback": _ffi.lib.LEPTRIS_PLAN_KIND_CALLBACK,
}
_NS_FORMS = {"none": 0, "exact": 1, "any": 2}
_FLAG_BITS = {
    "mixed_content": 0x1,
    "ordered": 0x2,
    "cdata": 0x4,
    "ns_lenient": 0x8,
}

#: CALLBACK row payload: the raw string value, the document byte
#: position of the source node, and the plan row's type_tag echo.
PlanCallback = namedtuple("PlanCallback", "value position type_tag")


def _kind(name, where):
    try:
        return _KINDS[name]
    except (KeyError, TypeError):
        valid = ", ".join(sorted(_KINDS))
        raise ValueError(
            f"{where}: unknown kind {name!r}; expected one of: {valid}"
        ) from None


def _flatten(spec):
    """Validate the spec tree and flatten it into the engine's
    plan-pool shape (index 0 = root)."""
    if not isinstance(spec, dict):
        raise TypeError("a plan spec must be a dict")
    elements = []

    def emit(subtree) -> int:
        index = len(elements)
        elements.append(None)

        name = subtree.get("element_name")
        if not name or not isinstance(name, str):
            raise ValueError(
                f"plan #{index}: element_name must be a non-empty str"
            )

        ns = subtree.get("ns", {"form": "none"})
        if isinstance(ns, str):
            ns = {"form": ns}
        form = _NS_FORMS.get(ns.get("form", "none"))
        if form is None:
            valid = ", ".join(sorted(_NS_FORMS))
            raise ValueError(
                f"plan #{index} ({name}): unknown ns form "
                f"{ns.get('form')!r}; expected one of: {valid}"
            )
        if form == 1 and not ns.get("uri"):
            raise ValueError(
                f"plan #{index} ({name}): ns form 'exact' needs a uri"
            )

        flags = 0
        for flag, enabled in (subtree.get("flags") or {}).items():
            bit = _FLAG_BITS.get(flag)
            if bit is None:
                valid = ", ".join(sorted(_FLAG_BITS))
                raise ValueError(
                    f"plan #{index} ({name}): unknown flag {flag!r}; "
                    f"expected one of: {valid}"
                )
            if enabled:
                flags |= bit

        raw_attrs = subtree.get("attributes") or {}
        if not isinstance(raw_attrs, dict):
            raise TypeError(
                f"plan #{index} ({name}): attributes must be a dict"
            )
        attrs = {}
        for wire_name, row in raw_attrs.items():
            row = row or {}
            kind = _kind(
                row.get("kind", "scalar"),
                f"plan #{index} ({name}) attribute {wire_name!r}",
            )
            if kind not in (
                _ffi.lib.LEPTRIS_PLAN_KIND_SCALAR,
                _ffi.lib.LEPTRIS_PLAN_KIND_COLLECTION,
                _ffi.lib.LEPTRIS_PLAN_KIND_CALLBACK,
            ):
                raise ValueError(
                    f"plan #{index} ({name}): attribute row "
                    f"{wire_name!r} must be scalar, collection or callback"
                )
            attrs[wire_name] = (kind, row.get("type_tag", 0))

        raw_children = subtree.get("children") or []
        if not isinstance(raw_children, list):
            raise TypeError(
                f"plan #{index} ({name}): children must be a list"
            )
        rows = {}
        kids = []
        for row in raw_children:
            wire_name = row.get(
                "name", "" if row.get("kind") == "content" else None
            )
            if wire_name is None or not isinstance(wire_name, str):
                raise TypeError(
                    f"plan #{index} ({name}): every child row needs a str "
                    f"name (content rows may omit it)"
                )
            if wire_name in rows:
                raise ValueError(
                    f"plan #{index} ({name}): duplicate child row "
                    f"{wire_name!r}"
                )
            kind = _kind(
                row.get("kind"), f"plan #{index} ({name}) row {wire_name!r}"
            )
            child_index = -1
            if kind == _ffi.lib.LEPTRIS_PLAN_KIND_NESTED:
                if "plan" not in row:
                    raise ValueError(
                        f"plan #{index} ({name}) row {wire_name!r}: "
                        f"nested rows need a 'plan'"
                    )
                child_index = emit(row["plan"])
            rows[wire_name] = (kind, row.get("type_tag", 0), child_index)
            kids.append((wire_name, kind, row.get("type_tag", 0), child_index))
        elements[index] = {
            "name": name,
            "ns_form": form,
            "ns_uri": ns.get("uri"),
            "flags": flags,
            "attrs": attrs,
            "rows": rows,
            "kids": kids,
        }
        return index

    emit(spec)
    return elements


class Plan:
    """Compiled schema descriptor (compile once, walk many)."""

    def __init__(self, spec: dict):
        abi = _ffi.lib.leptris_plan_abi_version()
        if abi != _PLAN_ABI_VERSION:
            raise LeptrisError(
                f"libleptris descriptor ABI v{abi} != binding's "
                f"v{_PLAN_ABI_VERSION}; upgrade leptris"
            )
        elements = _flatten(spec)
        self._elements = elements  # conversion context (attrs + rows)

        ffi = _ffi.ffi
        keepalive = []
        element_structs = ffi.new("leptris_element_plan[]", len(elements))
        for index, (struct, element) in enumerate(
            zip(element_structs, elements)
        ):
            name_c = ffi.new("char[]", element["name"].encode("utf-8"))
            keepalive.append(name_c)
            struct.element_name = name_c
            struct.ns_form = element["ns_form"]
            struct.pad0 = 0
            if element["ns_form"] == 1 and element["ns_uri"]:
                uri_c = ffi.new("char[]", element["ns_uri"].encode("utf-8"))
                keepalive.append(uri_c)
                struct.ns_uri = uri_c
            else:
                struct.ns_uri = ffi.NULL
            attr_rows = list(element["attrs"].items())
            struct.attribute_count = len(attr_rows)
            if attr_rows:
                arr = ffi.new("leptris_attr_plan[]", len(attr_rows))
                keepalive.append(arr)
                for slot, (wire_name, (kind, type_tag)) in zip(
                    arr, attr_rows
                ):
                    wire_c = ffi.new("char[]", wire_name.encode("utf-8"))
                    keepalive.append(wire_c)
                    slot.wire_name = wire_c
                    slot.kind = kind
                    slot.type_tag = type_tag
                struct.attribute_plans = arr
            else:
                struct.attribute_plans = ffi.NULL
            kids = element["kids"]
            struct.child_count = len(kids)
            if kids:
                arr = ffi.new("leptris_child_plan[]", len(kids))
                keepalive.append(arr)
                for slot, (wire_name, kind, type_tag, child_index) in zip(
                    arr, kids
                ):
                    wire_c = ffi.new("char[]", wire_name.encode("utf-8"))
                    keepalive.append(wire_c)
                    slot.wire_name = wire_c
                    slot.kind = kind
                    slot.type_tag = type_tag
                    slot.child_plan_index = child_index
                struct.child_plans = arr
            else:
                struct.child_plans = ffi.NULL
            struct.flags = element["flags"]
            struct.pad1 = 0

        spec_struct = ffi.new("leptris_plan_spec*")
        spec_struct.abi_version = _PLAN_ABI_VERSION
        spec_struct.plan_count = len(elements)
        spec_struct.plans = element_structs
        status = ffi.new("LeptrisStatus*")
        handle = _ffi.lib.leptris_plan_build(spec_struct, status)
        if handle == ffi.NULL:
            raise LeptrisError(f"plan build failed: status {int(status[0])}")
        self._handle = handle
        self._keepalive = keepalive + [element_structs]

    def __call__(self, element_or_document) -> Optional[dict]:
        from .document import Document
        from .element import Element

        if isinstance(element_or_document, Element):
            element = element_or_document
            document = element._document
        elif isinstance(element_or_document, Document):
            document = element_or_document
            element = document.getroot()
        else:
            raise TypeError("expected an Element or Document")
        ffi = _ffi.ffi
        status = ffi.new("LeptrisStatus*")
        result = _ffi.lib.leptris_plan_walk(
            document._cd(), element._cd(), self._handle, status
        )
        if result == ffi.NULL:
            raise LeptrisError(f"plan walk failed: status {int(status[0])}")
        try:
            return _convert(result, self._elements, plan_index=0)
        finally:
            _ffi.lib.leptris_plan_result_free(result)

    def close(self) -> None:
        if getattr(self, "_handle", None) is not None:
            _ffi.lib.leptris_plan_free(self._handle)
            self._handle = None

    def __enter__(self) -> "Plan":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass  # interpreter shutdown


def _convert(result, elements, plan_index):
    """Engine value tree -> shape-stable Python values, keyed by the
    plan's own rows (the author knows the shape statically)."""
    lib = _ffi.lib
    ffi = _ffi.ffi

    def string(value):
        char = lib.leptris_plan_value_string(value)
        return (
            ffi.string(char).decode("utf-8", "replace")
            if char != ffi.NULL
            else None
        )

    def leaf(value):
        if (
            lib.leptris_plan_value_kind(value)
            == lib.LEPTRIS_PLAN_VALUE_CALLBACK
        ):
            return PlanCallback(
                string(value),
                lib.leptris_plan_value_position(value),
                lib.leptris_plan_value_type_tag(value),
            )
        return string(value)

    def list_items(value):
        return [
            leaf(lib.leptris_plan_value_at(value, i))
            for i in range(lib.leptris_plan_value_count(value))
        ]

    def value_name(value):
        char = lib.leptris_plan_value_name(value)
        return (
            ffi.string(char).decode("utf-8", "replace")
            if char != ffi.NULL
            else ""
        )

    def row_matches(wire_name, row, value, value_kind, vname):
        """Values arrive in plan-row order; match each upcoming value
        to the row that produced it (collection wrappers and content
        runs carry no name — only collection items do)."""
        row_kind = row[0]
        if row_kind in (
            lib.LEPTRIS_PLAN_KIND_SCALAR,
            lib.LEPTRIS_PLAN_KIND_CALLBACK,
            lib.LEPTRIS_PLAN_KIND_RAW,
        ):
            return value_kind not in (
                lib.LEPTRIS_PLAN_VALUE_ELEMENT,
                lib.LEPTRIS_PLAN_VALUE_COLLECTION,
            ) and vname == wire_name
        if row_kind == lib.LEPTRIS_PLAN_KIND_NESTED:
            return (
                value_kind == lib.LEPTRIS_PLAN_VALUE_ELEMENT
                and vname == wire_name
            )
        # COLLECTION / CONTENT: an unnamed collection value; a
        # collection's items carry the row name, content runs none.
        if value_kind != lib.LEPTRIS_PLAN_VALUE_COLLECTION:
            return False
        count = lib.leptris_plan_value_count(value)
        if count == 0:
            return True  # [] either way — order decides
        item = lib.leptris_plan_value_name(
            lib.leptris_plan_value_at(value, 0)
        )
        if row_kind == lib.LEPTRIS_PLAN_KIND_COLLECTION:
            return (
                item != ffi.NULL
                and ffi.string(item).decode("utf-8", "replace")
                == wire_name
            )
        return item == ffi.NULL

    def element(value, plan_index):
        plan = elements[plan_index]
        row_list = list(plan["rows"].items())
        values = [
            lib.leptris_plan_value_at(value, i)
            for i in range(lib.leptris_plan_value_count(value))
        ]
        kinds = [lib.leptris_plan_value_kind(v) for v in values]
        names = [value_name(v) for v in values]
        children = {}
        vi = 0
        for wire_name, row in row_list:
            children[wire_name] = [] if row[0] in (
                lib.LEPTRIS_PLAN_KIND_COLLECTION,
                lib.LEPTRIS_PLAN_KIND_CONTENT,
            ) else None
            if vi < len(values) and row_matches(
                wire_name, row, values[vi], kinds[vi], names[vi]
            ):
                # A NESTED row can match repeatedly (implicit
                # collection of structured children): consume every
                # consecutive value this row produced — one match is
                # the dict, several a list.
                nested_matches = []
                while vi < len(values) and row_matches(
                    wire_name, row, values[vi], kinds[vi], names[vi]
                ):
                    nested_matches.append((values[vi], kinds[vi]))
                    vi += 1
                child, kind = nested_matches[0]
                if kind == lib.LEPTRIS_PLAN_VALUE_ELEMENT:
                    converted = [
                        element(v, row[2]) for v, k in nested_matches
                    ]
                    children[wire_name] = (
                        converted[0] if len(converted) == 1 else converted
                    )
                elif kind == lib.LEPTRIS_PLAN_VALUE_COLLECTION:
                    children[wire_name] = list_items(child)
                else:
                    children[wire_name] = leaf(child)
        attrs = {}
        for wire_name in plan["attrs"]:
            char = lib.leptris_plan_value_attribute(
                value, wire_name.encode("utf-8")
            )
            attrs[wire_name] = (
                ffi.string(char).decode("utf-8", "replace")
                if char != ffi.NULL
                else None
            )
        return {"attributes": attrs, "children": children}

    return element(result, plan_index)
