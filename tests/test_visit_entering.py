"""The entering-only subtree walk (libleptris 1.9.232+,
leptris_node_visit_entering): once per node, half the callbacks of
a full enter/leave walk."""

import pytest

from leptris import Document, LeptrisError


class TestVisitEntering:
    def test_document_order_with_depths(self):
        doc = Document.parse("<r><a>1</a>mid<b>2</b><!--c--></r>")
        seen = []
        doc.root.visit_entering(
            lambda node, depth: seen.append((node, depth))
        )
        kinds = [
            (getattr(n, "tag", None) or f"node{n.type}", d)
            for n, d in seen
        ]
        assert kinds == [
            ("r", 0), ("a", 1), ("node1", 2), ("node1", 1),
            ("b", 1), ("node1", 2), ("node2", 1),
        ]

    def test_elements_visited_once(self):
        doc = Document.parse("<r><a><b><c/></b></a></r>")
        tags = []
        doc.root.visit_entering(
            lambda n, d: tags.append(n.tag)
            if hasattr(n, "tag") else None
        )
        assert tags == ["r", "a", "b", "c"]

    def test_wrapped_nodes_are_live(self):
        doc = Document.parse("<r><a x='1'>t</a></r>")
        got = []
        doc.root.visit_entering(
            lambda n, d: got.append((n, d))
        )
        a = None
        for n, d in got:
            if getattr(n, "tag", None) == "a":
                a = n
                break
        assert a.get("x") == "1"
        assert a.text == "t"

    def test_closed_document_raises(self):
        doc = Document.parse("<r/>")
        root = doc.root
        doc.close()
        with pytest.raises(LeptrisError, match="closed"):
            root.visit_entering(lambda n, d: None)

    def test_empty_subtree_visits_root_only(self):
        doc = Document.parse("<r/>")
        seen = []
        doc.root.visit_entering(lambda n, d: seen.append(d))
        assert seen == [0]
