"""C bridge for leptris.

cffi ABI mode: the cdef below mirrors the public headers
(src/include/leptris/ plus the leptris.h umbrella). All handles are
opaque pointers; strings returned by accessors are document-owned and
only valid until leptris_document_free — copy into Python str at the
boundary.

The library is resolved from LEPTRIS_LIB_PATH, then the usual
install names, then the local build directory.
"""

import os

from cffi import FFI

ffi = FFI()

ffi.cdef(
    """
    typedef int LeptrisStatus;

    typedef struct leptris_document* LeptrisDocument;
    typedef struct leptris_element*  LeptrisElement;
    typedef struct leptris_node*     LeptrisNodeRef;
    typedef struct leptris_attribute* LeptrisAttribute;
    typedef struct leptris_sax_recorder* LeptrisSaxRecorder;
    typedef struct leptris_xpath_result* LeptrisXPathResult;
    typedef struct leptris_xpath_variable_set* LeptrisXPathVariableSet;
    typedef struct leptris_xpath_ns_map* LeptrisXPathNsSet;

    typedef struct {
        int indent;
        int xml_declaration;
        const char* encoding;
    } LeptrisSerializeOptions;

    typedef struct LeptrisSAXParser LeptrisSAXParser;
    typedef struct {
        void (*start_document)(void* user_data);
        void (*end_document)(void* user_data);
        void (*start_element)(void* user_data, const char* name, const char** attrs);
        void (*end_element)(void* user_data, const char* name);
        void (*characters)(void* user_data, const char* text, size_t len);
        void (*comment)(void* user_data, const char* comment);
        void (*cdata)(void* user_data, const char* cdata);
        void (*processing_instruction)(void* user_data, const char* target, const char* data);
        void (*start_prefix_mapping)(void* user_data, const char* prefix, const char* uri);
        void (*end_prefix_mapping)(void* user_data, const char* prefix);
        void (*error)(void* user_data, const char* message, int line, int column);
    } LeptrisSAXHandler;

    LeptrisDocument leptris_parse_string(const char* xml, size_t len, int* status);
    LeptrisDocument leptris_parse_string_inplace(char* xml, size_t len, int* status);
    LeptrisDocument leptris_parse_file(const char* filepath, int* status);
    void           leptris_document_free(LeptrisDocument doc);
    LeptrisElement  leptris_document_root(LeptrisDocument doc);
    char*          leptris_document_serialize(LeptrisDocument doc, LeptrisSerializeOptions* options);
    int            leptris_xinclude_process(LeptrisDocument doc, const char* base_path);
    int            leptris_document_save_file(LeptrisDocument doc, const char* filepath, LeptrisSerializeOptions* options);

    int    leptris_node_get_type(LeptrisNodeRef node);
    LeptrisNodeRef leptris_node_first_child(LeptrisNodeRef node);
    LeptrisNodeRef leptris_node_next_sibling(LeptrisNodeRef node);
    LeptrisNodeRef leptris_node_previous_sibling(LeptrisNodeRef node);
    size_t leptris_node_child_count(LeptrisNodeRef node);
    size_t leptris_node_children(LeptrisNodeRef parent, LeptrisNodeRef* out_nodes, size_t max_count);
    const char* leptris_element_attribute_ns(LeptrisElement elem, const char* uri, const char* local);
    int leptris_element_has_attribute_ns(LeptrisElement elem, const char* uri, const char* local);
    typedef struct {
        int flags;
        int strict_mode;
        int max_depth;
        int recover;
    } LeptrisParseOptions;
    LeptrisDocument leptris_parse_string_ex(const char* xml, size_t length, const LeptrisParseOptions* options, int* status);
    const char* leptris_attribute_prefix(LeptrisAttribute attr);
    const char* leptris_attribute_namespace_uri(LeptrisAttribute attr);
    size_t leptris_document_pi_count(LeptrisDocument doc);
    const char* leptris_document_pi_target(LeptrisDocument doc, size_t index);
    const char* leptris_document_pi_data(LeptrisDocument doc, size_t index);
    LeptrisNodeRef leptris_document_add_pi(LeptrisDocument doc, const char* target, const char* data);
    LeptrisNodeRef leptris_document_node(LeptrisDocument doc);
    size_t leptris_document_comment_count(LeptrisDocument doc);
    const char* leptris_document_comment_content(LeptrisDocument doc, size_t index);
    size_t leptris_document_serialize_into(LeptrisDocument doc, char* buf, size_t capacity, size_t* out_len, const LeptrisSerializeOptions* options);
    size_t leptris_element_serialize_into(LeptrisElement elem, char* buf, size_t capacity, size_t* out_len, const LeptrisSerializeOptions* options);
    LeptrisElement  leptris_node_as_element(LeptrisNodeRef node);
    LeptrisNodeRef  leptris_element_as_node(LeptrisElement elem);

    const char* leptris_element_name(LeptrisElement elem);
    const char* leptris_element_text(LeptrisElement elem);
    const char* leptris_element_prefix(LeptrisElement elem);
    const char* leptris_element_namespace(LeptrisElement elem);
    LeptrisElement leptris_element_child(LeptrisElement elem, size_t index);
    LeptrisElement leptris_element_first_child_any(LeptrisElement elem);
    LeptrisElement leptris_element_parent(LeptrisElement elem);
    const char* leptris_element_attribute(LeptrisElement elem, const char* name);
    LeptrisElement leptris_element_next_sibling_any(LeptrisElement elem);
    LeptrisElement leptris_element_previous_sibling_any(LeptrisElement elem);
    LeptrisAttribute leptris_element_first_attribute(LeptrisElement elem);
    LeptrisAttribute leptris_attribute_next(LeptrisAttribute attr);
    const char* leptris_attribute_get_name(LeptrisAttribute attr);
    const char* leptris_attribute_get_value(LeptrisElement elem, LeptrisAttribute attr);
    size_t leptris_element_attribute_count(LeptrisElement elem);
    size_t leptris_element_child_count(LeptrisElement elem);
    size_t leptris_element_children(LeptrisElement elem, LeptrisElement* out_children, size_t max_count);
    int    leptris_node_line(LeptrisNodeRef node);
    char* leptris_element_serialize(LeptrisElement elem, LeptrisSerializeOptions* options);

    const char* leptris_text_node_get_content(LeptrisNodeRef node);
    const char* leptris_comment_node_get_content(LeptrisNodeRef node);
    const char* leptris_cdata_node_get_content(LeptrisNodeRef node);
    const char* leptris_pi_node_get_target(LeptrisNodeRef node);
    const char* leptris_pi_node_get_data(LeptrisNodeRef node);

    char* leptris_c14n_canonicalize(LeptrisDocument doc, int version, int flags);
    char* leptris_c14n_canonicalize_ex(LeptrisDocument doc, int version, int mode, const char** inclusive_ns_prefixes, int with_comments);
    char* leptris_c14n_canonicalize_subtree(LeptrisElement elem, int version, int flags);
    char* leptris_c14n_canonicalize_subtree_ex(LeptrisElement elem, int version, int mode, const char** inclusive_ns_prefixes, int with_comments);

    const char* leptris_error_message(int status);
    const char* leptris_last_error(void);
    const char* leptris_document_last_error(LeptrisDocument doc);

    LeptrisXPathResult leptris_xpath_eval(LeptrisDocument doc, LeptrisElement context, const char* expression);
    LeptrisXPathResult leptris_xpath_eval_ns(LeptrisDocument doc, LeptrisElement context, const char* expression, LeptrisXPathNsSet ns);
    LeptrisXPathResult leptris_xpath_eval_with_vars_context(LeptrisDocument doc, LeptrisElement context, const char* expression, LeptrisXPathVariableSet variables);
    void     leptris_xpath_result_free(LeptrisXPathResult result);
    int      leptris_xpath_result_type(LeptrisXPathResult result);
    double   leptris_xpath_result_number(LeptrisXPathResult result);
    int      leptris_xpath_result_boolean(LeptrisXPathResult result);
    char*    leptris_xpath_result_string(LeptrisXPathResult result);
    size_t   leptris_xpath_result_count(LeptrisXPathResult result);
    LeptrisElement leptris_xpath_result_get(LeptrisXPathResult result, size_t index);
    size_t   leptris_xpath_result_get_nodes(LeptrisXPathResult result, LeptrisElement* out_nodes, size_t max_count);
    const char* leptris_version(void);
    int      leptris_xpath_result_node_kind(LeptrisXPathResult result, size_t index);
    LeptrisNodeRef leptris_xpath_result_get_node(LeptrisXPathResult result, size_t index);
    const char* leptris_xpath_result_node_name(LeptrisXPathResult result, size_t index);
    const char* leptris_xpath_result_node_value(LeptrisXPathResult result, size_t index);

    LeptrisXPathVariableSet leptris_xpath_variable_set_new(void);
    void leptris_xpath_variable_set_free(LeptrisXPathVariableSet set);
    int  leptris_xpath_variable_set_boolean(LeptrisXPathVariableSet set, const char* name, int value);
    int  leptris_xpath_variable_set_number(LeptrisXPathVariableSet set, const char* name, double value);
    int  leptris_xpath_variable_set_string(LeptrisXPathVariableSet set, const char* name, const char* value);

    LeptrisXPathNsSet leptris_xpath_ns_set_new(void);
    void leptris_xpath_ns_set_free(LeptrisXPathNsSet set);
    int  leptris_xpath_ns_set_add(LeptrisXPathNsSet set, const char* prefix, const char* uri);

    typedef struct leptris_xpath_compiled* LeptrisXPathCompiled;
    LeptrisXPathCompiled leptris_xpath_compile(const char* expression);
    LeptrisXPathResult leptris_xpath_compiled_eval(LeptrisXPathCompiled compiled, LeptrisDocument doc, LeptrisElement context);
    LeptrisXPathResult leptris_xpath_compiled_eval_ns(LeptrisXPathCompiled compiled, LeptrisDocument doc, LeptrisElement context, LeptrisXPathNsSet ns);
    LeptrisXPathResult leptris_xpath_compiled_eval_vars(LeptrisXPathCompiled compiled, LeptrisDocument doc, LeptrisElement context, LeptrisXPathVariableSet variables);
    void leptris_xpath_compiled_free(LeptrisXPathCompiled compiled);

    typedef struct leptris_iterparse* LeptrisIterparse;
    LeptrisIterparse leptris_iterparse_new(const char* xml, size_t len);
    typedef enum {
        LEPTRIS_ITERPARSE_TOP_LEVEL = 0,
        LEPTRIS_ITERPARSE_FULL_DOCUMENT = 1
    } LeptrisIterparseMode;
    LeptrisIterparse leptris_iterparse_new_ex(const char* xml, size_t len, int mode);
    LeptrisIterparse leptris_iterparse_new_file_ex(const char* path, int mode);
    const char* leptris_iterparse_error(LeptrisIterparse it);
    size_t leptris_iterparse_ns_count(LeptrisIterparse it);
    const char* leptris_iterparse_ns_uri(LeptrisIterparse it, const char* prefix);
    typedef struct {
        uint8_t kind;
        uint8_t reserved[7];
        uint32_t name_off, name_len;
        uint32_t text_off, text_len;
        uint32_t attrs_off;
        uint32_t attr_count;
        uint32_t line, column;
    } LeptrisSaxEventRecord;
    LeptrisSaxRecorder leptris_sax_recorder_new(void);
    int leptris_sax_recorder_feed(LeptrisSaxRecorder r, const char* xml, size_t len, int is_final);
    const LeptrisSaxEventRecord* leptris_sax_recorder_records(LeptrisSaxRecorder r, size_t* count);
    const char* leptris_sax_recorder_arena(LeptrisSaxRecorder r, size_t* len);
    void leptris_sax_recorder_free(LeptrisSaxRecorder r);
    LeptrisIterparse leptris_iterparse_new_file(const char* path);
    LeptrisElement leptris_iterparse_next(LeptrisIterparse it);
    void leptris_iterparse_free(LeptrisIterparse it);

    int leptris_sax_parse(const char* xml, size_t len, LeptrisSAXHandler* handler, void* user_data);
    LeptrisSAXParser* leptris_sax_parser_create(LeptrisSAXHandler* handler, void* user_data);
    int leptris_sax_parser_feed(LeptrisSAXParser* parser, const char* xml, size_t len, int is_final);
    void leptris_sax_parser_free(LeptrisSAXParser* parser);
    int leptris_sax_parser_set_streaming(LeptrisSAXParser* parser, int streaming);

    void leptris_free_string(char* str);
    """
)


