"""cibuildwheel CIBW_TEST_COMMAND: proves the freshly built wheel
loads its VENDORED libleptris (no LEPTRIS_LIB_PATH in this env)."""
import leptris

doc = leptris.Document.parse("<r><item n='2'/></r>")
assert doc.getroot().tag == "r"
assert doc.getroot().xpath("count(//item)") == 1.0
assert leptris.libleptris_version()
print("wheel smoke OK: leptris", leptris.__version__,
      "+ libleptris", leptris.libleptris_version())
