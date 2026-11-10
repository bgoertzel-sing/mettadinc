/* Registry access (see registry.h). */
#include "registry.h"
#include "registry_gen.h"
#include <stdlib.h>
#include <string.h>

static Sx *g_all;          /* parse result: a list holding the root form */

const Sx *dc_registry(void) {
    if (g_all) return g_all->n ? g_all->items[0] : NULL;
    size_t n = 0;
    for (size_t i = 0; dc_registry_parts[i]; i++) n += strlen(dc_registry_parts[i]);
    char *buf = malloc(n + 1);
    if (!buf) return NULL;
    size_t k = 0;
    for (size_t i = 0; dc_registry_parts[i]; i++) {
        size_t l = strlen(dc_registry_parts[i]);
        memcpy(buf + k, dc_registry_parts[i], l); k += l;
    }
    buf[k] = 0;
    const char *err = NULL; int line = 0;
    g_all = sx_parse_all(buf, &err, &line);
    free(buf);
    if (!g_all || g_all->n != 1 || !sx_head_is(g_all->items[0], "Dict")) { sx_free(g_all); g_all = NULL; return NULL; }
    return g_all->items[0];
}

const char *dc_registry_digest_hex(void) { return dc_registry_digest; }

const Sx *dc_reg_get(const Sx *dict, const char *key) {
    if (!dict || !sx_head_is(dict, "Dict")) return NULL;
    for (size_t i = 1; i < dict->n; i++) {
        const Sx *e = dict->items[i];
        if (e->kind == SX_LIST && e->n == 2 && e->items[0]->kind == SX_STR && !strcmp(e->items[0]->text, key))
            return e->items[1];
    }
    return NULL;
}

static const Sx *section(const char *sec, const char *name) {
    return dc_reg_get(dc_reg_get(dc_registry(), sec), name);
}
const Sx *dc_reg_decl(const char *head) { return section("declarations", head); }
const Sx *dc_reg_request(const char *head) { return section("requests", head); }
const Sx *dc_reg_library(const char *name) { return section("libraries", name); }
const Sx *dc_reg_result_type(const char *name) { return section("result_types", name); }

const char *dc_reg_str(const Sx *v) { return v && v->kind == SX_STR ? v->text : NULL; }

int dc_reg_list_has(const Sx *list, const char *s) {
    if (!list || !sx_head_is(list, "List")) return 0;
    for (size_t i = 1; i < list->n; i++)
        if (list->items[i]->kind == SX_STR && !strcmp(list->items[i]->text, s)) return 1;
    return 0;
}

int dc_reg_true(const Sx *v) { return sx_is_sym(v, "True"); }

void dc_registry_free(void) { sx_free(g_all); g_all = NULL; }