def _load():
    candidates = []
    if os.environ.get("LEPTRIS_LIB_PATH"):
        candidates.append(os.environ["LEPTRIS_LIB_PATH"])
    candidates += ["libleptris.dylib", "libleptris.so", "leptris.dll"]
    here = os.path.dirname(__file__)
    candidates += [
        os.path.join(here, "..", "..", "..", "build", "src", "libleptris.dylib"),
        os.path.join(here, "..", "..", "..", "build", "src", "libleptris.so"),
    ]
    for name in candidates:
        try:
            return ffi.dlopen(name)
        except OSError:
            continue
    raise ImportError(
        "libleptris not found; build it or set LEPTRIS_LIB_PATH"
    )


lib = _load()

NODE_ELEMENT = 0
NODE_TEXT = 1
NODE_COMMENT = 2
NODE_CDATA = 3
NODE_PI = 4
NODE_DOCTYPE = 5

XPATH_NODESET = 0
XPATH_BOOLEAN = 1
XPATH_NUMBER = 2
XPATH_STRING = 3

XPATH_NODE_ELEMENT = 0
XPATH_NODE_ATTRIBUTE = 1
XPATH_NODE_TEXT = 2
XPATH_NODE_OTHER = 3

C14N_1_0 = 0
C14N_1_1 = 1
C14N_CANONICAL = 0
C14N_EXCLUSIVE = 1
