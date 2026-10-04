"""set_root foreign-root adoption (libleptris 1.9.298+, the
leptris-ruby#371 face): foreign elements deep-copy into the target
pool and the caller gets the installed handle."""

from leptris import Document, tostring


class TestSetRootAdoption:
    def test_same_document_installs_the_element(self):
        with Document.create() as doc:
            root = doc.create_element("r")
            installed = doc.set_root(root)
            assert installed.tag == "r"
            assert tostring(doc.root) == b"<r/>"

    def test_foreign_root_adopts_by_copy(self):
        # foreign elements must be parentless (the engine contract,
        # same as same-document roots): an unattached built tree
        with Document.create() as src:
            payload = src.create_element("payload", {"id": "7"})
            payload.create_child("inner").text = "text"
            with Document.create() as dst:
                installed = dst.set_root(payload)
                assert installed.tag == "payload"
                assert installed.get("id") == "7"
                assert installed[0].text == "text"
                assert tostring(dst.root) == \
                    b'<payload id="7"><inner>text</inner></payload>'

    def test_foreign_attached_child_rejected(self):
        with Document.parse("<src><payload/></src>") as src:
            with Document.create() as dst:
                try:
                    dst.set_root(src.root[0])
                    raised = False
                except Exception:
                    raised = True
                assert raised

    def test_foreign_root_leaves_source_rootless(self):
        with Document.parse("<a/>") as src:
            with Document.create() as dst:
                dst.set_root(src.root)
                assert dst.root.tag == "a"

    def test_installed_handle_is_usable(self):
        with Document.create() as src:
            y = src.create_element("y")
            with Document.create() as dst:
                installed = dst.set_root(y)
                installed.create_child("z")
                assert tostring(dst.root) == b"<y><z/></y>"
