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
    void *(*element_child)(void *, size_t);
    size_t (*element_child_count)(void *);
    void *(*element_as_node)(void *);
    void *(*node_first_child)(void *);
    void *(*node_next_sibling)(void *);
    int (*node_get_type)(void *);
    const char *(*text_node_get_content)(void *);
    const char *(*cdata_node_get_content)(void *);
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
} Fns;

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
    const char *value = Fns.element_attribute(self->raw, utf8);
    Py_DECREF(encoded);
    if (value == NULL) {
        Py_INCREF(default_value);
        return default_value;
    }
    return PyUnicode_DecodeUTF8(value, strlen(value), "strict");
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
    {NULL}
};

static PyMethodDef element_methods[] = {
    {"getparent", (PyCFunction)elem_getparent, METH_NOARGS,
     "Parent element or None."},
    {"getnext", (PyCFunction)elem_getnext, METH_NOARGS,
     "Next element sibling or None."},
    {"get", (PyCFunction)elem_get_method, METH_VARARGS,
     "get(name, default=None) -> attribute value."},
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
accel_bind(PyObject *module, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = {
        "element_name", "element_namespace", "element_attribute",
        "element_child", "element_child_count", "element_as_node",
        "node_first_child", "node_next_sibling", "node_get_type",
        "text_node_get_content", "cdata_node_get_content", "element_first_attribute",
        "attribute_next", "attribute_get_name", "attribute_get_value",
        "element_parent", "element_next_sibling_any", "node_line",
        "xpath_eval", "xpath_result_type", "xpath_result_count",
        "xpath_result_get_nodes", "xpath_result_free", "xpath_result_number",
        "xpath_result_boolean", "xpath_result_string", "free_string",
        "error_class", NULL};
                PyObject *value_element_name = NULL, *value_element_namespace = NULL,
             *value_element_attribute = NULL, *value_element_child = NULL,
             *value_element_child_count = NULL, *value_element_as_node = NULL,
             *value_node_first_child = NULL, *value_node_next_sibling = NULL,
             *value_node_get_type = NULL, *value_text_node_get_content = NULL,
             *value_cdata_node_get_content = NULL, *value_element_first_attribute = NULL,
             *value_attribute_next = NULL, *value_attribute_get_name = NULL,
             *value_attribute_get_value = NULL, *value_element_parent = NULL,
             *value_element_next_sibling_any = NULL, *value_node_line = NULL,
             *value_xpath_eval = NULL, *value_xpath_result_type = NULL,
             *value_xpath_result_count = NULL, *value_xpath_result_get_nodes = NULL,
             *value_xpath_result_free = NULL, *value_xpath_result_number = NULL,
             *value_xpath_result_boolean = NULL, *value_xpath_result_string = NULL,
             *value_free_string = NULL, *value_error_class = NULL;
    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "|$OOOOOOOOOOOOOOOOOOOOOOOOOOOO", kwlist,
&value_element_name,
&value_element_namespace,
&value_element_attribute,
&value_element_child,
&value_element_child_count,
&value_element_as_node,
&value_node_first_child,
&value_node_next_sibling,
&value_node_get_type,
&value_text_node_get_content,
&value_cdata_node_get_content,
&value_element_first_attribute,
&value_attribute_next,
&value_attribute_get_name,
&value_attribute_get_value,
&value_element_parent,
&value_element_next_sibling_any,
&value_node_line,
&value_xpath_eval,
&value_xpath_result_type,
&value_xpath_result_count,
&value_xpath_result_get_nodes,
&value_xpath_result_free,
&value_xpath_result_number,
&value_xpath_result_boolean,
&value_xpath_result_string,
&value_free_string,
            &value_error_class))
        return NULL;
