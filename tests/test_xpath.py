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


class TestUpstreamV196:
    # leptris 1.9.6: /descendant:: seeds the document node and offers
    # the root element; $var/step heads no longer drop (bug-76).
    def test_absolute_descendant_includes_root(self):
        root = fromstring("<r><a/></r>")
        assert [e.tag for e in root.xpath("/descendant::r")] == ["r"]
        assert [e.tag for e in root.xpath("/descendant::a")] == ["a"]

    def test_variables_still_evaluate(self):
        root = fromstring(BOOKS)
        assert root.xpath(
            "//book[@id=$id]", variables={"id": "2"}
        )[0].text == "B"


class TestUpstreamV197:
    # leptris 1.9.7: document-level comments/PIs are tree children —
    # XPath //comment() and //processing-instruction() see them.
    def test_comment_sees_document_level(self):
        with Document.parse(
            b"<?pi d?><!-- pre --><r><a/><!-- inner --></r><!-- post -->"
        ) as doc:
            assert doc.xpath("//comment()") == [" pre ", " inner ", " post "]
            assert doc.xpath("//processing-instruction()") == ["d"]


class TestCompiledXPathVariables:
    def test_scalar_and_nodeset(self):
        from leptris import XPath, fromstring

        root = fromstring(BOOKS)
        query = XPath("//book[@id=$id]")
        assert query(root, variables={"id": "2"})[0].text == "B"
        assert XPath("$n + 1")(root, variables={"n": 41}) == 42.0
        assert XPath("$flag")(root, variables={"flag": True}) is True

    def test_matches_uncompiled_semantics(self):
        from leptris import XPath, fromstring

        root = fromstring(BOOKS)
        query = XPath("//book[@price > $min]")
        assert [b.text for b in query(root, variables={"min": 50})] == [
            b.text for b in root.xpath("//book[@price > 50]")
        ]

    def test_type_error_on_unsupported(self):
        from leptris import XPath, fromstring

        root = fromstring(BOOKS)
        with pytest.raises(TypeError):
            XPath("$x")(root, variables={"x": object()})

    def test_ns_plus_vars_falls_back_cleanly(self):
        from leptris import XPath, fromstring

        root = fromstring("<x:r xmlns:x='urn:x'><x:a>1</x:a></x:r>")
        query = XPath("count(//x:a)")
        assert query(
            root, namespaces={"x": "urn:x"}, variables={"unused": 0}
        ) == 1.0


class TestUpstreamV199:
    def test_attribute_axis_expands_entities(self):
        # leptris 1.9.9 (bug-59): the attribute axis returns expanded
        # values, matching @attr access.
        root = fromstring("<e t='a &amp; b'/>")
        assert root.xpath("//e/@t") == ["a & b"]

    def test_top_level_variables_with_namespaces(self):
        # leptris 1.9.9 (bug-36): top-level variables evaluate with
        # the declaring element's namespace context.
        NS = {"x": "urn:x"}
        root = fromstring("<x:r xmlns:x='urn:x'><x:a>1</x:a></x:r>")
        assert root.xpath(
            "count(//x:a)", namespaces=NS, variables={"u": 0}
        ) == 1.0


class TestRelativeNamespacedDescendant:
    # Fixed in libleptris 1.9.15 (#630 + the #557 reopen family):
    # relative descendant paths with prefixed name tests resolve
    # namespace-aware from element context.
    def test_relative_ns_descendant(self):
        NS = {"ns": "urn:ns"}
        root = fromstring(
            "<root xmlns:ns='urn:ns'><a><ns:x p='8'>t</ns:x></a></root>"
        )
        assert [e.tag for e in root.findall(".//ns:x", NS)] == ["{urn:ns}x"]
        assert [
            e.tag for e in root.xpath("descendant::ns:x", namespaces=NS)
        ] == ["{urn:ns}x"]

    def test_descendant_or_self_includes_ns_root(self):
        n = fromstring("<x:r xmlns:x='urn:x'><x:a/></x:r>")
        assert [
            e.tag for e in n.xpath("descendant-or-self::x:r", namespaces={"x": "urn:x"})
        ] == ["{urn:x}r"]


