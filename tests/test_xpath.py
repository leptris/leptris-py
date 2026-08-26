"""XPath: scalar types, nodesets, namespaces, variables, find*."""

import pytest

from leptris import Document, fromstring
from leptris import ParseError, XPathError

BOOKS = (
    "<library><book id='1' price='10'>A</book>"
    "<book id='2' price='90'>B</book></library>"
)

NS_XML = (
    "<x:root xmlns:x='urn:ex' xmlns:d='urn:def'>"
    "<x:item x:prio='high'>first</x:item>"
    "<d:thing/>"
    "<plain/>"
    "</x:root>"
)


@pytest.fixture()
def books():
    return fromstring(BOOKS)


class TestScalars:
    def test_number(self, books):
        assert books.xpath("count(//book)") == 2.0

    def test_string(self, books):
        assert books.xpath("string(//book[@id='2'])") == "B"

    def test_boolean(self, books):
        assert books.xpath("count(//book) = 2") is True
        assert books.xpath("count(//book) = 5") is False

    def test_document_context(self):
        with Document.parse(BOOKS) as doc:
            assert doc.xpath("count(//book)") == 2.0

    def test_element_context(self, books):
        assert books[0].xpath("string(@id)") == "1"
        assert books[1].xpath("count(../book)") == 2.0


class TestNodesets:
    def test_elements(self, books):
        found = books.xpath("//book")
        assert [b.text for b in found] == ["A", "B"]

    def test_predicate(self, books):
        assert books.xpath("//book[@id='2']/text()") == ["B"]

    def test_attribute_selection_returns_strings(self, books):
        assert books.xpath("//book/@id") == ["1", "2"]

    def test_mixed_nodeset_preserves_order_and_types(self):
        root = fromstring("<r><a id='1'>x</a><a id='2'>y</a></r>")
        result = root.xpath("//a | //a/@id")
        # Fixed upstream in libleptris 1.6.0 (#514): attribute
        # entries in mixed nodesets carry their values.
        assert len(result) == 4
        assert [type(item).__name__ for item in result] == [
            "Element", "str", "Element", "str",
        ]
        assert result[0].text == "x" and result[1] == "1"
        assert result[2].text == "y" and result[3] == "2"

    def test_union_deduplicates(self, books):
        assert len(books.xpath("//book | //book")) == 2

    def test_empty_nodeset(self, books):
        assert books.xpath("//nothing") == []


class TestNamespaces:
    def test_prefixed_query(self):
        root = fromstring(NS_XML)
        items = root.xpath("//x:item", namespaces={"x": "urn:ex"})
        assert [e.text for e in items] == ["first"]

    def test_count_with_namespaces(self):
        root = fromstring(NS_XML)
        assert root.xpath("count(//x:item)", namespaces={"x": "urn:ex"}) == 1.0

    def test_default_namespace_query(self):
        root = fromstring(NS_XML)
        things = root.xpath("//d:thing", namespaces={"d": "urn:def"})
        assert len(things) == 1

    def test_clark_notation_is_invalid_xpath(self):
        # Clark tags are translated by find/findall; raw xpath() follows
        # XPath 1.0 syntax, where { } is invalid (same as lxml).
        root = fromstring(NS_XML)
        with pytest.raises(XPathError):
            root.xpath("//{urn:ex}item")


class TestVariables:
    def test_number(self):
        root = fromstring(BOOKS)
        assert root.xpath("$n > 1", variables={"n": 2}) is True
        assert root.xpath("$n + 1", variables={"n": 41}) == 42.0

    def test_string(self):
        root = fromstring(BOOKS)
        assert root.xpath("$who", variables={"who": "me"}) == "me"

    def test_boolean_and_int(self):
        root = fromstring(BOOKS)
        assert root.xpath("$flag", variables={"flag": True}) is True
        assert root.xpath("$flag", variables={"flag": False}) is False

    def test_in_expression(self):
        root = fromstring(BOOKS)
        found = root.xpath("//book[@id=$id]", variables={"id": "2"})
        assert [b.text for b in found] == ["B"]

    def test_type_error_on_unsupported_value(self):
        root = fromstring(BOOKS)
        with pytest.raises(TypeError):
            root.xpath("$x", variables={"x": object()})


