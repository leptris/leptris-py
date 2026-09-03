"""XQuery 1.0 core through leptris.XQuery (libleptris 1.9.64+)."""

import pytest

from leptris import Document, XQuery
from leptris.error import LeptrisError

SRC = "<r><item v='1'>alpha</item><item v='5'>beta</item></r>"


class TestXQuery:
    def test_flwor_returns_strings_for_scalars(self):
        with Document.parse(SRC) as d:
            assert XQuery("for $i in //item return $i/@v")(d) == ["1", "5"]
            assert XQuery("for $i in //item return string($i)")(d) == [
                "alpha", "beta",
            ]

    def test_element_sequences_wrap(self):
        with Document.parse(SRC) as d:
            items = XQuery("//item")(d)
            assert [e.tag for e in items] == ["item", "item"]
            assert [e.get("v") for e in items] == ["1", "5"]

    def test_where_and_order_by(self):
        with Document.parse(SRC) as d:
            assert XQuery(
                "for $i in //item where $i/@v > 1 "
                "order by $i/@v descending return string($i)"
            )(d) == ["beta"]

    def test_positional_for(self):
        with Document.parse(SRC) as d:
            assert XQuery(
                "for $i at $p in //item return concat($p, ':', $i/@v)"
            )(d) == ["1:1", "2:5"]

    def test_scalar_results(self):
        with Document.parse(SRC) as d:
            assert XQuery("count(//item)")(d) == 2.0
            assert XQuery("let $x := 2 return $x * 21")(d) == ["42"]

    def test_prolog_variable_and_constructor(self):
        with Document.parse(SRC) as d:
            assert XQuery(
                "declare variable $n := 3; <out>{$n * 2}</out>"
            )(d) == "<out>6</out>"

    def test_prolog_namespace(self):
        with Document.parse(SRC) as d:
            assert XQuery(
                "declare namespace x = 'urn:x'; 'ns-ok'"
            )(d) == "ns-ok"

    def test_local_function(self):
        with Document.parse(SRC) as d:
            assert XQuery(
                "declare function local:dbl($x) { $x * 2 }; local:dbl(4)"
            )(d) == 8.0

    def test_try_catch_expression(self):
        with Document.parse(SRC) as d:
            assert XQuery(
                "try { error('boom') } catch * { 'caught' }"
            )(d) == "caught"

    def test_element_context(self):
        with Document.parse(SRC) as d:
            assert XQuery("string(.)")(d.getroot()[0]) == "alpha"

    def test_compile_error_raises(self):
        with pytest.raises(LeptrisError):
            XQuery("for $x in ")

    def test_reusable_across_documents(self):
        query = XQuery("count(//item)")
        with Document.parse(SRC) as d1:
            assert query(d1) == 2.0
        with Document.parse("<r><item/><item/><item/></r>") as d2:
            assert query(d2) == 3.0