class TestXPath31:
    # libleptris 1.9.29 (XPath 3.1 Lane 0, increments 7-8): let
    # expressions, simple map !, arrow =>, string concat ||.
    SRC = (
        "<r><item v='1'>alpha</item>"
        "<item v='2'>beta</item><item v='3'>gamma</item></r>"
    )

    def test_let_binds_visible_result(self):
        root = fromstring(self.SRC)
        assert root.xpath("let $x := //item[1] return $x/@v") == ["1"]

    def test_let_shadowing_bindings(self):
        root = fromstring(self.SRC)
        assert root.xpath(
            "let $y := (//item ! string(.)) return count($y)"
        ) == 3.0

    def test_simple_map(self):
        root = fromstring(self.SRC)
        assert root.xpath("//item ! string(.)") == ["alpha", "beta", "gamma"]

    def test_simple_map_chained(self):
        root = fromstring(self.SRC)
        assert root.xpath("//item ! @v ! string()") == ["1", "2", "3"]

    def test_arrow_operator(self):
        root = fromstring(self.SRC)
        assert root.xpath(
            "string-join((//item ! string(.)), ' ') => upper-case()"
        ) == "ALPHA BETA GAMMA"

    def test_string_concat(self):
        root = fromstring(self.SRC)
        assert root.xpath("//item[1] || '-' || //item[3]") == "alpha-gamma"

    def test_combined_form(self):
        # The release-notes composite: sequence build, map, arrow, sum.
        root = fromstring(self.SRC)
        assert root.xpath(
            "let $x := 5 return ($x to 7) ! (. * 2) => sum()"
        ) == 36.0


class TestXPath20Composition:
    # The 2.0 composition grammar shipped with the XSLT 3.0
    # increments (for/if/to) — verified through plain XPath too.
    SRC = (
        "<r><item v='1'>alpha</item>"
        "<item v='5'>beta</item><item v='9'>gamma</item></r>"
    )

    def test_for_expression(self):
        root = fromstring(self.SRC)
        assert root.xpath("for $i in //item return string($i/@v)") == [
            "1", "5", "9",
        ]

    def test_if_expression(self):
        root = fromstring(self.SRC)
        assert root.xpath(
            "if (count(//item) > 2) then 'many' else 'few'"
        ) == "many"

    def test_range_expression(self):
        root = fromstring(self.SRC)
        assert root.xpath("count(1 to 10)") == 10.0

    def test_try_catch_expression(self):
        # leptris/leptris#692: real try/catch expressions landed in
        # libleptris 1.9.66 (after a 1.9.41 loud-rejection interim).
        root = fromstring("<r/>")
        assert root.xpath("try { 'plain' } catch * { 'caught' }") == "plain"
        assert root.xpath(
            "try { error('boom') } catch * { 'caught' }"
        ) == "caught"


class TestXPath20Functions:
    # libleptris 1.9.35-1.9.36 (#691 slices): sequence math, the
    # regex trio, math:, and the strings/QNames/URIs slice — all
    # through plain XPath.
    SRC = "<r><item v='1'>alpha</item><item v='5'>beta</item><item v='9'>gamma</item></r>"

    def test_sequence_existence(self):
        root = fromstring(self.SRC)
        assert root.xpath("exists(//item[@v='99'])") is False
        assert root.xpath("empty(//nope)") is True
        assert root.xpath("exists(//item[@v='5'])") is True

    def test_sequence_aggregates(self):
        root = fromstring(self.SRC)
        assert root.xpath("avg(//item/@v)") == 5.0
        assert root.xpath("min(//item/@v)") == 1.0
        assert root.xpath("max(//item/@v)") == 9.0
        assert root.xpath("count(distinct-values((1, 1, 2)))") == 2.0

    def test_sequence_manipulation(self):
        root = fromstring(self.SRC)
        assert root.xpath("head((1, 2, 3))") == ["1"]
        assert root.xpath("count(remove((1, 2, 3), 1))") == 2.0
        assert root.xpath("count(subsequence(1 to 100, 10, 5))") == 5.0

    def test_regex_trio(self):
        # MSVC builds ship no regex engine — the trio raises loudly
        # there (leptris/leptris#686 family), like analyze-string.
        import sys

        root = fromstring(self.SRC)
        if sys.platform == "win32":
            from leptris.error import XPathError

            with pytest.raises(XPathError):
                root.xpath("matches('alpha', 'a')")
            return
        assert root.xpath("matches('alpha', '^al.*a$')") is True
        assert root.xpath("matches('alpha', '^al+a$')") is False
        assert root.xpath("replace('a-b-c', '-', '_')") == "a_b_c"
        assert root.xpath(
            "string-join(tokenize('a,b,c', ','), '|')"
        ) == "a|b|c"

    def test_regex_trio_node_args(self):
        # leptris/leptris#691 comment fixed in 1.9.38: node
        # first-arguments atomize to the string value. (MSVC: no
        # regex engine at all — raises loudly there instead.)
        import sys

        root = fromstring(self.SRC)
        if sys.platform == "win32":
            from leptris.error import XPathError

            with pytest.raises(XPathError):
                root.xpath("matches(//item[1], 'a')")
            return
        assert root.xpath("matches(//item[1], '^al.*a$')") is True
        assert root.xpath("replace(//item[1], 'al', 'AL')") == "ALpha"

    def test_math_namespace(self):
        root = fromstring(self.SRC)
        assert root.xpath("math:sqrt(9)") == 3.0
        assert root.xpath("abs(-3)") == 3.0
        assert root.xpath("round-half-to-even(2.5)") == 2.0
        assert root.xpath("math:pi()") == 3.141592653589793

    def test_strings_qnames_uris(self):
        root = fromstring(self.SRC)
        assert root.xpath("format-integer(12, 'W')") == "TWELVE"
        assert root.xpath("format-integer(5, 'a')") == "e"
        assert root.xpath("contains-token('a b c', 'b')") is True
        assert root.xpath("codepoints-to-string(65)") == "A"
        assert root.xpath("escape-html-uri('<a>')") == "&lt;a&gt;"
        assert root.xpath("encode-for-uri('a b')") == "a%20b"
        assert root.xpath("string(node-name(//item[1]))") == "item"


