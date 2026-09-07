"""Node contract specs (TODO.restructure/13)."""

import pytest


def _walk_all_nodes(root):
    node = root.to_node().first_child
    while node is not None:
        yield node
        node = node.next_sibling


class TestNodeContract:
    SRC = "<r><a x='1'>t1</a><!--c--><![CDATA[d]]><?p d?><b/></r>"

    def test_kinds_and_predicates(self):
        from leptris import Document

        with Document.parse(self.SRC) as d:
            kids = list(_walk_all_nodes(d.getroot()))
            kinds = [n.type for n in kids]
            assert len(kinds) == 5  # element, comment, cdata, pi, element
            assert kids[0].is_element() and not kids[0].is_text()
            assert kids[1].is_comment() and not kids[1].is_element()
            assert kids[2].is_cdata()
            assert kids[3].is_pi()
            assert kids[4].is_element()

    def test_content_dispatches_by_kind(self):
        from leptris import Document

        with Document.parse(self.SRC) as d:
            kids = list(_walk_all_nodes(d.getroot()))
            assert kids[1].content == "c"
            assert kids[2].content == "d"
            # PI content is None by design: Node.content covers
            # text/comment/CDATA; PI target/data ride the PI
            # accessors, not content.
            assert kids[3].content is None

    def test_traversal_and_counts(self):
        from leptris import Document

        with Document.parse(self.SRC) as d:
            root_node = d.getroot().to_node()
            # child_count counts ELEMENT children only, while the
            # first_child/next_sibling chain walks every node kind
            # (5). Reported upstream as a Node-API inconsistency.
            assert root_node.child_count == 2
            kids = list(_walk_all_nodes(d.getroot()))
            assert kids[0].next_sibling is kids[1] or kids[0].next_sibling.content == kids[1].content
            assert kids[1].previous_sibling is not None

    def test_as_element_roundtrip(self):
        from leptris import Document

        with Document.parse(self.SRC) as d:
            kids = list(_walk_all_nodes(d.getroot()))
            assert kids[0].as_element() is not None
            assert kids[1].as_element() is None  # comment stays a Node

    def test_closed_document_raises(self):
        from leptris import Document
        from leptris.error import LeptrisError

        with Document.parse(self.SRC) as d:
            node = next(_walk_all_nodes(d.getroot()))
        with pytest.raises(LeptrisError):
            node.content
