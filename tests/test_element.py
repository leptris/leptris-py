"""Element: lxml-compatible navigation, attributes, text model."""

import pytest

from leptris import Document, LeptrisError, fromstring

MIXED = "<p>Hello <b>world</b>!</p><!-- after -->"


@pytest.fixture()
def catalog():
    return fromstring(
        "<library><book id='1' lang='en'>Ulysses</book>"
        "<book id='2' lang='fr'>L'Etranger</book></library>"
    )


class TestTag:
    def test_plain(self, catalog):
        assert catalog.tag == "library"

    def test_clark_notation(self):
        root = fromstring("<x:root xmlns:x='urn:ex'><x:kid/></x:root>")
        assert root.tag == "{urn:ex}root"
        assert root[0].tag == "{urn:ex}kid"

    def test_default_namespace(self):
        root = fromstring("<r xmlns='urn:d'><k/></r>")
        assert root.tag == "{urn:d}r"
        assert root[0].tag == "{urn:d}k"
        assert root.prefix is None

    def test_prefix_and_namespace(self):
        root = fromstring("<x:root xmlns:x='urn:ex'/>")
        assert root.prefix == "x"
        assert root.namespace == "urn:ex"

    def test_no_namespace(self, catalog):
        assert catalog.namespace is None
        assert catalog.prefix is None


class TestAttributes:
    def test_get(self, catalog):
        book = catalog[0]
        assert book.get("id") == "1"
        assert book.get("missing") is None
        assert book.get("missing", "x") == "x"

    def test_attrib_is_dict_view(self, catalog):
        assert catalog[0].attrib == {"id": "1", "lang": "en"}
        assert dict(catalog[0].attrib) == {"id": "1", "lang": "en"}

    def test_attrib_protocol(self, catalog):
        attrib = catalog[0].attrib
        assert "id" in attrib
        assert "zzz" not in attrib
        assert attrib["id"] == "1"
        assert len(attrib) == 2
        assert sorted(attrib) == ["id", "lang"]
        assert sorted(attrib.keys()) == ["id", "lang"]
        assert sorted(attrib.values()) == ["1", "en"]
        with pytest.raises(KeyError):
            attrib["zzz"]

    def test_attrib_is_read_only(self, catalog):
        with pytest.raises(TypeError):
            catalog[0].attrib["id"] = "9"

    def test_keys_items_document_order(self, catalog):
        assert catalog[0].keys() == ["id", "lang"]
        assert catalog[0].items() == [("id", "1"), ("lang", "en")]

    def test_entity_expansion(self):
        root = fromstring("<e t='a &amp; b'/>")
        assert root.get("t") == "a & b"
        assert root.attrib == {"t": "a & b"}

    def test_no_attributes(self):
        root = fromstring("<e/>")
        assert root.attrib == {}
        assert len(root.attrib) == 0


class TestChildren:
    def test_indexing(self, catalog):
        assert catalog[0].get("id") == "1"
        assert catalog[1].get("id") == "2"

    def test_negative_index(self, catalog):
        assert catalog[-1].get("id") == "2"
        assert catalog[-2].get("id") == "1"

    def test_out_of_range(self, catalog):
        with pytest.raises(IndexError):
            catalog[5]
        with pytest.raises(IndexError):
            catalog[-3]

    def test_slicing(self, catalog):
        assert [b.get("id") for b in catalog[0:2]] == ["1", "2"]
        assert [b.get("id") for b in catalog[1:]] == ["2"]

    def test_len_counts_elements_not_text(self):
        root = fromstring("<r>text<a/>more<b/></r>")
        assert len(root) == 2

    def test_iteration_skips_text(self):
        root = fromstring("<r>text<a/>more<b/></r>")
        assert [child.tag for child in root] == ["a", "b"]

    def test_iteration_wide_element(self):
        # >3 children takes the bulk element_children path.
        root = fromstring("<r>" + "".join(f"<c{i}/>" for i in range(6)) + "</r>")
        assert [child.tag for child in root] == [f"c{i}" for i in range(6)]

    def test_iteration_wide_skips_text(self):
        root = fromstring(
            "<r>" + "".join(f"t{i}<c{i}/>" for i in range(5)) + "</r>"
        )
        assert [child.tag for child in root] == [f"c{i}" for i in range(5)]

    def test_sourceline(self):
        root = fromstring("<r>\n  <a/>\n  <b>\n    <c/>\n  </b>\n</r>\n")
        assert root.sourceline == 1
        assert root[0].sourceline == 2
        assert root[1].sourceline == 3
        assert root[1][0].sourceline == 4


