/* Accelerated Element allocation and hot accessors for leptris.
 *
 * Instances are allocated here, in C, and — after bind() receives
 * the libleptris function addresses — the hot accessors (tag, text,
 * attrib, get, len, indexing, getparent/getnext) also run entirely
 * in C, calling libleptris directly. The rest of the API surface
 * stays in Python: leptris/element.py attaches its methods onto this
 * heap type after import, skipping the members implemented here.
 *
 * Each instance stores BOTH the raw element pointer (for the C
 * accessors) and the cffi cdata handle (so pure-Python call sites
 * keep passing self._ptr to cffi unchanged), plus the owning
 * Document.
 *
 * Built against the limited API (abi3): one wheel per platform
 * serves every supported CPython. Without the extension,
 * leptris.element falls back to the equivalent pure-Python class.
 */

#define PY_SSIZE_T_CLEAN
#define Py_LIMITED_API 0x03090000
#include <Python.h>

#define ACCEL_RAW_INVALID ((void *)-1)

typedef struct AccelElement AccelElement;
typedef struct {
    AccelElement *first;
    AccelElement *last;
} Registry;

typedef struct AccelElement {
    PyObject_HEAD
    void *raw;          /* raw LeptrisElement pointer, or ACCEL_RAW_INVALID */
    PyObject *ptr;      /* cffi cdata for the LeptrisElement handle */
    PyObject *document; /* owning Document (strong reference) */
    Registry *registry; /* owning document registry (NULL when unlinked) */
    AccelElement *prev;
    AccelElement *next;
    PyObject *cached_tag;    /* documents are immutable: cache forever */
    PyObject *cached_attrib;
} AccelElement;

static PyTypeObject *ElementType;
static PyTypeObject *ReadOnlyDictType;

/* dict with assignment/removal disabled — the binding is read-only. */
static int
rodict_ass_subscript(PyObject *self, PyObject *key, PyObject *value)
{
    PyErr_SetString(PyExc_TypeError, "'attrib' is read-only");
    return -1;
}

static Py_ssize_t
rodict_sq_ass_item(PyObject *self, Py_ssize_t index, PyObject *value)
{
    PyErr_SetString(PyExc_TypeError, "'attrib' is read-only");
    return -1;
}

/* libleptris entry points, bound once from Python via addresses. */
static struct {
    const char *(*element_name)(void *);
    const char *(*element_namespace)(void *);
    const char *(*element_attribute)(void *, const char *);
    const char *(*element_attribute_ns)(void *, const char *, const char *);
    void *(*element_child)(void *, size_t);
    size_t (*element_child_count)(void *);
    void *(*element_as_node)(void *);
    void *(*node_first_child)(void *);
    void *(*node_next_sibling)(void *);
    int (*node_get_type)(void *);
    const char *(*text_node_get_content)(void *);
    const char *(*cdata_node_get_content)(void *);
    void *(*element_first_child_any)(void *);
    const char *(*element_prefix_fn)(void *);
    void *(*element_previous_sibling_any_fn)(void *);
    void *(*element_first_attribute)(void *);
    void *(*attribute_next)(void *);
    const char *(*attribute_get_name)(void *);
    const char *(*attribute_get_value)(void *, void *);
    void *(*element_parent)(void *);
    void *(*element_next_sibling_any)(void *);
    int (*node_line)(void *);
    void *(*xpath_eval)(void *, void *, const char *);
    int (*xpath_result_type)(void *);
    size_t (*xpath_result_count)(void *);
    size_t (*xpath_result_get_nodes)(void *, void **, size_t);
    void (*xpath_result_free)(void *);
    double (*xpath_result_number)(void *);
    int (*xpath_result_boolean)(void *);
    char *(*xpath_result_string)(void *);
    void (*free_string)(char *);
    void *(*ns_set_new)(void);
    void (*ns_set_free)(void *);
    int (*ns_set_add)(void *, const char *, const char *);
    void *(*xpath_eval_ns)(void *, void *, const char *, void *);
    char *(*element_serialize)(void *, void *);
    size_t (*element_serialize_into)(void *, char *, size_t, size_t *, const void *);
    char *(*document_serialize)(void *, void *);
    void *(*parse_string_fn)(const char *, size_t, int *);
    void *(*parse_string_ex)(const char *, size_t, const void *, int *);
    void *(*parse_file)(const char *, int *);
    void *(*document_root)(void *);
    void (*document_free)(void *);
} Fns;

#define FN_COUNT 43

static int bound = 0;
static PyObject *LeptrisErrorType = NULL;

/* -1 with LeptrisError set when the document was closed and this
 * element poisoned by invalidate(). ~5ns: one pointer compare. */
static int
check_poisoned(AccelElement *self)
{
    if (self->raw == ACCEL_RAW_INVALID) {
        PyErr_SetString(LeptrisErrorType, "operation on a closed document");
        return -1;
    }
    return 0;
}

static void
registry_link(Registry *reg, AccelElement *el)
{
    if (reg == NULL)
        return;
    el->registry = reg;
    el->prev = reg->last;
    el->next = NULL;
    if (reg->last != NULL)
        reg->last->next = el;
    else
        reg->first = el;
    reg->last = el;
}

static void
registry_unlink(AccelElement *el)
{
    Registry *reg = el->registry;
    if (reg == NULL)
        return;
    if (el->prev != NULL)
        el->prev->next = el->next;
    else
        reg->first = el->next;
    if (el->next != NULL)
        el->next->prev = el->prev;
    else
        reg->last = el->prev;
    el->registry = NULL;
}

static void
registry_capsule_free(PyObject *capsule)
{
    Registry *reg = (Registry *)PyCapsule_GetPointer(capsule, "leptris.registry");
    if (reg != NULL)
        PyMem_Free(reg);
}

static PyObject *
str_or_none(const char *value)
{
    if (value == NULL)
        Py_RETURN_NONE;
    return PyUnicode_DecodeUTF8(value, strlen(value), "strict");
}

/* Internal: build an Element from a raw pointer + cdata handle. */
static PyObject *
element_from_parts_reg(void *raw, PyObject *ptr, PyObject *document,
                       Registry *reg)
{
    AccelElement *el = (AccelElement *)PyType_GenericAlloc(ElementType, 0);
    if (el == NULL)
        return NULL;
    el->raw = raw;
    Py_INCREF(ptr);
    el->ptr = ptr;
    Py_INCREF(document);
    el->document = document;
    registry_link(reg, el);
    return (PyObject *)el;
}

static Registry *
registry_of(PyObject *document)
{
    if (document == NULL || document == Py_None)
        return NULL;
    PyObject *capsule = PyObject_GetAttrString(document, "_accel_registry");
    if (capsule == NULL) {
        PyErr_Clear();
        return NULL;
    }
    Registry *reg = NULL;
    if (PyCapsule_CheckExact(capsule))
        reg = (Registry *)PyCapsule_GetPointer(capsule, "leptris.registry");
    Py_DECREF(capsule);
    if (PyErr_Occurred()) {
        PyErr_Clear();
        return NULL;
    }
    return reg;
}

/* ---- field getsets -------------------------------------------------- */

