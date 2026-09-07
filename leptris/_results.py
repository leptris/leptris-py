"""The binding's result model: engine results -> Python values.

Shared by every evaluation surface (XPath, XQuery): nodesets wrap
source-tree Elements in batch or fall back to stringified synthetic
slots; scalars convert to float/str/bool. One module owns the
conversion so engines stay evaluation-only.
"""

from . import _ffi


def convert(document, result):
    """Convert a live LeptrisXPathResult (nodeset or scalar),
    freeing the result handle."""
    ffi = _ffi.ffi
    result_type = _ffi.lib.leptris_xpath_result_type(result)
    try:
        if result_type == _ffi.XPATH_NODESET:
            return nodeset(document, result)
        if result_type == _ffi.XPATH_NUMBER:
            return _ffi.lib.leptris_xpath_result_number(result)
        if result_type == _ffi.XPATH_STRING:
            ptr = _ffi.lib.leptris_xpath_result_string(result)
            if ptr == ffi.NULL:
                return ""
            value = ffi.string(ptr).decode("utf-8")
            _ffi.lib.leptris_free_string(ptr)
            return value
        if result_type == _ffi.XPATH_BOOLEAN:
            return bool(_ffi.lib.leptris_xpath_result_boolean(result))
        return None
    finally:
        _ffi.lib.leptris_xpath_result_free(result)


def nodeset(document, result) -> list:
    from .element import Element

    lib = _ffi.lib
    ffi = _ffi.ffi
    count = lib.leptris_xpath_result_count(result)
    if count == 0:
        return []
    # Fast path: one batch call fills the array when every node in
    # the result is an element; mixed nodesets return copied <
    # count and take the per-index path (strings for non-element
    # slots, which result_get reports as NULL).
    buffer = ffi.new("LeptrisElement[]", count)
    copied = lib.leptris_xpath_result_get_nodes(result, buffer, count)
    if copied == count:
        from .element import _materialize

        return _materialize(buffer, document)
    from .element import _make

    items = []
    append = items.append
    for index in range(count):
        ptr = lib.leptris_xpath_result_get(result, index)
        if ptr != ffi.NULL:
            append(_make(ptr, document))
        else:
            value = lib.leptris_xpath_result_node_value(result, index)
            append(ffi.string(value).decode("utf-8") if value != ffi.NULL else "")
    return items
