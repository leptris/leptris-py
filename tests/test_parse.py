"""Parsing and document lifecycle."""

import io

import pytest

from leptris import Document, fromstring, parse
from leptris import LeptrisError, ParseError

XML = "<library><book id='1'>Ulysses</book></library>"


class TestFromString:
    def test_returns_root_element(self):
        root = fromstring(XML)
        assert root.tag == "library"
        assert root[0].tag == "book"

    def test_str_and_bytes_agree(self):
        assert fromstring(XML)[0].text == fromstring(XML.encode())[0].text

    def test_bytes_only_doctype(self):
        assert fromstring(b"<?xml version='1.0'?><r/>").tag == "r"

    def test_type_error_on_non_string(self):
        with pytest.raises(TypeError):
            fromstring(123)

    def test_parse_error_raises(self):
        with pytest.raises(ParseError):
            fromstring("<unclosed>")

    def test_parse_error_message_names_cause(self):
        with pytest.raises(ParseError, match="parse error"):
            fromstring("<a></b>")


class TestParse:
    def test_path(self, tmp_path):
        path = tmp_path / "doc.xml"
        path.write_text(XML)
        with parse(str(path)) as doc:
            assert doc.getroot().tag == "library"

    def test_pathlib_object(self, tmp_path):
        path = tmp_path / "doc.xml"
        path.write_text(XML)
        with parse(path) as doc:
            assert doc.getroot().tag == "library"

    def test_file_like(self):
        with parse(io.StringIO(XML)) as doc:
            assert doc.getroot().tag == "library"
        with parse(io.BytesIO(XML.encode())) as doc:
            assert doc.getroot().tag == "library"

    def test_missing_file(self):
        with pytest.raises(ParseError):
            parse("/nonexistent/doc.xml")


class TestDocument:
    def test_parse_classmethod(self):
        with Document.parse(XML) as doc:
            assert doc.getroot().tag == "library"
            assert doc.root.tag == "library"

    def test_comment_only_document_is_not_well_formed(self):
        # XML requires a root element.
        with pytest.raises(ParseError):
            Document.parse("<!-- nothing -->")

    def test_close_is_idempotent(self):
        doc = Document.parse("<r/>")
        doc.close()
        doc.close()
        assert doc.closed

    def test_context_manager_closes(self):
        with Document.parse("<r/>") as doc:
            assert not doc.closed
        assert doc.closed

    def test_elements_keep_document_alive(self):
        root = Document.parse("<r><a/></r>").getroot()
        assert root[0].getparent().tag == "r"

    def test_access_after_close_raises(self):
        doc = Document.parse("<r/>")
        root = doc.getroot()
        doc.close()
        with pytest.raises(LeptrisError):
            root.tag
        with pytest.raises(LeptrisError):
            doc.xpath("//r")


def test_libleptris_version():
    from leptris import libleptris_version

    assert isinstance(libleptris_version(), str)
    assert libleptris_version() != ""

class TestRecover:
    def test_malformed_raises_without_recover(self):
        with pytest.raises(ParseError):
            Document.parse("<broken")

    def test_recover_yields_rootless_document(self):
        doc = Document.parse("<broken", recover=True)
        assert doc.getroot() is None
        doc.close()

    def test_recover_accepts_valid_document(self):
        with Document.parse("<r><a/></r>", recover=True) as doc:
            assert doc.xpath("count(//a)") == 1.0


class TestFreshDocumentRegression:
    # leptris/leptris#550: flat-path documents misbehave until the
    # root is touched; Document.parse promotes at construction.

    def test_xpath_without_getroot(self):
        doc = Document.parse("<r><a/></r>")
        assert doc.xpath("count(//a)") == 1.0
        doc.close()

    def test_tostring_without_getroot(self):
        from leptris import tostring

        doc = Document.parse("<r><a/></r>")
        assert tostring(doc) == b"<r><a/></r>"
        doc.close()