static PyObject *
elem_get_ptr(AccelElement *self, void *closure)
{
    if (self->ptr == NULL)
        Py_RETURN_NONE;
    Py_INCREF(self->ptr);
    return self->ptr;
}

static int
elem_set_ptr(AccelElement *self, PyObject *value, void *closure)
{
    PyObject *tmp = self->ptr;
    Py_XINCREF(value);
    self->ptr = value;
    Py_XDECREF(tmp);
    return 0;
}

static PyObject *
elem_get_raw(AccelElement *self, void *closure)
{
    if (self->raw == NULL)
        Py_RETURN_NONE;
    return PyLong_FromVoidPtr(self->raw);
}

static int
elem_set_raw(AccelElement *self, PyObject *value, void *closure)
{
    if (value == NULL || value == Py_None) {
        self->raw = NULL;
        return 0;
    }
    if (!PyLong_Check(value)) {
        PyErr_SetString(PyExc_TypeError, "_raw must be an address int");
        return -1;
    }
    self->raw = PyLong_AsVoidPtr(value);
    return 0;
}

static PyObject *
elem_get_document(AccelElement *self, void *closure)
{
    if (self->document == NULL)
        Py_RETURN_NONE;
    Py_INCREF(self->document);
    return self->document;
}

static int
elem_set_document(AccelElement *self, PyObject *value, void *closure)
{
    PyObject *tmp = self->document;
    Py_XINCREF(value);
    self->document = value;
    Py_XDECREF(tmp);
    return 0;
}

/* ---- C accessors (active once bind() succeeded) --------------------- */

static PyObject *
elem_get_tag(AccelElement *self, void *closure)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (self->cached_tag != NULL) {
        Py_INCREF(self->cached_tag);
        return self->cached_tag;
    }
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE; /* element.py provides the Python fallback */
    const char *ns = Fns.element_namespace(self->raw);
    const char *name = Fns.element_name(self->raw);
    if (name == NULL)
        name = "";
    PyObject *result = (ns == NULL)
        ? PyUnicode_DecodeUTF8(name, strlen(name), "strict")
        : PyUnicode_FromFormat("{%s}%s", ns, name);
    if (result != NULL) {
        Py_INCREF(result);
        Py_XDECREF(self->cached_tag);
        self->cached_tag = result;
    }
    return result;
}

/* ElementTree text semantics: the merged run of adjacent text/CDATA
 * nodes before the first child, or None when there is none. */
static PyObject *
elem_get_text(AccelElement *self, void *closure)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    void *node = Fns.node_first_child(Fns.element_as_node(self->raw));
    int type = (node != NULL) ? Fns.node_get_type(node) : 0;
    if (type != 1 && type != 3)
        Py_RETURN_NONE;
    /* Fast path: a lone text/CDATA node with a non-text follower. */
    {
        void *after = Fns.node_next_sibling(node);
        int after_type = (after != NULL) ? Fns.node_get_type(after) : 0;
        if (after_type != 1 && after_type != 3) {
            const char *value = (type == 1)
                ? Fns.text_node_get_content(node)
                : Fns.cdata_node_get_content(node);
            if (value == NULL)
                return PyUnicode_FromString("");
            return PyUnicode_DecodeUTF8(value, strlen(value), "strict");
        }
    }
    /* Merge adjacent text (1) and CDATA (3) nodes. */
    PyObject *parts = PyList_New(0);
    if (parts == NULL)
        return NULL;
    while (node != NULL) {
        int t = Fns.node_get_type(node);
        if (t != 1 && t != 3)
            break;
        const char *value = (t == 1) ? Fns.text_node_get_content(node)
                                     : Fns.cdata_node_get_content(node);
        PyObject *piece = (value != NULL)
            ? PyUnicode_DecodeUTF8(value, strlen(value), "strict")
            : PyUnicode_FromString("");
        if (piece == NULL || PyList_Append(parts, piece) < 0) {
            Py_XDECREF(piece);
            Py_DECREF(parts);
            return NULL;
        }
        Py_DECREF(piece);
        node = Fns.node_next_sibling(node);
    }
    Py_ssize_t count = PyList_Size(parts);
    if (count == 1) {
        PyObject *only = PyList_GetItem(parts, 0);
        Py_INCREF(only);
        Py_DECREF(parts);
        return only;
    }
    PyObject *joined = PyUnicode_Join(PyUnicode_FromString(""), parts);
    Py_DECREF(parts);
    return joined;
}

static PyObject *
elem_get_attrib(AccelElement *self, void *closure)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    if (self->cached_attrib != NULL) {
        Py_INCREF(self->cached_attrib);
        return self->cached_attrib;
    }
    PyObject *dict = PyObject_CallNoArgs((PyObject *)ReadOnlyDictType);
    if (dict == NULL)
        return NULL;
    /* C-level insertion bypasses the (blocking) Python-level
     * __setitem__ override on purpose. */
    void *attr = Fns.element_first_attribute(self->raw);
    while (attr != NULL) {
        const char *name = Fns.attribute_get_name(attr);
        const char *value = Fns.attribute_get_value(self->raw, attr);
        if (name == NULL)
            name = "";
        if (value == NULL)
            value = "";
        PyObject *key = PyUnicode_DecodeUTF8(name, strlen(name), "strict");
        PyObject *val = PyUnicode_DecodeUTF8(value, strlen(value), "strict");
        if (key == NULL || val == NULL ||
            PyDict_SetItem(dict, key, val) < 0) {
            Py_XDECREF(key);
            Py_XDECREF(val);
            Py_DECREF(dict);
            return NULL;
        }
        Py_DECREF(key);
        Py_DECREF(val);
        attr = Fns.attribute_next(attr);
    }
    Py_INCREF(dict);
    Py_XDECREF(self->cached_attrib);
    self->cached_attrib = dict;
    return dict;
}

static Py_ssize_t
elem_sq_length(AccelElement *self)
{
    if (bound && check_poisoned(self) < 0)
        return -1;
    if (!bound || self->raw == NULL)
        return 0;
    return (Py_ssize_t)Fns.element_child_count(self->raw);
}

static PyObject *
elem_sq_item_inner(AccelElement *self, Py_ssize_t index)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL) {
        PyErr_SetString(PyExc_TypeError, "indexing unavailable");
        return NULL;
    }
    Py_ssize_t count = (Py_ssize_t)Fns.element_child_count(self->raw);
    Py_ssize_t i = index;
    if (i < 0)
        i += count;
    if (i < 0 || i >= count) {
        PyErr_SetString(PyExc_IndexError, "child index out of range");
        return NULL;
    }
    void *child = Fns.element_child(self->raw, (size_t)i);
    if (child == NULL) {
        PyErr_SetString(PyExc_IndexError, "child index out of range");
        return NULL;
    }
    /* The cdata handle is produced lazily by Python (see _cd). */
    return element_from_parts_reg(
        child, Py_None,
        self->document != NULL ? self->document : Py_None,
        self->registry);
}

