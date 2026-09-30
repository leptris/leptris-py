"""The typed attribute face: get_int/get_float/get_bool in one C
crossing (leptris_element_attribute_{int,double,bool}).

Semantics pinned by direct engine probe against libleptris 1.9.280:

- int: strict full parse (leading/trailing whitespace tolerated);
  missing, empty, or non-numeric -> default
- double: strict like int (missing, empty, or unparseable ->
  default)
- bool: truthy (case-insensitive) true/1/yes; falsy false/0;
  missing or unrecognized -> default
"""

import pytest

from leptris import fromstring


@pytest.fixture
def elem():
    return fromstring(
        "<e a='42' b=' 7' c='-3' d='' x='abc' w=' 12x'"
        " e='3.5' f='1e3' g='true' h='FALSE' i='1' j='0' k='yes'/>"
    )


class TestGetInt:
    def test_plain(self, elem):
        assert elem.get_int("a") == 42

    def test_surrounding_whitespace(self, elem):
        assert elem.get_int("b") == 7

    def test_negative(self, elem):
        assert elem.get_int("c") == -3

    def test_empty_returns_default(self, elem):
        assert elem.get_int("d") == 0
        assert elem.get_int("d", 99) == 99

    def test_missing_returns_default(self, elem):
        assert elem.get_int("zz") == 0
        assert elem.get_int("zz", -7) == -7

    def test_non_numeric_is_strict(self, elem):
        assert elem.get_int("x", 5) == 5
        assert elem.get_int("w", 5) == 5  # trailing junk rejected

    def test_plain_names_only(self, elem):
        with pytest.raises(ValueError):
            elem.get_int("{urn:x}a")

    def test_str_only(self, elem):
        with pytest.raises(TypeError):
            elem.get_int(b"a")


class TestGetFloat:
    def test_plain(self, elem):
        assert elem.get_float("e") == 3.5

    def test_exponent(self, elem):
        assert elem.get_float("f") == 1000.0

    def test_empty_returns_default(self, elem):
        assert elem.get_float("d") == 0.0
        assert elem.get_float("d", 1.25) == 1.25

    def test_missing_returns_default(self, elem):
        assert elem.get_float("zz") == 0.0
        assert elem.get_float("zz", 7.5) == 7.5

    def test_unparseable_returns_default(self, elem):
        assert elem.get_float("x", 7.5) == 7.5
        assert elem.get_float("w", 7.5) == 7.5  # trailing junk rejected


class TestGetBool:
    @pytest.mark.parametrize("name", ["g", "i", "k"])
    def test_truthy(self, elem, name):
        assert elem.get_bool(name) is True

    def test_truthy_case_insensitive(self, elem):
        assert fromstring("<e v='TRUE'/>").get_bool("v") is True

    @pytest.mark.parametrize("name", ["h", "j"])
    def test_falsy(self, elem, name):
        assert elem.get_bool(name) is False

    def test_missing_returns_default(self, elem):
        assert elem.get_bool("zz") is False
        assert elem.get_bool("zz", True) is True

    def test_unrecognized_returns_default(self, elem):
        assert elem.get_bool("x") is False
        assert elem.get_bool("x", True) is True


class TestLifecycle:
    def test_closed_document_raises(self, elem):
        doc = elem.getroottree() if hasattr(elem, "getroottree") else None
        elem.document.close()
        with pytest.raises(Exception):
            elem.get_int("a")