class TestXPathDateSlice:
    # libleptris 1.9.40 (#691-E): xs:date/dateTime constructors and
    # the component accessors.

    def test_xs_date_constructor(self):
        root = fromstring("<r/>")
        assert root.xpath("string(xs:date('2020-03-01'))") == "2020-03-01"

    def test_date_component_accessors(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "year-from-dateTime(xs:dateTime('2020-03-01T10:30:00'))"
        ) == 2020.0


class TestXsConstructors:
    # libleptris 1.9.49 (lane 06): xs: atomic constructors through
    # plain XPath. xs:boolean string-lexical rules and xs:integer
    # invalid-lexical handling diverge from XSD — leptris/leptris#739.

    def test_numeric_constructors(self):
        root = fromstring("<r/>")
        assert root.xpath("xs:integer('42') + 1") == 43.0
        assert root.xpath("xs:integer(3.9)") == 3.0
        assert root.xpath("xs:double('2.5') * 2") == 5.0
        assert root.xpath("xs:decimal('1.25') + 1") == 2.25

    def test_boolean_constructors(self):
        # leptris/leptris#739 fixed in 1.9.61: string arguments
        # follow the XSD lexical mapping.
        root = fromstring("<r/>")
        assert root.xpath("xs:boolean(' true ')") is True
        assert root.xpath("xs:boolean('0')") is False
        assert root.xpath("xs:boolean('false')") is False
        assert root.xpath("xs:boolean(1)") is True
        assert root.xpath("xs:boolean(xs:double('NaN'))") is False

    def test_integer_lexical_errors(self):
        # leptris/leptris#739: an invalid lexical form raises instead
        # of producing NaN.
        from leptris.error import XPathError

        root = fromstring("<r/>")
        with pytest.raises(XPathError):
            root.xpath("xs:integer(' -3.9 ')")

    def test_string_constructors(self):
        root = fromstring("<r/>")
        assert root.xpath("xs:string(42)") == "42"
        assert root.xpath("string(xs:anyURI('a b'))") == "a b"


class TestXPathCastFamily:
    # libleptris 1.9.50 (lane 06): instance of / castable as /
    # cast as / treat as. Numeric cast targets and element() items
    # are broken — leptris/leptris#744.

    def test_castable(self):
        root = fromstring("<r/>")
        assert root.xpath("'12' castable as xs:integer") is True
        assert root.xpath("'x' castable as xs:integer") is False

    def test_instance_of(self):
        root = fromstring("<r><i/></r>")
        assert root.xpath("//i instance of node()") is True
        assert root.xpath("42 instance of xs:integer") is True

    def test_instance_of_node_kinds_and_cardinality(self):
        # leptris/leptris#744 fixed in 1.9.61: node kinds and
        # occurrence indicators match.
        root = fromstring("<r><i/>t</r>")
        assert root.xpath("//i instance of element()") is True
        assert root.xpath("('a', 'b') instance of xs:string+") is True

    def test_cast_string_and_treat(self):
        root = fromstring("<r><i/></r>")
        assert root.xpath("42 cast as xs:string") == "42"
        assert [e.tag for e in root.xpath("//i treat as element()")] == ["i"]