class TestRawAddressDocument:
    def test_empty_input_raises(self):
        with pytest.raises(ParseError):
            fromstring("")

    def test_memoryview_input(self):
        assert fromstring(memoryview(b"<r><a/></r>"))[0].tag == "a"

    def test_c14n_after_close_raises(self):
        from leptris import c14n

        doc = Document.parse("<r/>")
        doc.close()
        with pytest.raises(LeptrisError):
            c14n(doc)

    def test_write_after_close_raises(self):
        doc = Document.parse("<r/>")
        doc.close()
        with pytest.raises(LeptrisError):
            doc.write("/dev/null")

    def test_xinclude_after_close_raises(self):
        doc = Document.parse("<r/>")
        doc.close()
        with pytest.raises(LeptrisError):
            doc.process_xinclude()


class TestEdges:
    def test_bom_bytes(self):
        # UTF-8 BOM in a bytes input: leptris tolerates it (engine
        # treats the buffer as UTF-8 with no preamble stripping) and
        # the root tag is what it would have been without the BOM.
        root = fromstring(b"\xef\xbb\xbf<root/>")
        assert root.tag == "root"

    def test_parse_file_pathlib_path(self, tmp_path):
        path = tmp_path / "doc.xml"
        path.write_bytes(b"<r><a/></r>")
        with Document.parse_file(path) as doc:
            assert doc.getroot().tag == "r"

    def test_parse_file_pathlib_closed(self, tmp_path):
        path = tmp_path / "doc.xml"
        path.write_bytes(b"<r/>")
        doc = Document.parse_file(path)
        root = doc.getroot()
        doc.close()
        with pytest.raises(LeptrisError):
            root.tag


class TestNestingBoundary:
    # The engine caps document depth (default 256); lxml's expat has
    # its own recursion limit at a similar point — parity, not a gap.
    def test_depth_200_parses(self):
        xml = "<d>" * 200 + "x" + "</d>" * 200
        assert fromstring(xml).tag == "d"

    def test_depth_300_raises_cleanly(self):
        xml = "<d>" * 300 + "x" + "</d>" * 300
        with pytest.raises(ParseError):
            fromstring(xml)


class TestErrorMessageQuality:
    def test_no_doubled_generic_text(self):
        # status_message appends the thread-local last error; when it
        # is the same generic text, the message used to double it.
        from leptris.error import status_message

        assert status_message(1) != ""
        try:
            fromstring("<d>" * 300 + "x" + "</d>" * 300)
        except ParseError as e:
            assert str(e).count("XML parse error") <= 1


class TestAttributeNormalization:
    # libleptris 1.9.3 — XML 1.0 §3.3.3 (#576)
    def test_newlines_and_tabs_become_spaces(self):
        root = fromstring(b"<e a='x\ny\tz'/>")
        assert root.get("a") == "x y z"


class TestDatalessPI:
    # libleptris 1.9.3 — accept <?target?> without clobbering (#577)
    def test_dataless_pi_parses(self):
        root = fromstring(b"<?target?><r><a/></r>")
        assert root.tag == "r"
        assert root[0].tag == "a"

    def test_toplevel_pis_dataless(self):
        with Document.parse(b"<?target?><r/>") as doc:
            assert doc.toplevel_pis() == [("target", "")]


class TestDocumentLevelComments:
    # libleptris 1.9.3 — expose prolog/epilog comments (#578)
    def test_prolog_and_epilog(self):
        with Document.parse(b"<!-- pre --><r/><!-- post -->") as doc:
            assert doc.toplevel_comments() == [" pre ", " post "]

    def test_serialize_preserves_epilog(self):
        from leptris import tostring

        with Document.parse(b"<!-- pre --><r><a/></r><!-- post -->") as doc:
            assert tostring(doc) == b"<!-- pre --><r><a/></r><!-- post -->"

    def test_closed_raises(self):
        doc = Document.parse(b"<!-- c --><r/>")
        doc.close()
        with pytest.raises(LeptrisError):
            doc.toplevel_comments()
        with pytest.raises(LeptrisError):
            doc.toplevel_pis()