static PyObject *
elem_mp_subscript(AccelElement *self, PyObject *key)
{
    if (bound && self->raw != NULL && PyLong_Check(key)) {
        Py_ssize_t index = PyLong_AsSsize_t(key);
        if (!PyErr_Occurred())
            return elem_sq_item_inner(self, index);
        PyErr_Clear();
    }
    if (bound && self->raw != NULL && PySlice_Check(key)) {
        Py_ssize_t count = (Py_ssize_t)Fns.element_child_count(self->raw);
        Py_ssize_t start, stop, step, length;
        if (PySlice_GetIndicesEx(key, count, &start, &stop, &step, &length) < 0)
            return NULL;
        PyObject *out = PyList_New(length);
        if (out == NULL)
            return NULL;
        for (Py_ssize_t i = 0; i < length; i++) {
            Py_ssize_t idx = start + i * step;
            void *child = Fns.element_child(self->raw, (size_t)idx);
            PyObject *el = element_from_parts_reg(
                child, Py_None,
                self->document != NULL ? self->document : Py_None,
                self->registry);
            if (el == NULL || PyList_SetItem(out, i, el) < 0) {
                Py_XDECREF(el);
                Py_DECREF(out);
                return NULL;
            }
        }
        return out;
    }
    /* slices and anything else: Python implementation */
    PyObject *method = PyObject_GetAttrString(
        (PyObject *)Py_TYPE(self), "_py_getitem");
    if (method == NULL)
        return NULL;
    PyObject *result = PyObject_CallFunctionObjArgs(method, (PyObject *)self, key, NULL);
    Py_DECREF(method);
    return result;
}

static PyObject *
wrap_sibling(AccelElement *self, void *sibling)
{
    if (sibling == NULL)
        Py_RETURN_NONE;
    return element_from_parts_reg(
        sibling, Py_None,
        self->document != NULL ? self->document : Py_None,
        self->registry);
}

static PyObject *
elem_getparent(AccelElement *self, PyObject *unused)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    return wrap_sibling(self, Fns.element_parent(self->raw));
}

static PyObject *
elem_getnext(AccelElement *self, PyObject *unused)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    return wrap_sibling(self, Fns.element_next_sibling_any(self->raw));
}

static PyObject *
elem_get_method(AccelElement *self, PyObject *args)
{
    PyObject *name;
    PyObject *default_value = Py_None;
    if (!PyArg_ParseTuple(args, "U|O", &name, &default_value))
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    PyObject *encoded = PyUnicode_AsUTF8String(name);
    if (encoded == NULL)
        return NULL;
    const char *utf8 = PyBytes_AsString(encoded);
    if (utf8 == NULL) {
        Py_DECREF(encoded);
        return NULL;
    }
    const char *value = NULL;
    if (utf8[0] == '{' && Fns.element_attribute_ns != NULL) {
        /* Clark "{uri}local" -> namespace-aware lookup */
        const char *close = strchr(utf8 + 1, '}');
        if (close != NULL) {
            PyObject *uri = PyBytes_FromStringAndSize(
                utf8 + 1, close - utf8 - 1);
            if (uri == NULL) {
                Py_DECREF(encoded);
                return NULL;
            }
            value = Fns.element_attribute_ns(
                self->raw, PyBytes_AsString(uri), close + 1);
            Py_DECREF(uri);
        }
    } else {
        value = Fns.element_attribute(self->raw, utf8);
    }
    Py_DECREF(encoded);
    if (value == NULL) {
        Py_INCREF(default_value);
        return default_value;
    }
    return PyUnicode_DecodeUTF8(value, strlen(value), "strict");
}

static PyObject *
text_run_after(AccelElement *self, void *first_node) /* self unused */
{
    void *node = first_node;
    PyObject *parts = PyList_New(0);
    if (parts == NULL)
        return NULL;
    while (node != NULL) {
        int t = Fns.node_get_type(node);
        if (t != 1 && t != 3)
            break;
        const char *value = (t == 1) ? Fns.text_node_get_content(node)
                                     : Fns.cdata_node_get_content(node);
        PyObject *piece = (value != NULL)
            ? PyUnicode_DecodeUTF8(value, strlen(value), "strict")
            : PyUnicode_FromString("");
        if (piece == NULL || PyList_Append(parts, piece) < 0) {
            Py_XDECREF(piece);
            Py_DECREF(parts);
            return NULL;
        }
        Py_DECREF(piece);
        node = Fns.node_next_sibling(node);
    }
    Py_ssize_t count = PyList_Size(parts);
    if (count == 0) {
        Py_DECREF(parts);
        Py_RETURN_NONE;
    }
    if (count == 1) {
        PyObject *only = PyList_GetItem(parts, 0);
        Py_INCREF(only);
        Py_DECREF(parts);
        return only;
    }
    PyObject *joined = PyUnicode_Join(PyUnicode_FromString(""), parts);
    Py_DECREF(parts);
    return joined;
}

static PyObject *
elem_get_tail(AccelElement *self, void *closure)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    void *node = Fns.node_next_sibling(Fns.element_as_node(self->raw));
    int type = (node != NULL) ? Fns.node_get_type(node) : 0;
    if (type != 1 && type != 3)
        Py_RETURN_NONE;
    return text_run_after(self, node);
}

static PyObject *
elem_get_namespace(AccelElement *self, void *closure)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    return str_or_none(Fns.element_namespace(self->raw));
}

static PyObject *
elem_get_prefix(AccelElement *self, void *closure)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    return str_or_none(Fns.element_prefix_fn(self->raw));
}

static PyObject *
elem_get_sourceline(AccelElement *self, void *closure)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    return PyLong_FromLong(
        (long)Fns.node_line(Fns.element_as_node(self->raw)));
}

static PyGetSetDef element_getsets[] = {
    {"_ptr", (getter)elem_get_ptr, (setter)elem_set_ptr,
     "cffi handle for the wrapped LeptrisElement.", NULL},
    {"_raw", (getter)elem_get_raw, (setter)elem_set_raw,
     "Raw element pointer as an int (internal).", NULL},
    {"_document", (getter)elem_get_document, (setter)elem_set_document,
     "Owning Document.", NULL},
    {"tag", (getter)elem_get_tag, NULL, "Element name (Clark notation).", NULL},
    {"text", (getter)elem_get_text, NULL, "First-run text content.", NULL},
    {"attrib", (getter)elem_get_attrib, NULL, "Attributes as a dict.", NULL},
    {"tail", (getter)elem_get_tail, NULL, "Trailing text run.", NULL},
    {"namespace", (getter)elem_get_namespace, NULL, "Namespace URI.", NULL},
    {"prefix", (getter)elem_get_prefix, NULL, "Namespace prefix.", NULL},
    {"sourceline", (getter)elem_get_sourceline, NULL, "Source line.", NULL},
    {NULL}
};

static PyObject *
elem_getprevious(AccelElement *self, PyObject *unused)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        Py_RETURN_NONE;
    return wrap_sibling(self, Fns.element_previous_sibling_any_fn(self->raw));
}

typedef struct { int want; PyObject *keys; PyObject *vals; PyObject *pairs; } AttrSink;