class TestXPathFunctionItems:
    # libleptris 1.9.60/1.9.63 (lane 07): function items, partial
    # application, inline functions, dynamic calls, HOFs.

    def test_named_function_reference(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "let $f := upper-case#1 return $f('abc')"
        ) == "ABC"

    def test_inline_function(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "let $f := function($x) { $x + 1 } return $f(41)"
        ) == 42.0

    def test_dynamic_call(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "let $f := concat#2 return $f('a', 'b')"
        ) == "ab"

    def test_fold_left(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "fold-left(1 to 3, 0, function($a, $b) { $a + $b })"
        ) == "6"

    def test_for_each(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "string-join(for-each(1 to 3, function($x) { $x * 2 }), ',')"
        ) == "2,4,6"


class TestXPath20Grammar:
    # libleptris 1.9.73 (the XPath 2.0 ledger): quantified
    # expressions, set algebra, node comparisons, ends-with,
    # deep-equal, and the empty sequence.

    SRC = "<r><item cat='a' v='1'>x</item><item cat='b' v='2'>y</item><item cat='a' v='3'>z</item></r>"

    def test_quantified(self):
        root = fromstring(self.SRC)
        assert root.xpath("some $i in //item satisfies $i/@v > 2") is True
        assert root.xpath("every $i in //item satisfies $i/@v > 0") is True
        assert root.xpath("every $i in //item satisfies $i/@v > 2") is False

    def test_set_algebra(self):
        root = fromstring(self.SRC)
        assert root.xpath("count(//item intersect //item[@cat='a'])") == 2.0
        assert root.xpath("count(//item except //item[1])") == 2.0

    def test_node_comparisons(self):
        root = fromstring(self.SRC)
        assert root.xpath("//item[1] is //item[1]") is True
        assert root.xpath("boolean(//item[1] << //item[2])") is True
        assert root.xpath("boolean(//item[2] << //item[1])") is False

    def test_2_0_function_twins(self):
        root = fromstring(self.SRC)
        assert root.xpath("ends-with(//item[3], 'z')") is True
        assert root.xpath("deep-equal(//item[1], //item[1])") is True
        assert root.xpath("count(())") == 0.0


class TestXPathFunctionTail:
    # libleptris 1.9.77-1.9.79 (#691 tail + #692): date/duration
    # accessors, the scalar tail, environment functions, seeded RNG,
    # and function calls as path steps.

    def test_date_accessors(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "month-from-date(xs:date('2020-03-01'))"
        ) == 3.0
        assert root.xpath(
            "hours-from-dateTime(xs:dateTime('2020-03-01T10:30:00'))"
        ) == 10.0

    def test_duration_constructors(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "string(xs:dayTimeDuration('PT3H30M'))"
        ) == "PT3H30M"
        assert root.xpath(
            "string(xs:yearMonthDuration('P1Y2M'))"
        ) == "P1Y2M"

    def test_scalar_tail(self):
        root = fromstring("<r/>")
        assert root.xpath("compare('a', 'b')") == -1.0
        assert root.xpath("codepoint-equal('a', 'a')") is True
        assert root.xpath("round(2.5678, 2)") == 2.57

    def test_environment_functions(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "boolean(environment-variable('PATH') != '')"
        ) is True
        assert root.xpath("unparsed-text-available('nope.txt')") is False

    def test_seeded_random_number_generator(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "random-number-generator(1)?number >= 0"
        ) is True
        assert root.xpath(
            "let $a := random-number-generator(42)?number return "
            "$a = random-number-generator(42)?number"
        ) is True

    def test_function_as_path_step(self):
        root = fromstring("<r><item v='1'>alpha</item></r>")
        assert root.xpath(
            "string-join(//item ! string(@v) => concat('-'), '')"
        ) == "1-"


class TestXPathFormatNumber:
    # libleptris 1.9.80 (#691): format-number as a plain XPath
    # function (previously XSLT-context only).

    def test_pictures(self):
        root = fromstring("<r/>")
        assert root.xpath(
            "format-number(1234.5, '#,###.00')"
        ) == "1,234.50"
        assert root.xpath("format-number(0.42, '0%')") == "42%"
        assert root.xpath("format-number(-5, '#;(#)')") == "(5)"
