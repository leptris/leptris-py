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
    LeptrisDocument leptris_parse_string_with_encoding(const char* xml, size_t len, int* status);
    typedef struct leptris_xslt* LeptrisXslt;
    LeptrisXslt leptris_xslt_parse(const char* stylesheet_xml, size_t len);
    LeptrisXslt leptris_xslt_parse_file(const char* path);
    LeptrisDocument leptris_xslt_apply(LeptrisXslt xslt, LeptrisDocument doc);
    char* leptris_xslt_apply_string(LeptrisXslt xslt, LeptrisDocument doc);
    void leptris_xslt_free(LeptrisXslt xslt);
    int leptris_exslt_enable(LeptrisDocument doc);
    typedef struct LeptrisXQueryInternal* LeptrisXQuery;
    LeptrisXQuery leptris_xquery_parse(const char* query, size_t len);
    LeptrisXPathResult leptris_xquery_eval(LeptrisXQuery query, LeptrisDocument doc, LeptrisElement context_node);
    void leptris_xquery_free(LeptrisXQuery query);
    typedef struct LeptrisRelaxNGInternal* LeptrisRelaxNG;
    LeptrisRelaxNG leptris_rng_parse(const char* schema, size_t len, int* status);
    LeptrisRelaxNG leptris_rng_parse_file(const char* path, int* status);
    void leptris_rng_free(LeptrisRelaxNG rng);
    int leptris_rng_validate(LeptrisRelaxNG rng, LeptrisDocument doc);
    const char* leptris_rng_error(LeptrisRelaxNG rng);

    typedef struct leptris_schematron* LeptrisSchematron;
    LeptrisSchematron leptris_schematron_parse(const char* schema, size_t len, int* status);
    LeptrisSchematron leptris_schematron_parse_file(const char* path, int* status);
    LeptrisSchematron leptris_schematron_parse_phase(const char* schema, size_t len, const char* phase, int* status);
    void leptris_schematron_free(LeptrisSchematron sch);
    int leptris_schematron_valid(LeptrisSchematron sch, LeptrisDocument doc);
    LeptrisDocument leptris_schematron_validate(LeptrisSchematron sch, LeptrisDocument doc);
    const char* leptris_schematron_error(LeptrisSchematron sch);
    typedef struct LeptrisDoctypeInternal* LeptrisDoctype;
    LeptrisDoctype leptris_document_internal_subset(LeptrisDocument doc);
    const char* leptris_doctype_get_name(LeptrisDoctype dt);
    const char* leptris_doctype_get_public_id(LeptrisDoctype dt);
    const char* leptris_doctype_get_system_id(LeptrisDoctype dt);
    /* DTD validation (libleptris 1.9.202+) */
    typedef struct LeptrisDTD LeptrisDTD;
    typedef struct {
        char* message;
        char* element_name;
        int line;
        int column;
    } LeptrisDTDError;
    LeptrisDTD* leptris_dtd_parse(const char* dtd_content, size_t len);
    LeptrisDTD* leptris_document_get_dtd(LeptrisDocument doc);
    int leptris_dtd_parse_external_subset(LeptrisDTD* dtd, const char* content,
                                          size_t len);
    void leptris_dtd_set_pe_loader(LeptrisDTD* dtd,
                                   char* (*loader)(void* user_data,
                                                   const char* system_id,
                                                   size_t* out_len),
                                   void* user_data);
    int leptris_dtd_validate(LeptrisDocument doc, LeptrisDTD* dtd,
                             LeptrisDTDError* error);
    void leptris_dtd_free(LeptrisDTD* dtd);
    void leptris_dtd_error_free(LeptrisDTDError* error);
    /* engine-heap allocation for FFI-supplied buffers (1.9.204+):
       released with leptris_free_string; PE-loader buffers are
       consumed and freed by the parser */
    char* leptris_alloc_buffer(size_t len);
    /* document-level declaration/doctype removal (1.9.204+) */
    /* unified narration record kinds (types.h, 1.9.208) */
    typedef enum {
        LEPTRIS_DIAG_INVALID = 0,
        LEPTRIS_DIAG_NOT_ALLOWED_ANYWHERE,
        LEPTRIS_DIAG_NOT_ALLOWED_HERE,
        LEPTRIS_DIAG_NOT_ALLOWED_YET,
        LEPTRIS_DIAG_INCOMPLETE,
        LEPTRIS_DIAG_MISSING_REQUIRED_ATTR,
        LEPTRIS_DIAG_ATTR_NOT_ALLOWED,
        LEPTRIS_DIAG_ATTR_VALUE_INVALID,
        LEPTRIS_DIAG_CHAR_CONTENT_INVALID,
        LEPTRIS_DIAG_RECOVER,
        LEPTRIS_DIAG_COUNT_
    } LeptrisDiagKind;
    /* parse recover channel (#1200, 1.9.206+) */
    size_t leptris_document_parse_diag_count(LeptrisDocument doc);
    int leptris_document_parse_diag(LeptrisDocument doc,
                                    size_t index,
                                    LeptrisDiagKind* kind,
                                    char* message,
                                    size_t message_cap);
    LeptrisStatus leptris_document_clear_declaration(LeptrisDocument doc);
    LeptrisStatus leptris_document_remove_doctype(LeptrisDocument doc);
    typedef struct LeptrisDiffInternal* LeptrisDiff;
    LeptrisDiff leptris_diff(LeptrisDocument a, LeptrisDocument b, unsigned int flags, int* status);
    void leptris_diff_free(LeptrisDiff diff);
    size_t leptris_diff_op_count(LeptrisDiff diff);
    int leptris_diff_op_type(LeptrisDiff diff, size_t index);
    const char* leptris_diff_op_path(LeptrisDiff diff, size_t index);
    const char* leptris_diff_op_name(LeptrisDiff diff, size_t index);
    const char* leptris_diff_op_before(LeptrisDiff diff, size_t index);
    const char* leptris_diff_op_after(LeptrisDiff diff, size_t index);
    char* leptris_diff_serialize(LeptrisDiff diff);
    LeptrisXPathResult leptris_xquery_eval_params(LeptrisXQuery query, LeptrisDocument doc, LeptrisElement context_node, const char* const* names, const char* const* selects, size_t count);
    LeptrisDocument leptris_parse_file(const char* filepath, int* status);
    LeptrisDocument leptris_parse_html_string(const char* html, size_t length, int* status);
    LeptrisDocument leptris_parse_html4_string(const char* html, size_t length, int* status);
    void           leptris_document_free(LeptrisDocument doc);
    LeptrisElement  leptris_document_root(LeptrisDocument doc);
    char*          leptris_document_serialize(LeptrisDocument doc, LeptrisSerializeOptions* options);
    /* #1309 (1.9.225+): the ext options grew html_method (tri-state:
     * 0 = document default, 1 = force HTML, -1 = force XML); the
     * size-aware entries keep older bindings safe */
    typedef struct {
        int indent_text;
        const char* indent_unit;
        int expand_empty;
        int html_method;
    } LeptrisSerializeExtOptions;
    char* leptris_document_serialize_ext_sized(
        LeptrisDocument doc, const LeptrisSerializeOptions* options,
        const LeptrisSerializeExtOptions* ext, size_t ext_size);
    char* leptris_element_serialize_ext_sized(
        LeptrisElement elem, const LeptrisSerializeOptions* options,
        const LeptrisSerializeExtOptions* ext, size_t ext_size);
    /* HTML-flavored document construction + serialization */
    LeptrisDocument leptris_document_create_html(void);
    char* leptris_document_serialize_html(
        LeptrisDocument doc, LeptrisSerializeOptions* options);
    int leptris_document_save_html(
        LeptrisDocument doc, const char* filepath,
        LeptrisSerializeOptions* options);
    int            leptris_xinclude_process(LeptrisDocument doc, const char* base_path);
    int            leptris_document_save_file(LeptrisDocument doc, const char* filepath, LeptrisSerializeOptions* options);

    int    leptris_node_get_type(LeptrisNodeRef node);
    typedef unsigned int LeptrisDigestFlags;
    unsigned long long leptris_node_digest(LeptrisNodeRef node, LeptrisDigestFlags flags);
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
    /* bulk attribute face (#1254, 1.9.216+): one C pass; strings and
     * handles stay engine-owned */
    size_t leptris_element_attribute_pairs(
        LeptrisElement elem, const char** out_names, const char** out_values,
        LeptrisAttribute* out_attrs, size_t max_count);
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
    typedef enum { LEPTRIS_XPATH_10 = 1, LEPTRIS_XPATH_31 = 3 } LeptrisXPathVersion;
    LeptrisXPathResult leptris_xpath_eval_versioned(LeptrisDocument doc, LeptrisElement context, const char* expression, LeptrisXPathVersion version, LeptrisStatus* status);
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
    LeptrisXPathResult leptris_xpath_compiled_eval_ns_vars(LeptrisXPathCompiled compiled, LeptrisDocument doc, LeptrisElement context, LeptrisXPathNsSet ns, LeptrisXPathVariableSet variables);
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
    void leptris_sax_recorder_reset(LeptrisSaxRecorder r);
    LeptrisIterparse leptris_iterparse_new_file(const char* path);
    LeptrisElement leptris_iterparse_next(LeptrisIterparse it);
    void leptris_iterparse_free(LeptrisIterparse it);

    int leptris_sax_parse(const char* xml, size_t len, LeptrisSAXHandler* handler, void* user_data);
    LeptrisSAXParser* leptris_sax_parser_create(LeptrisSAXHandler* handler, void* user_data);
    int leptris_sax_parser_feed(LeptrisSAXParser* parser, const char* xml, size_t len, int is_final);
    void leptris_sax_parser_free(LeptrisSAXParser* parser);
    int leptris_sax_parser_set_streaming(LeptrisSAXParser* parser, int streaming);

    void leptris_free_string(char* str);

    /* Tree-shaped schema-descriptor materialization (#1039, lib
     * 1.9.162+): the ABI is frozen at leptris_plan_abi_version(). */
    size_t leptris_node_byte_offset(LeptrisNodeRef node);
    typedef struct leptris_plan* LeptrisPlan;
    typedef struct leptris_plan_result* LeptrisPlanResult;
    typedef enum {
        LEPTRIS_PLAN_KIND_SCALAR = 1,
        LEPTRIS_PLAN_KIND_COLLECTION = 2,
        LEPTRIS_PLAN_KIND_NESTED = 3,
        LEPTRIS_PLAN_KIND_RAW = 4,
        LEPTRIS_PLAN_KIND_CONTENT = 5,
        LEPTRIS_PLAN_KIND_CALLBACK = 6
    } LeptrisPlanKind;
    #define LEPTRIS_PLAN_FLAG_MIXED_CONTENT 0x1
    #define LEPTRIS_PLAN_FLAG_ORDERED 0x2
    #define LEPTRIS_PLAN_FLAG_CDATA 0x4
    #define LEPTRIS_PLAN_FLAG_NS_LENIENT 0x8
    #define LEPTRIS_PLAN_FLAG_EMIT_ORDER_SPINE 0x10
    typedef enum {
        LEPTRIS_PLAN_NS_NONE = 0,
        LEPTRIS_PLAN_NS_EXACT = 1,
        LEPTRIS_PLAN_NS_ANY = 2
    } LeptrisPlanNsForm;
    typedef struct {
        const char* wire_name;
        const char* expected_value;
    } leptris_attr_predicate;
    typedef struct {
        const char* wire_name;
        uint8_t kind;
        uint8_t type_tag;
        /* #1272 (additive, 1.9.216+): predicate_count = 0 keeps the
         * historical behavior; strings deep-copied at build */
        uint16_t predicate_count;
        uint16_t pad_pred;
        const leptris_attr_predicate* predicates;
    } leptris_attr_plan;
    typedef struct {
        const char* wire_name;
        uint8_t kind;
        uint8_t type_tag;
        int32_t child_plan_index;
        /* #1115 (additive, v1.9.178+): rule-level namespace form.
         * NONE keeps the historical no-namespace behavior. */
        uint8_t ns_form;
        uint8_t pad0;
        const char* ns_uri;
        /* #1272 (additive, 1.9.216+): element-side predicates */
        uint16_t predicate_count;
        uint16_t pad_pred;
        const leptris_attr_predicate* predicates;
    } leptris_child_plan;
    typedef struct {
        const char* element_name;
        uint8_t ns_form;
        uint8_t pad0;
        const char* ns_uri;
        uint32_t attribute_count;
        uint32_t child_count;
        const leptris_attr_plan* attribute_plans;
        const leptris_child_plan* child_plans;
        uint16_t flags;
        uint16_t pad1;
    } leptris_element_plan;
    typedef struct {
        uint32_t abi_version;
        uint32_t plan_count;
        const leptris_element_plan* plans;
    } leptris_plan_spec;
    typedef enum {
        LEPTRIS_PLAN_VALUE_ELEMENT = 0,
        LEPTRIS_PLAN_VALUE_SCALAR = 1,
        LEPTRIS_PLAN_VALUE_COLLECTION = 2,
        LEPTRIS_PLAN_VALUE_RAW = 3,
        LEPTRIS_PLAN_VALUE_CALLBACK = 4
    } LeptrisPlanValueKind;
    void leptris_element_expanded_name(LeptrisElement e, const char** local, const char** prefix, const char** uri);
    /* node-surface parity (lib 1.9.176, #1094) */
    /* RNG validation errors accumulate (#878, libleptris >= 1.9.179):
     * every failure from the last validate call, Jing-compatible
     * message vocabulary and positions. Reset per validate. */
    size_t leptris_rng_error_count(LeptrisRelaxNG rng);
    const char* leptris_rng_error_message(LeptrisRelaxNG rng, size_t i);
    int leptris_rng_error_line(LeptrisRelaxNG rng, size_t i);
    int leptris_rng_error_column(LeptrisRelaxNG rng, size_t i);

    /* The whole report in one call (libleptris >= 1.9.195, #1154's
     * used-export makes it bindable): handle-owned record array,
     * live until the next validate or free. */
    typedef struct {
        const char* kind;
        const char* message;
        const char* offender;
        unsigned int line;
        unsigned int column;
    } LeptrisRngErrorRecord;
    size_t leptris_rng_error_report(LeptrisRelaxNG rng,
                                    LeptrisRngErrorRecord** out);

    /* Parser-recorded source position (#1124, libleptris >= 1.9.180).
     * Columns follow Jing's convention: col_start is the byte after
     * the start tag's '>', col_end after the final '>'. Zeros for
     * programmatically-created nodes. */
    typedef struct {
        int line;
        int col_start;
        int col_end;
    } LeptrisSourcePosition;
    void leptris_node_source_position(LeptrisNodeRef node,
                                      LeptrisSourcePosition* out);

    LeptrisNodeRef leptris_document_append_pi(LeptrisDocument doc, const char* target, const char* data);
    LeptrisStatus leptris_document_remove_child(LeptrisDocument doc, LeptrisNodeRef node);
    LeptrisDoctype leptris_document_set_doctype(LeptrisDocument doc, const char* name, const char* public_id, const char* system_id);
    LeptrisStatus leptris_document_set_encoding(LeptrisDocument doc, const char* encoding);
    LeptrisStatus leptris_document_set_standalone(LeptrisDocument doc, int standalone);
    LeptrisStatus leptris_document_set_version(LeptrisDocument doc, const char* version);
    int leptris_document_standalone(LeptrisDocument doc);
    const char* leptris_document_version(LeptrisDocument doc);
    LeptrisNodeRef leptris_entity_ref_node_create(LeptrisDocument doc, const char* name);
    const char* leptris_entity_ref_node_name(LeptrisNodeRef node);
    uint32_t leptris_plan_abi_version(void);
    LeptrisPlan leptris_plan_build(const leptris_plan_spec* spec, LeptrisStatus* status);
    void leptris_plan_free(LeptrisPlan plan);
    /* entering-only subtree visitation (1.9.232+, #1332): once per
     * node -- elements are not re-visited after their subtree */
    typedef void (*LeptrisNodeVisitor)(void* user_data, LeptrisNodeRef node,
                                       int entering, int depth);
    void leptris_node_visit_entering(LeptrisNodeRef root,
                                     LeptrisNodeVisitor visitor,
                                     void* user_data);
    /* programmatic construction (engine creation surface, 1.9.216) */
    LeptrisDocument leptris_document_create(void);
    LeptrisStatus leptris_document_set_root(LeptrisDocument doc, LeptrisElement elem);
    LeptrisElement leptris_element_create(LeptrisDocument doc, const char* name);
    /* single-crossing element construction (1.9.237+): one call
     * creates the element and sets every attribute */
    LeptrisElement leptris_element_new_with_attributes(
        LeptrisDocument doc, const char* name, const char** attr_names,
        const char** attr_values, size_t attr_count);
    LeptrisElement leptris_element_create_child(LeptrisElement parent, const char* name);
    LeptrisStatus leptris_element_append_child(LeptrisElement parent, LeptrisElement child);
    LeptrisStatus leptris_element_insert_before(LeptrisElement sibling, LeptrisElement new_node);
    LeptrisStatus leptris_element_insert_after(LeptrisElement sibling, LeptrisElement new_node);
    LeptrisStatus leptris_element_set_text(LeptrisElement elem, const char* text);
    LeptrisStatus leptris_element_set_attribute(LeptrisElement elem,
                                                const char* name, const char* value);
    LeptrisPlanResult leptris_plan_walk(LeptrisDocument doc, LeptrisElement ctx, LeptrisPlan plan, LeptrisStatus* status);
    /* fused parse+walk+free (#1269b, 1.9.216+): parse_string +
     * walk(root) + free(doc) in one call — byte-parity result */
    LeptrisPlanResult leptris_plan_materialize(
        const char* source, size_t source_len,
        LeptrisPlan plan, LeptrisStatus* status);
    void leptris_plan_result_free(LeptrisPlanResult result);
    LeptrisPlanValueKind leptris_plan_value_kind(const LeptrisPlanResult v);
    const char* leptris_plan_value_name(const LeptrisPlanResult v);
    /* #1273 order identity + #1269a in-pass types (1.9.216+) */
    uint8_t leptris_plan_value_node_kind(const LeptrisPlanResult v);
    uint32_t leptris_plan_value_order_index(const LeptrisPlanResult v);
    int leptris_plan_value_int(const LeptrisPlanResult v, int64_t* out);
    int leptris_plan_value_float(const LeptrisPlanResult v, double* out);
    int leptris_plan_value_bool(const LeptrisPlanResult v, int* out);
    uint8_t leptris_plan_value_type_tag(const LeptrisPlanResult v);
    const char* leptris_plan_value_string(const LeptrisPlanResult v);
    size_t leptris_plan_value_length(const LeptrisPlanResult v);
    size_t leptris_plan_value_position(const LeptrisPlanResult v);
    size_t leptris_plan_value_count(const LeptrisPlanResult v);
    LeptrisPlanResult leptris_plan_value_at(const LeptrisPlanResult v, size_t i);
    const char* leptris_plan_value_attribute(const LeptrisPlanResult v, const char* wire_name);
    """
)


def _load():
    here = os.path.dirname(__file__)
    candidates = []
    if os.environ.get("LEPTRIS_LIB_PATH"):
        candidates.append(os.environ["LEPTRIS_LIB_PATH"])
    # Wheels vendor the pinned release build per platform
    # (scripts/vendor_libleptris.sh -> leptris/_vendor/).
    candidates += [
        os.path.join(here, "_vendor", "libleptris.dylib"),
        os.path.join(here, "_vendor", "libleptris.so"),
        os.path.join(here, "_vendor", "leptris.dll"),
    ]
    candidates += ["libleptris.dylib", "libleptris.so", "leptris.dll"]
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
# XPath 3.0 function item (libleptris TODO 07 lane): a closure or
# named function reference. Not callable across the FFI boundary
# yet — _convert raises explicitly.
XPATH_FUNCTION = 4

XPATH_NODE_ELEMENT = 0
XPATH_NODE_ATTRIBUTE = 1
XPATH_NODE_TEXT = 2
XPATH_NODE_OTHER = 3

C14N_1_0 = 0
C14N_1_1 = 1
C14N_CANONICAL = 0
C14N_EXCLUSIVE = 1