static int
attr_walk(AccelElement *self, AttrSink *sink)
{
    void *attr = Fns.element_first_attribute(self->raw);
    while (attr != NULL) {
        const char *name = Fns.attribute_get_name(attr);
        const char *value = Fns.attribute_get_value(self->raw, attr);
        if (name == NULL)
            name = "";
        if (value == NULL)
            value = "";
        PyObject *key = PyUnicode_DecodeUTF8(name, strlen(name), "strict");
        if (key == NULL)
            return -1;
        PyObject *val = NULL;
        if (sink->vals != NULL || sink->pairs != NULL) {
            val = PyUnicode_DecodeUTF8(value, strlen(value), "strict");
            if (val == NULL) {
                Py_DECREF(key);
                return -1;
            }
        }
        int failed = 0;
        if (sink->keys != NULL)
            failed = PyList_Append(sink->keys, key) < 0;
        if (!failed && sink->vals != NULL)
            failed = PyList_Append(sink->vals, val) < 0;
        if (!failed && sink->pairs != NULL) {
            PyObject *pair = PyTuple_Pack(2, key, val);
            if (pair == NULL || PyList_Append(sink->pairs, pair) < 0)
                failed = 1;
            Py_XDECREF(pair);
        }
        Py_DECREF(key);
        Py_XDECREF(val);
        if (failed)
            return -1;
        attr = Fns.attribute_next(attr);
    }
    return 0;
}

static PyObject *
attr_list_method(AccelElement *self, int want)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        return PyList_New(0);
    AttrSink sink = {want, NULL, NULL, NULL};
    if (want == 0) {
        sink.keys = PyList_New(0);
        if (sink.keys == NULL) return NULL;
    } else if (want == 1) {
        sink.vals = PyList_New(0);
        if (sink.vals == NULL) return NULL;
    } else {
        sink.pairs = PyList_New(0);
        if (sink.pairs == NULL) return NULL;
    }
    if (attr_walk(self, &sink) < 0) {
        Py_XDECREF(sink.keys);
        Py_XDECREF(sink.vals);
        Py_XDECREF(sink.pairs);
        return NULL;
    }
    if (want == 0) return sink.keys;
    if (want == 1) return sink.vals;
    return sink.pairs;
}

static PyObject *
elem_keys(AccelElement *self, PyObject *unused)
{
    return attr_list_method(self, 0);
}

static PyObject *
elem_values(AccelElement *self, PyObject *unused)
{
    return attr_list_method(self, 1);
}

static PyObject *
elem_items(AccelElement *self, PyObject *unused)
{
    return attr_list_method(self, 2);
}

/* Document-order text runs of the subtree, merged per run. */
static int
itertext_walk(void *element, PyObject *out)
{
    void *node = Fns.node_first_child(Fns.element_as_node(element));
    while (node != NULL) {
        int type = Fns.node_get_type(node);
        if (type == 1 || type == 3) {
            PyObject *run = text_run_after(NULL, node);
            if (run == NULL || PyList_Append(out, run) < 0) {
                Py_XDECREF(run);
                return -1;
            }
            Py_DECREF(run);
            while (node != NULL) { /* skip the consumed run */
                int t = Fns.node_get_type(node);
                if (t != 1 && t != 3)
                    break;
                node = Fns.node_next_sibling(node);
            }
        } else {
            if (type == 0 && itertext_walk(node, out) < 0)
                return -1;
            node = Fns.node_next_sibling(node);
        }
    }
    return 0;
}

static PyObject *
elem_itertext(AccelElement *self, PyObject *unused)
{
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        return PyList_New(0);
    PyObject *out = PyList_New(0);
    if (out == NULL)
        return NULL;
    if (itertext_walk(self->raw, out) < 0) {
        Py_DECREF(out);
        return NULL;
    }
    return out;
}

static PyMethodDef element_methods[] = {
    {"getparent", (PyCFunction)elem_getparent, METH_NOARGS,
     "Parent element or None."},
    {"getnext", (PyCFunction)elem_getnext, METH_NOARGS,
     "Next element sibling or None."},
    {"get", (PyCFunction)elem_get_method, METH_VARARGS,
     "get(name, default=None) -> attribute value."},
    {"getprevious", (PyCFunction)elem_getprevious, METH_NOARGS,
     "Previous element sibling or None."},
    {"keys", (PyCFunction)elem_keys, METH_NOARGS,
     "Attribute names in document order."},
    {"items", (PyCFunction)elem_items, METH_NOARGS,
     "(name, value) pairs in document order."},
    {"values", (PyCFunction)elem_values, METH_NOARGS,
     "Attribute values in document order."},
    {"itertext", (PyCFunction)elem_itertext, METH_NOARGS,
     "Merged text runs of the subtree, document order."},
    {NULL}
};

static void
element_dealloc(AccelElement *self)
{
    registry_unlink(self);
    Py_XDECREF(self->ptr);
    Py_XDECREF(self->document);
    Py_XDECREF(self->cached_tag);
    Py_XDECREF(self->cached_attrib);
    PyObject_Free(self);
}

static PyType_Slot element_slots[] = {
    {Py_tp_dealloc, (void *)element_dealloc},
    {Py_tp_getset, (void *)element_getsets},
    {Py_tp_methods, (void *)element_methods},
    {Py_sq_length, (void *)elem_sq_length},
    {Py_mp_subscript, (void *)elem_mp_subscript},
    {Py_tp_doc, (void *)"Accelerated Element base type."},
    {0, NULL}
};

static PyType_Slot rodict_slots[] = {
    {Py_mp_ass_subscript, (void *)rodict_ass_subscript},
    {Py_sq_ass_item, (void *)rodict_sq_ass_item},
    {0, NULL}
};

static PyObject *ObjectBases = NULL;

static PyType_Spec rodict_spec = {
    "leptris._leptrisaccel.ReadOnlyDict",
    0,
    0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HEAPTYPE | Py_TPFLAGS_BASETYPE,
    rodict_slots
};

static PyType_Spec element_spec = {
    "leptris._leptrisaccel.Element",
    sizeof(AccelElement),
    0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HEAPTYPE | Py_TPFLAGS_BASETYPE,
    element_slots
};

/* ---- module-level factories ----------------------------------------- */

static PyObject *
accel_create(PyObject *module, PyObject *args)
{
    PyObject *ptr, *document;
    unsigned long long address;
    if (!PyArg_ParseTuple(args, "KOO", &address, &ptr, &document))
        return NULL;
    return element_from_parts_reg(
        (void *)(uintptr_t)address, ptr, document, registry_of(document));
}