class TestFind:
    def test_findall_children(self, books):
        assert [b.text for b in books.findall("book")] == ["A", "B"]

    def test_findall_descendants(self, books):
        assert len(books.findall(".//book")) == 2

    def test_findall_with_predicate(self, books):
        assert [b.text for b in books.findall("book[@id='2']")] == ["B"]

    def test_find_first_or_none(self, books):
        assert books.find("book").text == "A"
        assert books.find("nope") is None

    def test_findtext(self, books):
        assert books.findtext("book") == "A"
        assert books.findtext("nope") is None
        assert books.findtext("nope", "fallback") == "fallback"

    def test_findtext_empty_element(self):
        root = fromstring("<r><a/></r>")
        assert root.findtext("a") is None
        assert root.findtext("a", "d") == "d"

    def test_clark_names(self):
        root = fromstring(NS_XML)
        assert root.findall("{urn:ex}item")[0].text == "first"
        assert root.find("{urn:def}thing") is not None
        assert root.find("{urn:ex}nope") is None

    def test_clark_with_declared_prefixes(self):
        root = fromstring(NS_XML)
        found = root.findall("x:item", namespaces={"x": "urn:ex"})
        assert [e.text for e in found] == ["first"]

    def test_superset_xpath_accepted(self):
        # ElementPath would reject these; XPath 1.0 accepts them.
        root = fromstring(BOOKS)
        assert root.findall("book[@price > 50]")[0].text == "B"
        assert len(root.findall(".//book | .//book")) == 2


class TestErrors:
    def test_invalid_expression(self, books):
        with pytest.raises(XPathError):
            books.xpath("///[")

    def test_unknown_prefix_returns_empty(self, books):
        # Unlike lxml (which raises), an undeclared prefix evaluates to
        # an empty nodeset — documented in the README differences table.
        assert books.xpath("//nope:book") == []

    def test_error_carries_message(self, books):
        with pytest.raises(XPathError, match="XPath"):
            books.xpath("///[")

    def test_parse_error_type(self):
        with pytest.raises(ParseError):
            fromstring("<a>")

class TestNamespaceAwareGet:
    def test_clark_get(self):
        root = fromstring(
            "<x:r xmlns:x='urn:x' x:id='7' plain='v'/>"
        )
        assert root.get("{urn:x}id") == "7"
        assert root.get("{urn:x}nope") is None
        assert root.get("plain") == "v"
        assert root.get("{urn:x}id", "d") == "7"
        assert root.get("nope", "d") == "d"

    def test_clark_get_wrong_uri(self):
        root = fromstring("<x:r xmlns:x='urn:x' x:id='7'/>")
        assert root.get("{urn:other}id") is None

class TestCompiledXPath:
    def test_scalar(self):
        from leptris import XPath, fromstring

        root = fromstring("<r><a>1</a><a>2</a></r>")
        query = XPath("count(//a)")
        assert query(root) == 2.0
        assert query(root) == 2.0  # reusable

    def test_nodeset(self):
        from leptris import XPath, fromstring

        root = fromstring("<r><a id='1'>x</a><a id='2'>y</a></r>")
        query = XPath("//a[@id='2']")
        assert query(root)[0].text == "y"

    def test_document_argument(self):
        from leptris import XPath, Document

        with Document.parse("<r><a/></r>") as doc:
            assert len(XPath("//a")(doc)) == 1

    def test_context_element(self):
        from leptris import XPath, fromstring

        root = fromstring("<r><b id='1'/><b id='2'/></r>")
        assert XPath("string(@id)")(root[1]) == "2"

    def test_namespaces(self):
        from leptris import XPath, fromstring

        root = fromstring("<x:r xmlns:x='urn:x'><x:a/></x:r>")
        query = XPath("count(//x:a)")
        assert query(root, namespaces={"x": "urn:x"}) == 1.0

    def test_invalid_expression_raises(self):
        from leptris import XPath
        from leptris.error import XPathError

        with pytest.raises(XPathError):
            XPath("///[")

    def test_repr(self):
        from leptris import XPath

        assert repr(XPath("//a")) == "<XPath '//a'>"

class TestCompiledXPathFastPath:
    def test_compiled_with_ns_matches_plain(self):
        from leptris import XPath, fromstring

        root = fromstring(
            "<x:r xmlns:x='urn:x'><x:a>1</x:a><x:a>2</x:a><b/></x:r>"
        )
        ns = {"x": "urn:x"}
        query = XPath("//x:a")
        assert [e.text for e in query(root, namespaces=ns)] == ["1", "2"]
        assert [e.tag for e in query(root, namespaces=ns)] == [
            e.tag for e in root.xpath("//x:a", namespaces=ns)
        ]
        assert XPath("count(//x:a)")(root, namespaces=ns) == 2.0
