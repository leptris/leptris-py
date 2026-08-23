/* Accelerated Element allocation for leptris.
 *
 * Element instances are allocated here, in C, while the entire API
 * surface stays in Python: leptris/element.py attaches its methods
 * onto this heap type after import. Fields hold the cffi cdata
 * handle and the owning Document, so pure-Python call sites are
 * unchanged.
 *
 * Built against the limited API (abi3) so one wheel per platform
 * serves every supported CPython. When the extension is unavailable
 * (no compiler at install time) leptris.element falls back to an
 * equivalent pure-Python class.
 */

#define PY_SSIZE_T_CLEAN
#define Py_LIMITED_API 0x03090000
#include <Python.h>

typedef struct {
    PyObject_HEAD
    PyObject *ptr;       /* cffi cdata for the LeptrisElement handle */
    PyObject *document;  /* owning Document (strong reference) */
} AccelElement;

static PyTypeObject *ElementType;

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

static PyGetSetDef element_getsets[] = {
    {"_ptr", (getter)elem_get_ptr, (setter)elem_set_ptr,
     "cffi handle for the wrapped LeptrisElement.", NULL},
    {"_document", (getter)elem_get_document, (setter)elem_set_document,
     "Owning Document.", NULL},
    {NULL}
};

static void
element_dealloc(AccelElement *self)
{
    Py_XDECREF(self->ptr);
    Py_XDECREF(self->document);
    PyObject_Free(self);
}

static PyType_Slot element_slots[] = {
    {Py_tp_dealloc, (void *)element_dealloc},
    {Py_tp_getset, (void *)element_getsets},
    {Py_tp_doc, (void *)"Accelerated Element base type."},
    {0, NULL}
};

static PyType_Spec element_spec = {
    "leptris._leptrisaccel.Element",
    sizeof(AccelElement),
    0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HEAPTYPE | Py_TPFLAGS_BASETYPE,
    element_slots
};

static PyObject *
accel_create(PyObject *module, PyObject *args)
{
    PyObject *ptr, *document;
    if (!PyArg_ParseTuple(args, "OO", &ptr, &document))
        return NULL;
    AccelElement *el = (AccelElement *)PyType_GenericAlloc(ElementType, 0);
    if (el == NULL)
        return NULL;
    Py_INCREF(ptr);
    el->ptr = ptr;
    Py_INCREF(document);
    el->document = document;
    return (PyObject *)el;
}

static PyObject *
accel_materialize(PyObject *module, PyObject *args)
{
    PyObject *sequence, *document;
    if (!PyArg_ParseTuple(args, "OO", &sequence, &document))
        return NULL;
    PyObject *fast = PySequence_Fast(sequence, "ptrs must be a sequence");
    if (fast == NULL)
        return NULL;
    int is_list = PyList_Check(fast);
    Py_ssize_t count = is_list ? PyList_Size(fast) : PyTuple_Size(fast);
    PyObject *out = PyList_New(count);
    if (out == NULL) {
        Py_DECREF(fast);
        return NULL;
    }
    for (Py_ssize_t i = 0; i < count; i++) {
        PyObject *ptr = is_list ? PyList_GetItem(fast, i)
                                : PyTuple_GetItem(fast, i);
        AccelElement *el = (AccelElement *)PyType_GenericAlloc(ElementType, 0);
        if (el == NULL) {
            Py_DECREF(out);
            Py_DECREF(fast);
            return NULL;
        }
        Py_INCREF(ptr);
        el->ptr = ptr;
        Py_INCREF(document);
        el->document = document;
        if (PyList_SetItem(out, i, (PyObject *)el) < 0) {
            Py_DECREF(el);
            Py_DECREF(out);
            Py_DECREF(fast);
            return NULL;
        }
    }
    Py_DECREF(fast);
    return out;
}

static PyMethodDef accel_methods[] = {
    {"create", accel_create, METH_VARARGS,
     "create(ptr, document) -> Element"},
    {"materialize", accel_materialize, METH_VARARGS,
     "materialize(ptrs, document) -> list[Element]"},
    {NULL}
};

static struct PyModuleDef accel_module = {
    PyModuleDef_HEAD_INIT,
    "leptris._leptrisaccel",
    "C-accelerated Element allocation for leptris.",
    -1,
    accel_methods,
};

PyMODINIT_FUNC
PyInit__leptrisaccel(void)
{
    PyObject *module = PyModule_Create(&accel_module);
    if (module == NULL)
        return NULL;
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