#define BIND_FN(name) \
    if (value_##name != NULL && value_##name != Py_None) { \
        unsigned long long addr = PyLong_AsUnsignedLongLong(value_##name); \
        if (PyErr_Occurred()) return NULL; \
        Fns.name = (__typeof__(Fns.name))(uintptr_t)addr; \
    }
    BIND_FN(element_name)
    BIND_FN(element_namespace)
    BIND_FN(element_attribute)
    BIND_FN(element_child)
    BIND_FN(element_child_count)
    BIND_FN(element_as_node)
    BIND_FN(node_first_child)
    BIND_FN(node_next_sibling)
    BIND_FN(node_get_type)
    BIND_FN(text_node_get_content)
    BIND_FN(cdata_node_get_content)
    BIND_FN(element_first_attribute)
    BIND_FN(attribute_next)
    BIND_FN(attribute_get_name)
    BIND_FN(attribute_get_value)
    BIND_FN(element_parent)
    BIND_FN(element_next_sibling_any)
    BIND_FN(node_line)
    BIND_FN(xpath_eval)
    BIND_FN(xpath_result_type)
    BIND_FN(xpath_result_count)
    BIND_FN(xpath_result_get_nodes)
    BIND_FN(xpath_result_free)
    BIND_FN(xpath_result_number)
    BIND_FN(xpath_result_boolean)
    BIND_FN(xpath_result_string)
    BIND_FN(free_string)
#undef BIND_FN
    if (value_error_class != NULL && value_error_class != Py_None) {
        Py_XDECREF(LeptrisErrorType);
        Py_INCREF(value_error_class);
        LeptrisErrorType = value_error_class;
    }
    bound = 1;
    Py_RETURN_NONE;
}

static PyObject *
accel_nodeset(PyObject *module, PyObject *args)
{
    PyObject *document_ptr;   /* cffi LeptrisDocument handle */
    PyObject *context_obj;    /* raw context address int or None */
    PyObject *expression;     /* str */
    PyObject *document;       /* owning Document object */
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
    /* document raw address: take it from the cdata via Python-provided
     * int in document_ptr if it is an int, else bail to slow path */
    if (!PyLong_Check(document_ptr)) {
        Py_DECREF(encoded);
        Py_RETURN_NONE;
    }
    void *doc_raw = PyLong_AsVoidPtr(document_ptr);
    void *result = Fns.xpath_eval(doc_raw, ctx, expr);
    Py_DECREF(encoded);
    if (result == NULL)
        Py_RETURN_NONE; /* evaluation failed: Python path raises */
    if (Fns.xpath_result_type(result) != 0) {
        /* scalar (boolean/number/string): the Python path converts */
        Fns.xpath_result_free(result);
        Py_RETURN_NONE;
    }
    size_t count = Fns.xpath_result_count(result);
    PyObject *out = PyList_New(0);
    if (out == NULL) {
        Fns.xpath_result_free(result);
        return NULL;
    }
    if (count == 0) {
        Fns.xpath_result_free(result);
        return out;
    }
    void **elems = (void **)PyMem_Malloc(count * sizeof(void *));
    if (elems == NULL) {
        Py_DECREF(out);
        Fns.xpath_result_free(result);
        return PyErr_NoMemory();
    }
    size_t copied = Fns.xpath_result_get_nodes(result, elems, count);
    Fns.xpath_result_free(result);
    Registry *reg = registry_of(document);
    for (size_t i = 0; i < copied; i++) {
        PyObject *el = element_from_parts_reg(elems[i], Py_None, document, reg);
        if (el == NULL || PyList_Append(out, el) < 0) {
            Py_XDECREF(el);
            Py_DECREF(out);
            PyMem_Free(elems);
            return NULL;
        }
        Py_DECREF(el);
    }
    PyMem_Free(elems);
    if (copied != count) {
        /* mixed nodeset: the Python path handles non-element slots */
        Py_DECREF(out);
        Py_RETURN_NONE;
    }
    return out;
}

static PyObject *
accel_new_registry(PyObject *module, PyObject *unused)
{
    Registry *reg = (Registry *)PyMem_Malloc(sizeof(Registry));
    if (reg == NULL)
        return PyErr_NoMemory();
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

static PyMethodDef accel_methods[] = {
    {"create", accel_create, METH_VARARGS,
     "create(address, ptr, document) -> Element"},
    {"materialize", accel_materialize, METH_VARARGS,
     "materialize(ptrs, document, addresses) -> list[Element]"},
    {"bind", (PyCFunction)accel_bind, METH_VARARGS | METH_KEYWORDS,
     "bind(**fn_addresses) -> None"},
    {"nodeset", accel_nodeset, METH_VARARGS,
     "nodeset(document_address, context_address, expression, document) -> list | None"},
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
    return module;
}