static PyObject *
accel_materialize(PyObject *module, PyObject *args)
{
    PyObject *ptrs, *document, *addresses;
    if (!PyArg_ParseTuple(args, "OOO", &ptrs, &document, &addresses))
        return NULL;
    PyObject *fast = PySequence_Fast(ptrs, "ptrs must be a sequence");
    if (fast == NULL)
        return NULL;
    PyObject *fast_addr =
        PySequence_Fast(addresses, "addresses must be a sequence");
    if (fast_addr == NULL) {
        Py_DECREF(fast);
        return NULL;
    }
    int is_list = PyList_Check(fast);
    int addr_is_list = PyList_Check(fast_addr);
    Py_ssize_t count = is_list ? PyList_Size(fast) : PyTuple_Size(fast);
    Py_ssize_t addr_count =
        addr_is_list ? PyList_Size(fast_addr) : PyTuple_Size(fast_addr);
    if (addr_count < count) {
        Py_DECREF(fast_addr);
        Py_DECREF(fast);
        PyErr_SetString(PyExc_ValueError, "addresses shorter than ptrs");
        return NULL;
    }
    PyObject *out = PyList_New(count);
    if (out == NULL) {
        Py_DECREF(fast_addr);
        Py_DECREF(fast);
        return NULL;
    }
    for (Py_ssize_t i = 0; i < count; i++) {
        PyObject *ptr = is_list ? PyList_GetItem(fast, i)
                                : PyTuple_GetItem(fast, i);
        PyObject *addr_obj = addr_is_list ? PyList_GetItem(fast_addr, i)
                                          : PyTuple_GetItem(fast_addr, i);
        void *raw = NULL;
        if (PyLong_Check(addr_obj))
            raw = PyLong_AsVoidPtr(addr_obj);
        AccelElement *el =
            (AccelElement *)PyType_GenericAlloc(ElementType, 0);
        if (el == NULL || PyList_SetItem(out, i, (PyObject *)el) < 0) {
            Py_XDECREF((PyObject *)el);
            Py_DECREF(out);
            Py_DECREF(fast_addr);
            Py_DECREF(fast);
            return NULL;
        }
        el->raw = raw;
        Py_INCREF(ptr);
        el->ptr = ptr;
        Py_INCREF(document);
        el->document = document;
        registry_link(registry_of(document), el);
    }
    Py_DECREF(fast_addr);
    Py_DECREF(fast);
    return out;
}

static PyObject *
accel_bind(PyObject *module, PyObject *args)
{
    PyObject *addresses, *error_class;
    if (!PyArg_ParseTuple(args, "OO", &addresses, &error_class))
        return NULL;
    PyObject *fast = PySequence_Fast(addresses, "addresses must be a sequence");
    if (fast == NULL)
        return NULL;
    Py_ssize_t count = PySequence_Size(fast);
    if (count != FN_COUNT) {
        Py_DECREF(fast);
        PyErr_Format(
            PyExc_ValueError,
            "bind: expected %d function addresses in Fns declaration "
            "order, got %zd", FN_COUNT, count);
        return NULL;
    }
    /* The Fns declaration order IS the protocol. */
    void **slots[] = {
    (void **)&Fns.element_name,
    (void **)&Fns.element_namespace,
    (void **)&Fns.element_attribute,
    (void **)&Fns.element_attribute_ns,
    (void **)&Fns.element_child,
    (void **)&Fns.element_child_count,
    (void **)&Fns.element_as_node,
    (void **)&Fns.node_first_child,
    (void **)&Fns.node_next_sibling,
    (void **)&Fns.node_get_type,
    (void **)&Fns.text_node_get_content,
    (void **)&Fns.cdata_node_get_content,
    (void **)&Fns.element_first_child_any,
    (void **)&Fns.element_prefix_fn,
    (void **)&Fns.element_previous_sibling_any_fn,
    (void **)&Fns.element_first_attribute,
    (void **)&Fns.attribute_next,
    (void **)&Fns.attribute_get_name,
    (void **)&Fns.attribute_get_value,
    (void **)&Fns.element_parent,
    (void **)&Fns.element_next_sibling_any,
    (void **)&Fns.node_line,
    (void **)&Fns.xpath_eval,
    (void **)&Fns.xpath_result_type,
    (void **)&Fns.xpath_result_count,
    (void **)&Fns.xpath_result_get_nodes,
    (void **)&Fns.xpath_result_free,
    (void **)&Fns.xpath_result_number,
    (void **)&Fns.xpath_result_boolean,
    (void **)&Fns.xpath_result_string,
    (void **)&Fns.free_string,
    (void **)&Fns.ns_set_new,
    (void **)&Fns.ns_set_free,
    (void **)&Fns.ns_set_add,
    (void **)&Fns.xpath_eval_ns,
    (void **)&Fns.element_serialize,
    (void **)&Fns.element_serialize_into,
    (void **)&Fns.document_serialize,
    (void **)&Fns.parse_string_fn,
    (void **)&Fns.parse_string_ex,
    (void **)&Fns.parse_file,
    (void **)&Fns.document_root,
    (void **)&Fns.document_free,
    };
    for (Py_ssize_t i = 0; i < FN_COUNT; i++) {
        PyObject *item = PyList_Check(fast)
            ? PyList_GetItem(fast, i)
            : PyTuple_GetItem(fast, i);
        if (!PyLong_Check(item)) {
            Py_DECREF(fast);
            PyErr_SetString(PyExc_TypeError, "addresses must be ints");
            return NULL;
        }
        *slots[i] = PyLong_AsVoidPtr(item);
    }
    Py_DECREF(fast);
    if (error_class != Py_None) {
        Py_XDECREF(LeptrisErrorType);
        Py_INCREF(error_class);
        LeptrisErrorType = error_class;
    }
    bound = 1;
    Py_RETURN_NONE;
}

/* Shared tail of the C evaluation paths: scalars converted, all-
 * element nodesets materialized, anything else -> None (Python path).
 * Consumes result. */
static PyObject *
finish_result(void *result, PyObject *document)
{
    int rtype = Fns.xpath_result_type(result);
    if (rtype != 0) {
        PyObject *scalar = NULL;
        if (rtype == 2)
            scalar = PyFloat_FromDouble(Fns.xpath_result_number(result));
        else if (rtype == 1)
            scalar = PyBool_FromLong(Fns.xpath_result_boolean(result));
        else if (rtype == 3) {
            char *s = Fns.xpath_result_string(result);
            if (s == NULL)
                scalar = PyUnicode_FromString("");
            else {
                scalar = PyUnicode_DecodeUTF8(s, strlen(s), "strict");
                Fns.free_string(s);
            }
        }
        Fns.xpath_result_free(result);
        return scalar;
    }
    size_t count = Fns.xpath_result_count(result);
    if (count == 0) {
        Fns.xpath_result_free(result);
        return PyList_New(0);
    }
    PyObject *out = PyList_New((Py_ssize_t)count);
    if (out == NULL) {
        Fns.xpath_result_free(result);
        return NULL;
    }
    void **elems = (void **)PyMem_Malloc(count * sizeof(void *));
    if (elems == NULL) {
        Py_DECREF(out);
        Fns.xpath_result_free(result);
        return PyErr_NoMemory();
    }
    size_t copied = Fns.xpath_result_get_nodes(result, elems, count);
    Fns.xpath_result_free(result);
    if (copied != count) {
        /* mixed nodeset: hand back to the engine path untouched */
        Py_DECREF(out);
        PyMem_Free(elems);
        Py_RETURN_NONE;
    }
    Registry *reg = registry_of(document);
    for (size_t i = 0; i < copied; i++) {
        PyObject *el = element_from_parts_reg(elems[i], Py_None, document, reg);
        if (el == NULL) {
            Py_DECREF(out);
            PyMem_Free(elems);
            return NULL;
        }
        PyList_SetItem(out, (Py_ssize_t)i, el);
    }
    PyMem_Free(elems);
    return out;
}