class TestSiblings:
    def test_getnext_getprevious(self, catalog):
        first, second = catalog[0], catalog[1]
        assert first.getnext().get("id") == "2"
        assert second.getprevious().get("id") == "1"

    def test_getnext_skips_text(self):
        root = fromstring("<r><a/>between<b/></r>")
        assert root[0].getnext().tag == "b"

    def test_boundaries(self, catalog):
        assert catalog.getparent() is None
        assert catalog[1].getnext() is None
        assert catalog[0].getprevious() is None

    def test_getparent(self, catalog):
        assert catalog[0].getparent().tag == "library"


class TestTextModel:
    def test_simple_text(self, catalog):
        assert catalog[0].text == "Ulysses"

    def test_no_text_is_none(self):
        assert fromstring("<r/>").text is None
        assert fromstring("<r><b/></r>").text is None

    def test_text_stops_at_first_child(self):
        p = fromstring(MIXED)
        assert p.text == "Hello "
        assert p[0].text == "world"
        assert p[0].tail == "!"

    def test_tail_none_outside(self):
        root = fromstring("<r><a/></r>")
        assert root[0].tail is None

    def test_cdata_merges_into_text(self):
        root = fromstring("<a>x<![CDATA[y]]>z<b/>t</a>")
        assert root.text == "xyz"
        assert root[0].tail == "t"

    def test_cdata_only(self):
        assert fromstring("<a><![CDATA[raw <b>]]></a>").text == "raw <b>"

    def test_itertext(self):
        p = fromstring(MIXED)
        assert "".join(p.itertext()) == "Hello world!"

    def test_itertext_merges_cdata_runs(self):
        root = fromstring("<a>x<![CDATA[y]]>z<b/>t</a>")
        assert list(root.itertext()) == ["xyz", "t"]

    def test_itertext_skips_comments(self):
        root = fromstring("<r>a<!--c-->b</r>")
        assert "".join(root.itertext()) == "ab"

    def test_entity_in_text(self):
        assert fromstring("<r>a &amp; b</r>").text == "a & b"


class TestIterators:
    def test_iter_includes_self(self):
        root = fromstring("<x><y><z/></y><w/></x>")
        assert [e.tag for e in root.iter()] == ["x", "y", "z", "w"]

    def test_iter_from_mid_tree_context(self):
        root = fromstring("<x><y><z1/><w/></y><z2/></x>")
        y = root[0]
        assert [e.tag for e in y.iter()] == ["y", "z1", "w"]
        assert [e.tag for e in y.iterdescendants()] == ["z1", "w"]

    def test_iter_tag_filter(self):
        root = fromstring("<x><y><z/></y><w/></x>")
        assert [e.tag for e in root.iter("z")] == ["z"]
        assert list(root.iter("none")) == []

    def test_iter_wildcard(self):
        root = fromstring("<x><y/></x>")
        assert [e.tag for e in root.iter("*")] == ["x", "y"]

    def test_iter_clark_filter(self):
        root = fromstring("<x:root xmlns:x='urn:x'><x:a/><b/></x:root>")
        assert [e.tag for e in root.iter("{urn:x}a")] == ["{urn:x}a"]
        assert list(root.iterdescendants("{urn:x}root")) == []

    def test_iter_non_qname_tag_matches_nothing(self):
        root = fromstring("<x><y/></x>")
        assert list(root.iter("not a name")) == []
        assert list(root.iterdescendants("not a name")) == []

    def test_iterdescendants_excludes_self(self):
        root = fromstring("<x><y><z/></y><w/></x>")
        assert [e.tag for e in root.iterdescendants()] == ["y", "z", "w"]


class TestNodeLayer:
    def test_node_types_and_content(self):
        doc = fromstring("<r>text<!--c--></r>")
        node = doc.to_node()
        kinds = [child.type for child in _walk(node)]
        assert 1 in kinds  # text
        assert 2 in kinds  # comment
        assert node.child_count == 0  # counts elements only

    def test_comment_content_exact(self):
        root = fromstring("<r><!-- c --></r>")
        assert root.to_node().first_child.content == " c "

    def test_as_element_round_trip(self, catalog):
        node = catalog.to_node()
        assert node.is_element()
        assert node.as_element().tag == "library"

    def test_non_element_node_has_no_element_view(self):
        root = fromstring("<r>text</r>")
        assert root.to_node().first_child.as_element() is None

    def test_repr(self, catalog):
        assert repr(catalog).startswith("<Element 'library' at ")


def _walk(node):
    child = node.first_child
    while child is not None:
        yield child
        child = child.next_sibling

class TestIterNamespacedRoot:
    # leptris/leptris#557: descendant-or-self omits a namespaced root
    # for prefixed name tests — iter() matches self in Python and
    # walks descendant:: instead.

    def test_iter_clark_includes_namespaced_self(self):
        root = fromstring("<x:r xmlns:x='urn:x'><x:a/></x:r>")
        assert [e.tag for e in root.iter("{urn:x}r")] == ["{urn:x}r"]

    def test_iter_plain_includes_self(self):
        root = fromstring("<r><a/></r>")
        assert [e.tag for e in root.iter("r")] == ["r"]