class TestInplaceBufferLifetime:
    # libleptris 1.9.5 (#561) made in-place parsing the fast path; the
    # engine retains pointers into the buffer until document_free, so
    # the Document owns a private copy and drops it at close.
    def test_document_outlives_input(self):
        doc = Document.parse("<catalog>" + "<r><a>text</a></r>" * 100 + "</catalog>")
        import gc

        gc.collect()
        assert doc.xpath("count(//a)") == 100.0
        root = doc.getroot()
        assert root[0][0].text == "text"
        doc.close()

    def test_close_releases_buffer(self):
        doc = Document.parse("<r/>")
        assert doc._buffer is not None
        doc.close()
        assert doc._buffer is None

    def test_user_input_never_mutated(self):
        original = b"<r><a/></r>"
        Document.parse(original)
        assert original == b"<r><a/></r>"


class TestAttributeDefaults:
    # libleptris 1.9.8: plain parse excludes ATTLIST defaults (XML 1.0
    # §5 permits either; lxml includes them, ElementTree has no DTD).
    DOC = b"""<!DOCTYPE r [<!ATTLIST r attr CDATA "default">]><r/>"""

    def test_excluded_by_default(self):
        assert fromstring(TestAttributeDefaults.DOC).get("attr") is None

    def test_opt_in_materializes(self):
        with Document.parse(self.__class__.DOC, attribute_defaults=True) as doc:
            assert doc.getroot().get("attr") == "default"

    def test_opt_in_with_recover(self):
        with Document.parse(
            b"""<!DOCTYPE r [<!ATTLIST r attr CDATA "d">]><r/>""",
            recover=True,
            attribute_defaults=True,
        ) as doc:
            assert doc.getroot().get("attr") == "d"


class TestRemoveBlankText:
    PRETTY = "<r>\n  <a>1</a>\n  <b/>\n</r>\n"

    def test_default_keeps_whitespace(self):
        root = fromstring(self.PRETTY)
        assert root.text == "\n  "
        assert root[0].tail == "\n  "

    def test_opt_in_drops_ws_only_nodes(self):
        with Document.parse(self.PRETTY, remove_blank_text=True) as doc:
            root = doc.getroot()
            assert root.text is None
            assert root[0].tail is None
            assert root[0].text == "1"
            assert len(root) == 2

    def test_combines_with_attribute_defaults(self):
        xml = b"""<!DOCTYPE r [<!ATTLIST r a CDATA "d">]>\n<r>\n  <x/>\n</r>"""
        with Document.parse(
            xml, attribute_defaults=True, remove_blank_text=True
        ) as doc:
            root = doc.getroot()
            assert root.get("a") == "d"
            assert root.text is None


class TestEncodingDetection:
    def test_utf16_bom(self):
        xml = "<?xml version='1.0'?><r><a>café</a></r>".encode("utf-16")
        root = fromstring(xml)
        assert root.tag == "r" and root[0].text == "café"

    def test_utf16_declared(self):
        xml = "<?xml version='1.0' encoding='UTF-16'?><r/>".encode("utf-16")
        assert fromstring(xml).tag == "r"

    def test_latin1_declared(self):
        # Fixed in libleptris 1.9.15 (#613): with_encoding converts
        # declared single-byte encodings; the retry now covers them.
        xml = "<?xml version='1.0' encoding='ISO-8859-1'?><r>café</r>".encode(
            "iso-8859-1"
        )
        assert fromstring(xml).text == "café"

    def test_utf8_fast_path_unchanged(self):
        assert fromstring("<r><a/></r>").tag == "r"

    def test_garbage_still_raises(self):
        with pytest.raises(ParseError):
            fromstring(b"\xff\xfe garbage not xml")


class TestSelfClosingThenText:
    # leptris 1.9.22 pinned the #653 verdict in engine specs; these
    # pin it through the binding. Well-formed self-closing-then-text
    # shapes parse (lxml parity); the report's repro carries a stray
    # </y> after a self-closed <y/> — ill-formed, rejected by both
    # leptris and libxml2 identically.
    def test_well_formed_shapes_parse(self):
        assert fromstring(b"<div><p><br/>hello</p></div>").tag == "div"
        assert fromstring(b"<r><y/>t</r>").tag == "r"

    def test_stray_close_tag_rejected_like_libxml2(self):
        with pytest.raises(ParseError):
            fromstring(b"<r><b><y/>t</y></b></r>")