static PyObject *
accel_nodeset(PyObject *module, PyObject *args)
{
    PyObject *document_ptr, *context_obj, *expression, *document;
    if (!PyArg_ParseTuple(args, "OOOO", &document_ptr, &context_obj,
                          &expression, &document))
        return NULL;
    if (!bound)
        Py_RETURN_NONE;
    PyObject *encoded = PyUnicode_AsUTF8String(expression);
    if (encoded == NULL)
        return NULL;
    const char *expr = PyBytes_AsString(encoded);
    void *ctx = NULL;
    if (context_obj != Py_None && PyLong_Check(context_obj))
        ctx = PyLong_AsVoidPtr(context_obj);
    if (!PyLong_Check(document_ptr)) {
        Py_DECREF(encoded);
        Py_RETURN_NONE;
    }
    void *doc_raw = PyLong_AsVoidPtr(document_ptr);
    void *result = Fns.xpath_eval(doc_raw, ctx, expr);
    Py_DECREF(encoded);
    if (result == NULL)
        Py_RETURN_NONE;
    return finish_result(result, document);
}

static PyObject *
accel_nodeset_ns(PyObject *module, PyObject *args)
{
    PyObject *document_ptr, *context_obj, *expression, *document, *bindings;
    /* bindings: flat [prefix, uri, prefix, uri, ...] */
    if (!PyArg_ParseTuple(args, "OOOOO", &document_ptr, &context_obj,
                          &expression, &document, &bindings))
        return NULL;
    if (!bound || !PyLong_Check(document_ptr))
        Py_RETURN_NONE;
    PyObject *fast = PySequence_Fast(bindings, "bindings must be a sequence");
    if (fast == NULL)
        return NULL;
    Py_ssize_t n = PySequence_Size(fast);
    void *ns_set = Fns.ns_set_new();
    if (ns_set == NULL) {
        Py_DECREF(fast);
        Py_RETURN_NONE;
    }
    int ok = 1;
    int is_list = PyList_Check(fast);
    for (Py_ssize_t i = 0; i + 1 < n && ok; i += 2) {
        PyObject *prefix = PyUnicode_AsUTF8String(
            is_list ? PyList_GetItem(fast, i) : PyTuple_GetItem(fast, i));
        PyObject *uri = PyUnicode_AsUTF8String(
            is_list ? PyList_GetItem(fast, i + 1)
                    : PyTuple_GetItem(fast, i + 1));
        if (prefix == NULL || uri == NULL) {
            Py_XDECREF(prefix);
            Py_XDECREF(uri);
            ok = 0;
            break;
        }
        if (Fns.ns_set_add(ns_set, PyBytes_AsString(prefix),
                           PyBytes_AsString(uri)) != 0)
            ok = 0;
        Py_DECREF(prefix);
        Py_DECREF(uri);
    }
    Py_DECREF(fast);
    if (!ok) {
        Fns.ns_set_free(ns_set);
        Py_RETURN_NONE;
    }
    PyObject *encoded = PyUnicode_AsUTF8String(expression);
    if (encoded == NULL) {
        Fns.ns_set_free(ns_set);
        return NULL;
    }
    void *ctx = NULL;
    if (context_obj != Py_None && PyLong_Check(context_obj))
        ctx = PyLong_AsVoidPtr(context_obj);
    void *doc_raw = PyLong_AsVoidPtr(document_ptr);
    void *result = Fns.xpath_eval_ns(
        doc_raw, ctx, PyBytes_AsString(encoded), ns_set);
    Py_DECREF(encoded);
    Fns.ns_set_free(ns_set);
    if (result == NULL)
        Py_RETURN_NONE;
    return finish_result(result, document);
}

static PyObject *
accel_serialize_elem(PyObject *module, PyObject *args)
{
    unsigned long long address;
    int indent, declaration;
    if (!PyArg_ParseTuple(args, "Kii", &address, &indent, &declaration))
        return NULL;
    if (!bound)
        Py_RETURN_NONE;
    /* The engine's non-NULL options path is measurably slower even
     * for defaults - pass NULL unless something is requested. */
    void *options = NULL;
    struct { int indent; int xml_declaration; const char *encoding; } opts;
    static const char utf8[] = "UTF-8";
    if (indent != 0 || declaration != 0) {
        opts.indent = indent;
        opts.xml_declaration = declaration;
        /* the engine emits the declaration only with an encoding set */
        opts.encoding = (declaration != 0) ? utf8 : NULL;
        options = &opts;
    }
    if (Fns.element_serialize_into == NULL)
        Py_RETURN_NONE;
    /* 1.9.0: _into takes the options pointer directly - no
     * allocating fallback needed. */
    size_t needed = Fns.element_serialize_into(
        (void *)(uintptr_t)address, NULL, 0, NULL, options);
    if (needed == 0)
        Py_RETURN_NONE;
    PyObject *bytes = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)(needed - 1));
    if (bytes == NULL)
        return NULL;
    size_t written = 0;
    Fns.element_serialize_into((void *)(uintptr_t)address,
                               PyBytes_AsString(bytes), needed, &written,
                               options);
    return bytes;
}

/* First element child whose name matches, via the element sibling
 * chain (no XPath). Sentinel: None -> not found; needs the document
 * object to attach ownership. */
static PyObject *
accel_find_first(PyObject *module, PyObject *args)
{
    unsigned long long address;
    PyObject *name, *document;
    if (!PyArg_ParseTuple(args, "KUO", &address, &name, &document))
        return NULL;
    if (!bound)
        Py_RETURN_NONE;
    PyObject *encoded = PyUnicode_AsUTF8String(name);
    if (encoded == NULL)
        return NULL;
    const char *want = PyBytes_AsString(encoded);
    size_t want_len = strlen(want);
    void *child = Fns.element_first_child_any((void *)(uintptr_t)address);
    while (child != NULL) {
        const char *candidate = Fns.element_name(child);
        if (candidate != NULL && strcmp(candidate, want) == 0
            && strlen(candidate) == want_len) {
            Py_DECREF(encoded);
            return element_from_parts_reg(
                child, Py_None, document, registry_of(document));
        }
        child = Fns.element_next_sibling_any(child);
    }
    Py_DECREF(encoded);
    Py_RETURN_NONE;
}

static PyObject *make_registry_capsule(void);

static PyObject *
accel_new_registry(PyObject *module, PyObject *unused)
{
    return make_registry_capsule();
}

static PyObject *
accel_invalidate(PyObject *module, PyObject *capsule)
{
    if (!PyCapsule_CheckExact(capsule)) {
        PyErr_SetString(PyExc_TypeError, "expected a registry capsule");
        return NULL;
    }
    Registry *reg =
        (Registry *)PyCapsule_GetPointer(capsule, "leptris.registry");
    if (reg == NULL)
        return NULL;
    AccelElement *el = reg->first;
    while (el != NULL) {
        AccelElement *next = el->next;
        el->raw = ACCEL_RAW_INVALID;
        PyObject *tmp = el->ptr;
        Py_INCREF(Py_None);
        el->ptr = Py_None;
        Py_XDECREF(tmp);
        /* unlink as we walk so late deaths stay cheap */
        el->prev = NULL;
        el->next = NULL;
        el->registry = NULL;
        el = next;
    }
    reg->first = NULL;
    reg->last = NULL;
    Py_RETURN_NONE;
}

