/* Registry access (see registry.h). */
#include "registry.h"
#include "registry_gen.h"
#include <stdlib.h>
#include <string.h>

/* Two compiled registries (hive answer 1 on t-2026-11-12-mettadinc-m4-estimates): the release registry
 * (registry_gen.c, the bundle patches only) and the beyond-release registry (registry_beyond_gen.c, plus the
 * local patches).  The beyond one is used only while --beyond-release is on (dc_eval_beyond_release), so
 * release 1 admits, answers and reports its digest exactly as before the local patches. */
int dc_eval_beyond_release(void);
static Sx *g_all[2];       /* parse results: [0] release, [1] beyond release; each a list holding the root form */

static const Sx *load(int b) {
    if (g_all[b]) return g_all[b]->n ? g_all[b]->items[0] : NULL;
    const char *const *parts = b ? dc_registry_beyond_parts : dc_registry_parts;
    size_t n = 0;
    for (size_t i = 0; parts[i]; i++) n += strlen(parts[i]);
    char *buf = malloc(n + 1);
    if (!buf) return NULL;
    size_t k = 0;
    for (size_t i = 0; parts[i]; i++) {
        size_t l = strlen(parts[i]);
        memcpy(buf + k, parts[i], l); k += l;
    }
    buf[k] = 0;
    const char *err = NULL; int line = 0;
    g_all[b] = sx_parse_all(buf, &err, &line);
    free(buf);
    if (!g_all[b] || g_all[b]->n != 1 || !sx_head_is(g_all[b]->items[0], "Dict")) {
        sx_free(g_all[b]); g_all[b] = NULL; return NULL;
    }
    return g_all[b]->items[0];
}

const Sx *dc_registry(void) { return load(dc_eval_beyond_release() ? 1 : 0); }

const char *dc_registry_digest_hex(void) {
    return dc_eval_beyond_release() ? dc_registry_beyond_digest : dc_registry_digest;
}

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

void dc_registry_free(void) { for (int b = 0; b < 2; b++) { sx_free(g_all[b]); g_all[b] = NULL; } }
