"""iterparse: bounded-memory incremental parsing."""

import io

import pytest

from leptris import iterparse
from leptris.error import ParseError

class TestIterparse:
    XML = "<root>" + "".join(f"<rec id='{i}'>v{i}</rec>" for i in range(5)) + "</root>"

    def test_yields_completed_top_level(self):
        from leptris import iterparse
        import io

        seen = [(e.get("id"), e.text) for _, e in iterparse(io.StringIO(self.XML))]
        assert seen == [(str(i), f"v{i}") for i in range(5)]

    def test_file_source(self, tmp_path):
        from leptris import iterparse

        path = tmp_path / "doc.xml"
        path.write_text(self.XML)
        tags = [e.tag for _, e in iterparse(str(path))]
        assert tags == ["rec"] * 5

    def test_subtree_content(self):
        from leptris import iterparse
        import io

        # Elements are borrowed: inspect within the iteration (the
        # engine releases each subtree on the next yield).
        xml = "<r><rec><a>1</a><b x='2'/></rec></r>"
        checked = []
        for _, element in iterparse(io.StringIO(xml)):
            checked.append(
                (element.tag, element[0].text, element[1].get("x"))
            )
        assert checked == [("rec", "1", "2")]

    def test_borrowed_until_next(self):
        from leptris import iterparse
        import io

        # Only the CURRENT element may be inspected; iteration runs
        # to exhaustion without holding references.
        count = 0
        for _, element in iterparse(io.StringIO(self.XML)):
            assert element.tag == "rec"
            count += 1
        assert count == 5

    def test_repeat_is_stable(self):
        from leptris import iterparse
        import io

        for _ in range(10):
            assert len(list(iterparse(io.StringIO(self.XML)))) == 5

    def test_only_end_events(self):
        from leptris import iterparse
        import io

        with pytest.raises(ValueError):
            iterparse(io.StringIO(self.XML), events=("start", "end"))
        list(iterparse(io.StringIO(self.XML), events="end"))

    def test_missing_file(self):
        from leptris import iterparse
        from leptris.error import ParseError

        with pytest.raises(ParseError):
            iterparse("/nonexistent/doc.xml")