/* ---- subtree cursor: a walk, not a query ---------------------------- */

typedef struct {
    PyObject_HEAD
    AccelElement *start;      /* strong ref: keeps the document alive
                                 and its poison flag signals close() */
    void *top;                /* raw pointer of the subtree root */
    void *current;            /* next candidate, NULL when exhausted */
    PyObject *document;       /* strong ref */
    Registry *registry;
    PyObject *local_bytes;    /* NULL = match every element */
    PyObject *ns_bytes;       /* namespace filter (see want_ns) */
    const char *local_c;      /* borrowed from local_bytes */
    const char *ns_c;         /* borrowed from ns_bytes */
    int want_ns;              /* 1: ns must equal ns_c; 0: ns must
                                 be absent (unprefixed name test) */
} AccelCursor;

static PyTypeObject *CursorType;

static void *
cursor_successor(AccelCursor *c, void *el)
{
    void *child = Fns.element_first_child_any(el);
    if (child != NULL)
        return child;
    while (el != c->top) {
        void *sib = Fns.element_next_sibling_any(el);
        if (sib != NULL)
            return sib;
        el = Fns.element_parent(el);
        if (el == NULL)
            return NULL;
    }
    return NULL;
}

static int
cursor_matches(AccelCursor *c, void *el)
{
    if (c->local_bytes == NULL)
        return 1;
    const char *name = Fns.element_name(el);
    if (name == NULL || strcmp(name, c->local_c) != 0)
        return 0;
    const char *ns = Fns.element_namespace(el);
    if (c->want_ns)
        return ns != NULL && strcmp(ns, c->ns_c) == 0;
    return ns == NULL;
}

static PyObject *
cursor_next(AccelCursor *self)
{
    if (self->start->raw == ACCEL_RAW_INVALID) {
        PyErr_SetString(LeptrisErrorType, "operation on a closed document");
        return NULL;
    }
    while (self->current != NULL) {
        void *el = self->current;
        self->current = cursor_successor(self, el);
        if (cursor_matches(self, el))
            return element_from_parts_reg(
                el, Py_None, self->document, self->registry);
    }
    return NULL; /* StopIteration */
}

static PyObject *
cursor_self(AccelCursor *self)
{
    Py_INCREF(self);
    return (PyObject *)self;
}

static void
cursor_dealloc(AccelCursor *self)
{
    Py_XDECREF(self->start);
    Py_XDECREF(self->document);
    Py_XDECREF(self->local_bytes);
    Py_XDECREF(self->ns_bytes);
    PyObject_Free(self);
}

static PyObject *
cursor_repr(AccelCursor *self)
{
    return PyUnicode_FromFormat(
        "<leptris.SubtreeIterator object at %p>", (void *)self);
}

static PyType_Slot cursor_slots[] = {
    {Py_tp_iter, (void *)cursor_self},
    {Py_tp_iternext, (void *)cursor_next},
    {Py_tp_dealloc, (void *)cursor_dealloc},
    {Py_tp_repr, (void *)cursor_repr},
    {Py_tp_doc, (void *)"Document-order element cursor over a subtree."},
    {0, NULL}
};

static PyType_Spec cursor_spec = {
    "leptris._leptrisaccel.SubtreeIterator",
    sizeof(AccelCursor),
    0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HEAPTYPE,
    cursor_slots
};

/* subtree_iter(element, include_self, ns | None, local | None) */
static PyObject *
accel_subtree_iter(PyObject *module, PyObject *args)
{
    PyObject *start, *ns, *local;
    int include_self;
    if (!PyArg_ParseTuple(args, "O!pOO",
                          ElementType, &start, &include_self, &ns, &local))
        return NULL;
    if (!bound) {
        PyErr_SetString(LeptrisErrorType, "accelerator is not bound");
        return NULL;
    }
    AccelElement *el = (AccelElement *)start;
    if (check_poisoned(el) < 0)
        return NULL;
    AccelCursor *c = (AccelCursor *)PyType_GenericAlloc(CursorType, 0);
    if (c == NULL)
        return NULL;
    c->top = el->raw;
    c->current = include_self ? el->raw : cursor_successor(c, el->raw);
    Py_INCREF(start);
    c->start = el;
    Py_INCREF(el->document);
    c->document = el->document;
    c->registry = registry_of(el->document);
    c->want_ns = (ns != Py_None);
    if (local != Py_None) {
        c->local_bytes = PyUnicode_AsUTF8String(local);
        if (c->local_bytes == NULL) {
            Py_DECREF(c);
            return NULL;
        }
        c->local_c = PyBytes_AsString(c->local_bytes);
    }
    if (c->want_ns) {
        c->ns_bytes = PyUnicode_AsUTF8String(ns);
        if (c->ns_bytes == NULL) {
            Py_DECREF(c);
            return NULL;
        }
        c->ns_c = PyBytes_AsString(c->ns_bytes);
    }
    return (PyObject *)c;
}

/* children(element) -> presized list of element children */
static PyObject *
accel_children(PyObject *module, PyObject *element)
{
    if (!PyObject_TypeCheck(element, ElementType)) {
        PyErr_SetString(PyExc_TypeError, "expected an Element");
        return NULL;
    }
    AccelElement *self = (AccelElement *)element;
    if (check_poisoned(self) < 0)
        return NULL;
    if (!bound || self->raw == NULL)
        return PyList_New(0);
    size_t count = Fns.element_child_count(self->raw);
    PyObject *out = PyList_New((Py_ssize_t)count);
    if (out == NULL)
        return NULL;
    Registry *reg = registry_of(self->document);
    void *child = Fns.element_first_child_any(self->raw);
    for (size_t i = 0; i < count && child != NULL; i++) {
        PyObject *item = element_from_parts_reg(
            child, Py_None, self->document, reg);
        if (item == NULL) {
            Py_DECREF(out);
            return NULL;
        }
        PyList_SetItem(out, (Py_ssize_t)i, item);
        child = Fns.element_next_sibling_any(child);
    }
    return out;
}

/* serialize_doc(document_address) -> bytes (default options) */
static PyObject *
accel_serialize_doc(PyObject *module, PyObject *args)
{
    unsigned long long address;
    if (!PyArg_ParseTuple(args, "K", &address))
        return NULL;
    if (!bound)
        Py_RETURN_NONE;
    char *data = Fns.document_serialize((void *)(uintptr_t)address, NULL);
    if (data == NULL) {
        PyErr_SetString(LeptrisErrorType, "serialization failed");
        return NULL;
    }
    PyObject *out = PyBytes_FromStringAndSize(data, strlen(data));
    Fns.free_string(data);
    return out;
}

/* ---- document parse/registry seam ---------------------------------- */

/* LeptrisParseOptions layout (types.h): flags, strict_mode, max_depth,
 * recover — four ints. */
typedef struct { int flags; int strict_mode; int max_depth; int recover; }
    CParseOptions;

