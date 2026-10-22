"""Minimal repro: leptris-py native ops on a mingw wheel (Windows).

Run: python repro.py
On macOS/Linux every op prints OK. On the Windows mingw wheel the
first native op is expected to hard-crash the process (serialbench-py
gates these off for exactly this: adapters/xml/leptris_adapter.py,
"windows: the native ops ... segfault inside the mingw wheel").
"""
import platform
import sys

import leptris

print("python:", sys.version.split()[0], platform.machine(), platform.system())
print("accel:", leptris._leptrisaccel.__file__)

doc = leptris.XML("<r><x>1</x></r>")
SHEET = (
    "<xsl:stylesheet xmlns:xsl='http://www.w3.org/1999/XSL/Transform' version='1.0'>"
    "<xsl:template match='/'><out/></xsl:template></xsl:stylesheet>")

print("op 1/4 xquery ...", flush=True)
q = leptris.XQuery("/*[1]")
print("  xquery OK:", q(doc), flush=True)

print("op 2/4 xslt ...", flush=True)
print("  xslt OK:", leptris.XSLT(SHEET)(doc), flush=True)

print("op 3/4 xpath control ...", flush=True)
print("  xpath OK:", doc.xpath("//x/text()"), flush=True)

print("op 4/4 xslt round-trip ...", flush=True)
out = leptris.XSLT(SHEET)(doc)
print("  round-trip OK:", out.xpath("//out") is not None, flush=True)

print("ALL OPS SURVIVED", flush=True)
