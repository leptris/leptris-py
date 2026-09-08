

class TestC14NAttributeOrder:
    # libleptris 1.9.108 (leptris/leptris#919): attributes sort by
    # namespace URI then local name (no-namespace first) — the C14N
    # ordering rule.

    def test_uri_then_local(self):
        from leptris.api import c14n
        from leptris import Document

        xml = (
            b"<doc xmlns:b='urn:b' xmlns:a='urn:a'"
            b" b:z='1' a:m='2' z='3' a:b='4' b:a='5'/>"
        )
        with Document.parse(xml) as d:
            assert c14n(d.getroot()).decode() == (
                '<doc xmlns:a="urn:a" xmlns:b="urn:b"'
                ' z="3" a:b="4" a:m="2" b:a="5" b:z="1"></doc>'
            )