static PyObject *
make_registry_capsule(void)
{
    Registry *reg = (Registry *)PyMem_Malloc(sizeof(Registry));
    if (reg == NULL) {
        PyErr_NoMemory();
        return NULL;
    }
    reg->first = NULL;
    reg->last = NULL;
    PyObject *capsule =
        PyCapsule_New(reg, "leptris.registry", registry_capsule_free);
    if (capsule == NULL) {
        PyMem_Free(reg);
        return NULL;
    }
    return capsule;
}

/* parse(data, recover) -> (address | None, registry | None,
 * status). "y#p" hands the bytes buffer straight to C
 * (PyBytes_AsStringAndSize is in the stable ABI); the engine copies,
 * so the buffer is only read during the call. parse_string_inplace
 * was measured 8-40% slower than parse_string at every scale on
 * 1.9.0, despite the header's "3-5x faster" claim (leptris#561). */
static PyObject *
accel_parse(PyObject *module, PyObject *args)
{
    const char *data;
    Py_ssize_t length;
    int recover;
    if (!PyArg_ParseTuple(args, "y#p", &data, &length, &recover))
        return NULL;
    if (!bound) {
        PyErr_SetString(LeptrisErrorType, "accelerator is not bound");
        return NULL;
    }
    int status = 0;
    void *doc;
    if (recover) {
        CParseOptions opts = {0, -1, 0, 1};
        doc = Fns.parse_string_ex(data, (size_t)length, &opts, &status);
    } else {
        doc = Fns.parse_string_fn(data, (size_t)length, &status);
    }
    if (doc == NULL)
        return Py_BuildValue("(OOi)", Py_None, Py_None, status);
    Fns.document_root(doc); /* promote flat-path documents (#550) */
    PyObject *registry = make_registry_capsule();
    if (registry == NULL)
        return NULL;
    return Py_BuildValue("(NOi)", PyLong_FromVoidPtr(doc), registry, status);
}

/* parse_file(path_bytes) -> (address | None, registry | None, status) */
static PyObject *
accel_parse_file(PyObject *module, PyObject *args)
{
    const char *path;
    Py_ssize_t length;
    if (!PyArg_ParseTuple(args, "y#", &path, &length))
        return NULL;
    if (!bound) {
        PyErr_SetString(LeptrisErrorType, "accelerator is not bound");
        return NULL;
    }
    int status = 0;
    void *doc = Fns.parse_file(path, &status);
    if (doc == NULL)
        return Py_BuildValue("(OOi)", Py_None, Py_None, status);
    Fns.document_root(doc);
    PyObject *registry = make_registry_capsule();
    if (registry == NULL)
        return NULL;
    return Py_BuildValue("(NOi)", PyLong_FromVoidPtr(doc), registry, status);
}

/* close_document(address) -> None */
static PyObject *
accel_close_document(PyObject *module, PyObject *args)
{
    unsigned long long address;
    if (!PyArg_ParseTuple(args, "K", &address))
        return NULL;
    if (bound)
        Fns.document_free((void *)(uintptr_t)address);
    Py_RETURN_NONE;
}

/* document_root(address, document) -> Element | None */
static PyObject *
accel_document_root(PyObject *module, PyObject *args)
{
    unsigned long long address;
    PyObject *document;
    if (!PyArg_ParseTuple(args, "KO", &address, &document))
        return NULL;
    if (!bound)
        Py_RETURN_NONE;
    void *root = Fns.document_root((void *)(uintptr_t)address);
    if (root == NULL)
        Py_RETURN_NONE;
    return element_from_parts_reg(
        root, Py_None, document, registry_of(document));
}

static PyMethodDef accel_methods[] = {
    {"create", accel_create, METH_VARARGS,
     "create(address, ptr, document) -> Element"},
    {"materialize", accel_materialize, METH_VARARGS,
     "materialize(ptrs, document, addresses) -> list[Element]"},
    {"bind", accel_bind, METH_VARARGS,
     "bind(addresses_in_Fns_order, error_class) -> None"},
    {"nodeset", accel_nodeset, METH_VARARGS,
     "nodeset(document_address, context_address, expression, document) -> list | scalar | None"},
    {"nodeset_ns", accel_nodeset_ns, METH_VARARGS,
     "nodeset_ns(document_address, context_address, expression, document, bindings) -> list | scalar | None"},
    {"find_first", accel_find_first, METH_VARARGS,
     "find_first(address, name, document) -> Element | None"},
    {"serialize_elem", accel_serialize_elem, METH_VARARGS,
     "serialize_elem(address, indent, declaration) -> bytes | None"},
    {"parse", accel_parse, METH_VARARGS,
     "parse(data, recover) -> (address|None, registry|None, status)"},
    {"parse_file", accel_parse_file, METH_VARARGS,
     "parse_file(path_bytes) -> (address|None, registry|None, status)"},
    {"close_document", accel_close_document, METH_VARARGS,
     "close_document(address) -> None"},
    {"document_root", accel_document_root, METH_VARARGS,
     "document_root(address, document) -> Element | None"},
    {"subtree_iter", accel_subtree_iter, METH_VARARGS,
     "subtree_iter(element, include_self, ns, local) -> SubtreeIterator"},
    {"children", (PyCFunction)accel_children, METH_O,
     "children(element) -> list[Element]"},
    {"serialize_doc", accel_serialize_doc, METH_VARARGS,
     "serialize_doc(document_address) -> bytes | None"},
    {"new_registry", (PyCFunction)accel_new_registry, METH_NOARGS,
     "new_registry() -> capsule tracking live elements of a document"},
    {"invalidate", (PyCFunction)accel_invalidate, METH_O,
     "invalidate(capsule) -> poison all tracked elements (document closed)"},
    {NULL}
};

static struct PyModuleDef accel_module = {
    PyModuleDef_HEAD_INIT,
    "leptris._leptrisaccel",
    "C-accelerated Element allocation and accessors for leptris.",
    -1,
    accel_methods,
};

PyMODINIT_FUNC
PyInit__leptrisaccel(void)
{
    PyObject *module = PyModule_Create(&accel_module);
    if (module == NULL)
        return NULL;
    ObjectBases = PyTuple_Pack(1, (PyObject *)&PyDict_Type);
    if (ObjectBases == NULL) {
        Py_DECREF(module);
        return NULL;
    }
    ReadOnlyDictType = (PyTypeObject *)PyType_FromSpecWithBases(
        &rodict_spec, ObjectBases);
    if (ReadOnlyDictType == NULL) {
        Py_DECREF(module);
        return NULL;
    }
    ElementType = (PyTypeObject *)PyType_FromSpec(&element_spec);
    if (ElementType == NULL) {
        Py_DECREF(module);
        return NULL;
    }
    if (PyModule_AddObject(module, "Element", (PyObject *)ElementType) < 0) {
        Py_DECREF(ElementType);
        Py_DECREF(module);
        return NULL;
    }
    CursorType = (PyTypeObject *)PyType_FromSpec(&cursor_spec);
    if (CursorType == NULL) {
        Py_DECREF(module);
        return NULL;
    }
    if (PyModule_AddObject(module, "SubtreeIterator",
                           (PyObject *)CursorType) < 0) {
        Py_DECREF(CursorType);
        Py_DECREF(module);
        return NULL;
    }
    return module;
}
