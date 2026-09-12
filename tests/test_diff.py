"""Native XML diff (leptris.diff, libleptris 1.9.144+)."""

import pytest

from leptris import Document, diff
from leptris.error import LeptrisError


def _docs(a, b):
    return Document.parse(a), Document.parse(b)


class TestXmlDiff:
    def test_ops_full_shape(self):
        a, b = _docs(
            "<r><i a='1'>t</i><gone/></r>",
            "<r><i a='2'>t</i><new>!x</new></r>",
        )
        with a, b:
            d = diff(a, b)
            assert len(d) == 3
            ops = list(d)
            assert ops[0].type == "update-attr"
            assert (ops[0].name, ops[0].before, ops[0].after) == (
                "a", "1", "2",
            )
            assert ops[1].type == "delete"
            assert ops[1].name == "gone"
            assert ops[2].type == "insert"
            assert ops[2].name == "new"

    def test_update_text(self):
        a, b = _docs("<r>t1</r>", "<r>t2</r>")
        with a, b:
            (op,) = list(diff(a, b))
            assert op.type == "update-text"
            assert (op.before, op.after) == ("t1", "t2")

    def test_identical_documents(self):
        a, b = _docs("<r><i/></r>", "<r><i/></r>")
        with a, b:
            assert len(diff(a, b)) == 0

    def test_ignore_ws_text(self):
        pretty_a = b"<r>\n  <i/>\n</r>"
        compact_b = b"<r><i/></r>"
        a, b = _docs(pretty_a, compact_b)
        with a, b:
            assert len(diff(a, b)) > 0  # ws text differs by default
            assert len(diff(a, b, ignore_ws_text=True)) == 0

    def test_serialize_form(self):
        a, b = _docs("<r><i a='1'/></r>", "<r><i a='2'/></r>")
        with a, b:
            # line-per-op form, trailing newline included
            assert (
                diff(a, b).serialize() == '- /r/i @a "1" -> "2"\n'
            )

    def test_type_error_on_non_documents(self):
        with pytest.raises(TypeError):
            diff("<r/>", "<r/>")
