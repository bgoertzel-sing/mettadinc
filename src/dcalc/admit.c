/* M1 admission (see admit.h).  Mirrors validation/check_fixtures.py; the
 * comments name the checker function each part follows. */
#include "admit.h"
#include "registry.h"
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void *xm(size_t n) { void *p = malloc(n ? n : 1); if (!p) abort(); return p; }
static char *xs(const char *s) { size_t n = strlen(s) + 1; char *p = xm(n); memcpy(p, s, n); return p; }
static void grow(void **v, size_t *cap, size_t n, size_t el) {
    if (n < *cap) return;
    *cap = *cap ? *cap * 2 : 8;
    *v = realloc(*v, *cap * el);
    if (!*v) abort();
}

/* ------------------------------------------------------------ string sets */
int dc_ss_has(const DcStrSet *s, const char *x) {
    for (size_t i = 0; i < s->n; i++) if (!strcmp(s->v[i], x)) return 1;
    return 0;
}
void dc_ss_add(DcStrSet *s, const char *x) {
    if (dc_ss_has(s, x)) return;
    grow((void **)&s->v, &s->cap, s->n, sizeof *s->v);
    s->v[s->n++] = xs(x);
}
void dc_ss_free(DcStrSet *s) {
    for (size_t i = 0; i < s->n; i++) free(s->v[i]);
    free(s->v); memset(s, 0, sizeof *s);
}

/* ------------------------------------------------------------ printing, diagnostics */
static const char *shw(const Sx *x, char *buf, size_t n) {
    char *p = sx_print(x); snprintf(buf, n, "%s", p); free(p); return buf;
}
/* Key of an atom or form as the checker stores it: symbol text, else printed. */
static const char *key_of(const Sx *x, char *buf, size_t n) {
    if (x->kind == SX_SYM) return x->text;
    return shw(x, buf, n);
}
static void diag(DcAdmission *a, const char *mod, const Sx *at, const char *where, const char *fmt, ...) {
    char msg[1024], full[1400];
    va_list ap; va_start(ap, fmt); vsnprintf(msg, sizeof msg, fmt, ap); va_end(ap);
    snprintf(full, sizeof full, "%s:%d:%d: %s: %s", a->fname ? a->fname : "?", at ? at->line : 0, at ? at->col : 0, where, msg);
    grow((void **)&a->diag.v, &a->diag.cap, a->diag.n, sizeof *a->diag.v);
    a->diag.v[a->diag.n].mod = xs(mod ? mod : "");
    a->diag.v[a->diag.n].msg = xs(full);
    a->diag.n++;
}
size_t dc_admit_module_ndiag(const DcAdmission *a, const char *mn) {
    size_t k = 0;
    for (size_t i = 0; i < a->diag.n; i++) if (!strcmp(a->diag.v[i].mod, mn)) k++;
    return k;
}

/* ------------------------------------------------------------ registry helpers */
static const Sx *reg_section(const char *sec) { return dc_reg_get(dc_registry(), sec); }
/* lib_names: name appears under key in one of the module's libraries. */
static int lib_has(const DcAModule *m, const char *key, const char *name) {
    for (size_t i = 0; i < m->libraries.n; i++) {
        const Sx *v = dc_reg_get(dc_reg_library(m->libraries.v[i]), key);
        if (dc_reg_list_has(v, name) || (sx_head_is(v, "Dict") && dc_reg_get(v, name))) return 1;
    }
    return 0;
}

/* ------------------------------------------------------------ declarations table */
static DcADecl *find_decl(const DcAModule *m, const char *name) {
    for (size_t i = 0; i < m->ndecl; i++) if (!strcmp(m->decls[i].name, name)) return &m->decls[i];
    return NULL;
}
static void put_decl(DcAModule *m, const char *name, const char *kind, const Sx *form, int own) {
    DcADecl *d = find_decl(m, name);
    if (!d) {
        grow((void **)&m->decls, &m->capdecl, m->ndecl, sizeof *m->decls);
        d = &m->decls[m->ndecl++]; d->name = xs(name);
    }
    d->kind = kind; d->form = form; d->own = own;
}
DcAModule *dc_admit_find(DcAdmission *a, const char *name) {
    for (size_t i = 0; i < a->nmod; i++) if (!strcmp(a->mods[i].name, name)) return &a->mods[i];
    return NULL;
}

/* collect_names */
static void collect_names(DcAModule *m, const char *head, const Sx *it) {
    char b[512];
    for (size_t i = 2; i < it->n; i++) {
        const Sx *x = it->items[i];
        if (x->kind != SX_LIST || x->n == 0) continue;
        const Sx *h = x->items[0];
        if (!strcmp(head, "Carrier")) {
            if (sx_is_sym(h, "Enum")) for (size_t k = 1; k < x->n; k++) dc_ss_add(&m->elements, key_of(x->items[k], b, sizeof b));
        } else if (!strcmp(head, "Record")) {
            dc_ss_add(&m->fields, key_of(h, b, sizeof b));
        } else if (!strcmp(head, "Machine") || !strcmp(head, "MethodSystem")) {
            if ((sx_is_sym(h, "Observe") || sx_is_sym(h, "Action") || sx_is_sym(h, "Merge")) && x->n > 1) {
                const Sx *l = x->items[1];
                if (l->kind == SX_LIST) { if (l->n && l->items[0]->kind != SX_LIST) dc_ss_add(&m->labels, key_of(l->items[0], b, sizeof b)); }
                else dc_ss_add(&m->labels, key_of(l, b, sizeof b));
            }
        } else {
            const char *tag = !strcmp(head, "BlockPartition") ? "Block" : !strcmp(head, "KernelHive") ? "Member"
                            : !strcmp(head, "DescriptionSystem") ? "Description" : NULL;
            if (tag && sx_is_sym(h, tag) && x->n > 1) dc_ss_add(&m->labels, key_of(x->items[1], b, sizeof b));
        }
    }
}

/* parse_profile */
static void parse_profile(DcAdmission *a, DcAModule *m, const Sx *it) {
    char b[512];
    const Sx *P = reg_section("profiles");
    if (it->n == 2 && it->items[1]->kind != SX_LIST) {
        const Sx *sh = dc_reg_get(dc_reg_get(P, "shorthands"), key_of(it->items[1], b, sizeof b));
        if (!sh || sh->n != 4) { diag(a, m->name, it, m->name, "unknown profile shorthand %s", b[0] ? b : it->items[1]->text); return; }
        m->dynamics = dc_reg_str(sh->items[1]); m->values = dc_reg_str(sh->items[2]); m->carriers = dc_reg_str(sh->items[3]);
        return;
    }
    m->dynamics = m->values = m->carriers = NULL;
    for (size_t i = 1; i < it->n; i++) {
        const Sx *x = it->items[i];
        if (x->kind != SX_LIST || x->n != 2 || x->items[0]->kind != SX_SYM || x->items[1]->kind == SX_LIST) continue;
        const char *k = x->items[0]->text, *v = x->items[1]->text;
        if (!strcmp(k, "Dynamics")) m->dynamics = v;
        else if (!strcmp(k, "Values")) m->values = v;
        else if (!strcmp(k, "Carriers")) m->carriers = v;
    }
    if (!m->dynamics || !dc_reg_list_has(dc_reg_get(P, "dynamics"), m->dynamics) ||
        !m->values || !dc_reg_list_has(dc_reg_get(P, "values"), m->values) ||
        !m->carriers || !dc_reg_list_has(dc_reg_get(P, "carriers"), m->carriers))
        diag(a, m->name, it, m->name, "bad profile %s", shw(it, b, sizeof b));
}

/* scan_module */
static void scan_module(DcAdmission *a, DcAModule *m) {
    char b[512];
    dc_ss_add(&m->libraries, "Core");
    int profiled = 0;
    for (size_t i = 2; i < m->form->n; i++) {
        const Sx *it = m->form->items[i];
        if (it->kind != SX_LIST || it->n == 0) { diag(a, m->name, it, m->name, "module %s: stray atom %s", m->name, shw(it, b, sizeof b)); continue; }
        const Sx *h = it->items[0];
        const char *hd = h->kind == SX_SYM ? h->text : NULL;
        if (hd && !strcmp(hd, "Profile")) { parse_profile(a, m, it); profiled = 1; }
        else if (hd && !strcmp(hd, "Use")) {
            for (size_t k = 1; k < it->n; k++) {
                const char *lib = key_of(it->items[k], b, sizeof b);
                if (it->items[k]->kind != SX_SYM || !dc_reg_library(lib)) diag(a, m->name, it->items[k], m->name, "module %s: unknown library %s", m->name, lib);
                dc_ss_add(&m->libraries, lib);
            }
        } else if (hd && !strcmp(hd, "Import")) {
            grow((void **)&m->imports, &m->capimp, m->nimp, sizeof *m->imports);
            m->imports[m->nimp++] = it;
        } else if (hd && dc_reg_decl(hd)) {
            if (it->n < 2 || it->items[1]->kind == SX_LIST) { diag(a, m->name, it, m->name, "%s without a name", hd); continue; }
            const char *nm = key_of(it->items[1], b, sizeof b);
            if (find_decl(m, nm)) diag(a, m->name, it->items[1], m->name, "duplicate declaration %s", nm);
            put_decl(m, nm, hd, it, 1);
            collect_names(m, hd, it);
        } else diag(a, m->name, it, m->name, "module %s: unknown declaration head %s", m->name, key_of(h, b, sizeof b));
    }
    if (!profiled || !m->dynamics) diag(a, m->name, m->form, m->name, "module %s: missing Profile", m->name);
}

/* resolve_imports */
static void resolve_imports(DcAdmission *a, DcAModule *m) {
    char b[512];
    for (size_t i = 0; i < m->nimp; i++) {
        const Sx *imp = m->imports[i];
        if (imp->n < 3 || !sx_head_is(imp->items[2], "Only")) {
            diag(a, m->name, imp, m->name, "Import must name its declarations with (Only ...): %s", shw(imp, b, sizeof b)); continue;
        }
        const char *sn = key_of(imp->items[1], b, sizeof b);
        DcAModule *src = dc_admit_find(a, sn);
        if (!src) { diag(a, m->name, imp, m->name, "Import of unknown module %s", sn); continue; }
        const Sx *only = imp->items[2];
        for (size_t k = 1; k < only->n; k++) {
            char c[512]; const char *nm = key_of(only->items[k], c, sizeof c);
            DcADecl *d = find_decl(src, nm);
            if (!d) { diag(a, m->name, only->items[k], m->name, "Import: %s has no declaration %s", src->name, nm); continue; }
            put_decl(m, nm, d->kind, d->form, 0);
            collect_names(m, d->kind, d->form);
        }
        for (size_t k = 0; k < src->elements.n; k++) dc_ss_add(&m->elements, src->elements.v[k]);
        for (size_t k = 0; k < src->libraries.n; k++) dc_ss_add(&m->libraries, src->libraries.v[k]);
    }
}

/* ------------------------------------------------------------ part 2: references and values */
typedef struct { char *var; const char *rt; } DcRes;
typedef struct {
    DcAdmission *a; DcAModule *m;
    char where[320];          /* \"fname:Module.decl\" as the checker prints it */
    const Sx *at;             /* item under check, for the location */
    DcRes *res; size_t nres, capres;   /* LetResult variables -> result type (Ctx.results) */
    DcStrSet bound;
} Ctx;

static void cerr(Ctx *c, const Sx *at, const char *fmt, ...) {
    char msg[1024];
    va_list ap; va_start(ap, fmt); vsnprintf(msg, sizeof msg, fmt, ap); va_end(ap);
    diag(c->a, c->m->name, at ? at : c->at, c->where, "%s", msg);
}
static const char *res_get(const Ctx *c, const char *v) {
    for (size_t i = c->nres; i-- > 0;) if (!strcmp(c->res[i].var, v)) return c->res[i].rt;
    return NULL;
}

/* is_num: an optional '-' and decimal digits (no size limit). */
static int is_num(const Sx *x) {
    if (!x || x->kind != SX_SYM) return 0;
    const char *p = x->text;
    if (*p == '-') p++;
    if (!*p) return 0;
    for (; *p; p++) if (*p < '0' || *p > '9') return 0;
    return 1;
}
/* Compare two decimal integers of any length: -1, 0 or 1 (no overflow). */
static int num_cmp(const char *a, const char *b) {
    int na = *a == '-', nb = *b == '-';
    if (na) a++;
    if (nb) b++;
    while (*a == '0' && a[1]) a++;
    while (*b == '0' && b[1]) b++;
    if (!strcmp(a, "0")) na = 0;
    if (!strcmp(b, "0")) nb = 0;
    if (na != nb) return na ? -1 : 1;
    size_t la = strlen(a), lb = strlen(b);
    int r = la != lb ? (la < lb ? -1 : 1) : strcmp(a, b);
    r = r > 0 ? 1 : r < 0 ? -1 : 0;
    return na ? -r : r;
}
/* rational: an integer or (Rat p q) with integer p, q. */
static int rational(const Sx *v, const char **p, const char **q) {
    if (is_num(v)) { *p = v->text; *q = "1"; return 1; }
    if (v->kind == SX_LIST && v->n == 3 && sx_is_sym(v->items[0], "Rat") && is_num(v->items[1]) && is_num(v->items[2])) {
        *p = v->items[1]->text; *q = v->items[2]->text; return 1;
    }
    return 0;
}

/* request_result */
static const char *request_result(DcAModule *m, const Sx *rq) {
    if (!rq || rq->kind != SX_LIST || !rq->n || rq->items[0]->kind != SX_SYM) return NULL;
    const char *h = rq->items[0]->text;
    const Sx *q = dc_reg_request(h);
    if (q) return dc_reg_str(dc_reg_get(q, "result"));
    DcADecl *d = find_decl(m, h);
    if (d && !strcmp(d->kind, "Method"))
        for (size_t i = 0; i < d->form->n; i++) {
            const Sx *x = d->form->items[i];
            if (sx_head_is(x, "Returns")) return x->n > 1 && x->items[1]->kind == SX_SYM ? x->items[1]->text : NULL;
        }
    return NULL;
}
/* result_type_of_derivation */
static const char *derivation_type(DcAModule *m, const char *name) {
    DcADecl *d = find_decl(m, name);
    if (!d || strcmp(d->kind, "Derive") || d->form->n < 3) return NULL;
    return request_result(m, d->form->items[2]);
}
/* field_type: Value is the result itself; a trailing '?' marks an optional field. */
static const char *field_type(const char *rt, const char *fld, char *buf, size_t n) {
    if (!strcmp(fld, "Value")) return rt;
    if (!rt) return NULL;
    const char *t = dc_reg_str(dc_reg_get(dc_reg_get(dc_reg_result_type(rt), "fields"), fld));
    if (!t) return NULL;
    snprintf(buf, n, "%s", t);
    size_t l = strlen(buf);
    while (l && buf[l - 1] == '?') buf[--l] = 0;
    return buf;
}

/* kind_ok / _kind_ok; kinds is \"A|B|...\" */
static const char *const ARROW_TYPES[] = { "CheckedAbstractionMap", "CheckedGradedArrow", "CheckedLinearArrow",
                                           "CheckedSimulation", "ComposedArrow", "CheckedTransfer", 0 };
static const char *const ARROW_DECLS[] = { "AbstractionMap", "LinearArrow", "Simulation", "Transfer", 0 };
static int in_list(const char *s, const char *const *l) { for (; *l; l++) if (!strcmp(*l, s)) return 1; return 0; }
static int kind_one(const char *k, const char *dk, const char *ft) {
    if ((dk && !strcmp(dk, k)) || (ft && !strcmp(ft, k))) return 1;
    return !strcmp(k, "Arrow") && ((ft && in_list(ft, ARROW_TYPES)) || (dk && in_list(dk, ARROW_DECLS)));
}
static int kind_ok_raw(const char *kinds, const char *dk, const char *ft) {
    char b[512]; snprintf(b, sizeof b, "%s", kinds);
    for (char *s = b, *e; s; s = e) {
        e = strchr(s, '|'); if (e) *e++ = 0;
        if (kind_one(s, dk, ft)) return 1;
    }
    return 0;
}
static int kind_ok(const char *kinds, const char *dk, const char *ft) {
    const Sx *spec = dk ? dc_reg_decl(dk) : NULL;
    const char *dec = spec ? dc_reg_str(dc_reg_get(spec, "declares")) : NULL;
    if (dec && strcmp(dec, dk) && kind_ok_raw(kinds, dec, ft)) return 1;
    return kind_ok_raw(kinds, dk, ft);
}

static int cmp_str(const void *x, const void *y) { return strcmp(*(char *const *)x, *(char *const *)y); }
static void check_expr(Ctx *c, const Sx *x);

/* check_ref */
static void check_ref(Ctx *c, const Sx *val, const char *kinds) {
    char b[512], sb[512], fb[256];
    if (val->kind != SX_LIST) {
        const char *s = key_of(val, b, sizeof b);
        if (s[0] == '$') return;              /* parameter of a schema or method; checked at invocation */
        DcADecl *d = find_decl(c->m, s);
        if (!d) { cerr(c, val, "undeclared name %s (expected %s)", s, kinds); return; }
        if (!strcmp(d->kind, "Derive")) {
            const char *rt = derivation_type(c->m, s);
            if (!kind_ok(kinds, NULL, rt)) cerr(c, val, "%s is a derivation of type %s, expected %s", s, rt ? rt : "None", kinds);
            return;
        }
        if (!kind_ok(kinds, d->kind, NULL)) cerr(c, val, "%s is a %s, expected %s", s, d->kind, kinds);
        return;
    }
    if (sx_head_is(val, "Output")) {
        if (val->n != 3) { cerr(c, val, "Output needs a source and a field: %s", shw(val, b, sizeof b)); return; }
        const Sx *src = val->items[1], *fl = val->items[2];
        const char *sn = key_of(src, sb, sizeof sb), *rt;
        if (src->kind == SX_SYM && sn[0] == '$') {
            rt = res_get(c, sn);
            if (!rt) { cerr(c, val, "Output from unbound result variable %s", sn); return; }
        } else {
            DcADecl *d = find_decl(c->m, sn);
            if (!d || strcmp(d->kind, "Derive")) { cerr(c, val, "Output from %s, which is not a derivation", sn); return; }
            rt = derivation_type(c->m, sn);
        }
        const char *ft = fl->kind == SX_SYM ? field_type(rt, fl->text, fb, sizeof fb) : NULL;
        if (!ft) {
            const Sx *fs = rt ? dc_reg_get(dc_reg_result_type(rt), "fields") : NULL;
            size_t nf = fs && fs->n ? fs->n - 1 : 0;
            char **names = xm((nf ? nf : 1) * sizeof *names), av[600] = "";
            for (size_t i = 0; i < nf; i++) names[i] = fs->items[i + 1]->items[0]->text;
            qsort(names, nf, sizeof *names, cmp_str);
            for (size_t i = 0; i < nf; i++) { if (i) strncat(av, ", ", sizeof av - strlen(av) - 1); strncat(av, names[i], sizeof av - strlen(av) - 1); }
            free(names);
            cerr(c, val, "result %s has no field %s (available: Value, %s)", rt ? rt : "None", key_of(fl, b, sizeof b), av);
            return;
        }
        if (!kind_ok(kinds, NULL, ft)) cerr(c, val, "(Output %s %s) has type %s, expected %s", sn, key_of(fl, b, sizeof b), ft, kinds);
        return;
    }
    cerr(c, val, "expected a reference to %s, found %s", kinds, shw(val, b, sizeof b));
}

/* check_value: one argument or field value against its registry type. */
static void check_value(Ctx *c, const Sx *val, const char *typ, const char *what) {
    char b[512]; const char *p, *q;
    if (!strcmp(typ, "stable-or-horizon")) { if (sx_is_sym(val, "Stable")) return; typ = "horizon"; }
    if (!strcmp(typ, "rat01")) {
        if (!rational(val, &p, &q) || num_cmp(q, "0") <= 0 || num_cmp("0", p) > 0 || num_cmp(p, q) > 0)
            cerr(c, val, "%s: expected a rational in [0,1], found %s", what, shw(val, b, sizeof b));
    } else if (!strcmp(typ, "discount")) {
        if (!rational(val, &p, &q) || num_cmp(q, "0") <= 0 || num_cmp("0", p) >= 0 || num_cmp(p, q) > 0)
            cerr(c, val, "%s: expected a discount in (0,1], found %s", what, shw(val, b, sizeof b));
    } else if (!strcmp(typ, "rat")) {
        if (!rational(val, &p, &q)) cerr(c, val, "%s: expected a rational, found %s", what, shw(val, b, sizeof b));
    } else if (!strcmp(typ, "nat")) {
        if (!is_num(val) || val->text[0] == '-' ) {
            if (!(is_num(val) && num_cmp(val->text, "0") >= 0))
                cerr(c, val, "%s: expected a natural number, found %s", what, shw(val, b, sizeof b));
        }
    } else if (!strcmp(typ, "horizon")) {
        int ok = sx_is_sym(val, "AllFiniteWords") || (sx_head_is(val, "Steps") && val->n == 2 && is_num(val->items[1]));
        if (!ok) cerr(c, val, "%s: expected AllFiniteWords or (Steps k), found %s", what, shw(val, b, sizeof b));
    } else if (!strcmp(typ, "budget")) {
        if (!(val->kind == SX_LIST && val->n == 2 && is_num(val->items[1])))
            cerr(c, val, "%s: expected (Unit k), found %s", what, shw(val, b, sizeof b));
    } else if (!strcmp(typ, "selector")) {
        if (sx_is_sym(val, "Center") || sx_is_sym(val, "First")) return;
        if (sx_head_is(val, "Choose") && val->n == 2) { check_ref(c, val->items[1], "Map"); return; }
        cerr(c, val, "%s: expected Center, First or (Choose map), found %s", what, shw(val, b, sizeof b));
    } else if (!strncmp(typ, "enum:", 5)) {
        int ok = 0;
        if (val->kind == SX_SYM) {
            char t[512]; snprintf(t, sizeof t, "%s", typ + 5);
            for (char *s = t, *e; s && !ok; s = e) { e = strchr(s, '|'); if (e) *e++ = 0; ok = !strcmp(s, val->text); }
        }
        if (!ok) cerr(c, val, "%s: expected one of %s, found %s", what, typ + 5, shw(val, b, sizeof b));
    } else if (!strncmp(typ, "ref:", 4)) {
        check_ref(c, val, typ + 4);
    } else if (!strcmp(typ, "word")) {
        if (!sx_head_is(val, "Do")) cerr(c, val, "%s: expected (Do a ...), found %s", what, shw(val, b, sizeof b));
        else for (size_t i = 1; i < val->n; i++)
            if (val->items[i]->kind == SX_LIST || !dc_ss_has(&c->m->labels, key_of(val->items[i], b, sizeof b)))
                cerr(c, val->items[i], "%s: unknown action label %s", what, key_of(val->items[i], b, sizeof b));
    } else if (!strcmp(typ, "pair")) {
        if (!(sx_head_is(val, "Pair") && val->n == 3)) cerr(c, val, "%s: expected (Pair a b), found %s", what, shw(val, b, sizeof b));
        else check_expr(c, val);
    } else if (!strcmp(typ, "grade")) {
        const char *p2, *q2;
        if (!(sx_head_is(val, "Grade") && val->n == 3 && rational(val->items[1], &p, &q) && rational(val->items[2], &p2, &q2)))
            cerr(c, val, "%s: expected (Grade L eta), found %s", what, shw(val, b, sizeof b));
    } else if (!strcmp(typ, "element")) {
        if (!(val->kind != SX_LIST && (dc_ss_has(&c->m->elements, key_of(val, b, sizeof b)) || is_num(val))))
            cerr(c, val, "%s: %s is not a declared element", what, shw(val, b, sizeof b));
    } else if (!strcmp(typ, "name")) {
        if (val->kind == SX_LIST) cerr(c, val, "%s: expected a name, found %s", what, shw(val, b, sizeof b));
    } else if (!strcmp(typ, "expr") || !strcmp(typ, "predicate") || !strcmp(typ, "names") || !strcmp(typ, "request") || !strcmp(typ, "property")) {
        check_expr(c, val);
    } else cerr(c, val, "%s: unknown registry type %s", what, typ);
}

/* ------------------------------------------------------------ part 3: expressions and requests */
/* known_atom */
static int known_atom(Ctx *c, const Sx *x) {
    char b[512];
    if (x->kind == SX_STR || is_num(x)) return 1;
    const char *a = key_of(x, b, sizeof b);
    if (a[0] == '$') return 1;
    DcAModule *m = c->m;
    if (find_decl(m, a) || dc_ss_has(&m->elements, a) || dc_ss_has(&m->labels, a) || dc_ss_has(&m->fields, a)) return 1;
    static const char *const keys[] = { "constants", "builtin_types", "primitives", "type_constructors", 0 };
    for (int i = 0; keys[i]; i++) if (lib_has(m, keys[i], a)) return 1;
    return dc_reg_request(a) || dc_reg_decl(a) || dc_reg_result_type(a);
}

static const char OUTPUT_KINDS[] = "Machine|Representation|Arrow|Tolerance|Relation|KernelHive|Transfer|Map|Scalar|"
    "CheckedImplementationContract|Certificate|DefectMeasurement|PolicyValue|AveragedModel|"
    "InvarianceResult|ExactAbstraction|Refinement|Partition|Rational";

static void check_request(Ctx *c, const Sx *rq);

static void res_put(Ctx *c, const char *v, const char *rt) {
    grow((void **)&c->res, &c->capres, c->nres, sizeof *c->res);
    c->res[c->nres].var = xs(v); c->res[c->nres].rt = rt; c->nres++;
}

/* check_expr */
static void check_expr(Ctx *c, const Sx *x) {
    char b[512];
    if (x->kind != SX_LIST) {
        if (!known_atom(c, x)) cerr(c, x, "undeclared name %s", key_of(x, b, sizeof b));
        return;
    }
    if (!x->n) return;
    const Sx *h = x->items[0];
    const char *hd = h->kind == SX_SYM ? h->text : NULL;
    if (hd && (!strcmp(hd, "Tokens") || !strcmp(hd, "Query") || !strcmp(hd, "Digest"))) {
        if (!strcmp(hd, "Query") && x->n > 1) check_expr(c, x->items[1]);
        return;
    }
    if (hd && !strcmp(hd, "Output")) { check_ref(c, x, OUTPUT_KINDS); return; }
    DcADecl *d = hd ? find_decl(c->m, hd) : NULL;
    if (hd && (dc_reg_request(hd) || (d && !strcmp(d->kind, "Method")))) { check_request(c, x); return; }
    if (hd && dc_reg_decl(hd) && !dc_reg_request(hd)) {
        const Sx *df = dc_reg_get(dc_reg_decl(hd), "fields");
        for (size_t i = 1; i < x->n; i++) {
            const Sx *y = x->items[i];
            if (y->kind == SX_LIST && y->n && y->items[0]->kind == SX_SYM && dc_reg_get(df, y->items[0]->text))
                for (size_t k = 1; k < y->n; k++) check_expr(c, y->items[k]);
            else check_expr(c, y);
        }
        return;
    }
    if (hd && !strcmp(hd, "LetResult")) {
        if (x->n != 4 || x->items[1]->kind != SX_SYM || x->items[1]->text[0] != '$') {
            cerr(c, x, "LetResult needs $var, request and body: %s", shw(x, b, sizeof b)); return;
        }
        check_request(c, x->items[2]);
        res_put(c, x->items[1]->text, request_result(c->m, x->items[2]));
        check_expr(c, x->items[3]);
        return;
    }
    if (h->kind != SX_LIST && !known_atom(c, h)) {
        char s[61]; shw(x, b, sizeof b); snprintf(s, sizeof s, "%.60s", b);
        cerr(c, h, "unknown head %s in %s", key_of(h, b, sizeof b) == b ? b : h->text, s);
    }
    for (size_t i = 1; i < x->n; i++) check_expr(c, x->items[i]);
}

/* positional entry (List "name" "type" ["variadic"]) */
static const char *pos_name(const Sx *e) { return e && e->n > 1 ? dc_reg_str(e->items[1]) : NULL; }
static const char *pos_type(const Sx *e) { return e && e->n > 2 ? dc_reg_str(e->items[2]) : NULL; }

/* check_request */
static void check_request(Ctx *c, const Sx *rq) {
    char b[512], what[300];
    if (rq->kind != SX_LIST || !rq->n || rq->items[0]->kind != SX_SYM) { cerr(c, rq, "unregistered request %s", shw(rq, b, sizeof b)); return; }
    const char *head = rq->items[0]->text;
    const Sx *spec = dc_reg_request(head);
    DcAModule *m = c->m;
    if (!spec) {
        DcADecl *d = find_decl(m, head);
        if (d && !strcmp(d->kind, "Method")) {
            const Sx *pr = sx_find(d->form, "Parameters", 0);
            size_t n = pr ? pr->n - 1 : 0;
            if (rq->n - 1 != n) cerr(c, rq, "method %s takes %zu argument(s)", head, n);
            for (size_t i = 1; i < rq->n; i++) check_expr(c, rq->items[i]);
            return;
        }
        cerr(c, rq, "unregistered request %s", head); return;
    }
    const char *lib = dc_reg_str(dc_reg_get(spec, "library"));
    if (lib && !dc_ss_has(&m->libraries, lib)) cerr(c, rq, "%s belongs to library %s, not imported by %s", head, lib, m->name);
    if (!m->dynamics || !dc_reg_list_has(dc_reg_get(spec, "profiles"), m->dynamics))
        cerr(c, rq, "%s does not support %s dynamics", head, m->dynamics ? m->dynamics : "None");
    if (!m->carriers || !dc_reg_list_has(dc_reg_get(spec, "carriers"), m->carriers))
        cerr(c, rq, "%s does not support %s carriers", head, m->carriers ? m->carriers : "None");
    const Sx *ps = dc_reg_get(spec, "positional"), *ka = dc_reg_get(spec, "args");
    size_t np = ps && ps->n ? ps->n - 1 : 0;
    const Sx *last = np ? ps->items[np] : NULL;
    int variadic = last && last->n > 3 && dc_reg_str(last->items[3]) && !strcmp(dc_reg_str(last->items[3]), "variadic");
    size_t na = rq->n - 1, i = 0, npos = 0;
    #define ARG(k) (rq->items[(k) + 1])
    #define KEYED(y) ((y)->kind == SX_LIST && (y)->n && (y)->items[0]->kind == SX_SYM && dc_reg_get(ka, (y)->items[0]->text))
    while (i < na && !(KEYED(ARG(i)) && (npos >= np || !variadic))) {
        if (!variadic && npos == np) break;
        npos++; i++;
    }
    if (variadic) {
        if (npos < 1) cerr(c, rq, "%s needs at least one %s", head, pos_name(last));
        snprintf(what, sizeof what, "%s %s", head, pos_name(last));
        for (size_t k = 0; k < npos; k++) check_value(c, ARG(k), pos_type(last), what);
    } else {
        if (npos != np) cerr(c, rq, "%s expects %zu positional argument(s), found %zu", head, np, npos);
        for (size_t k = 0; k < npos && k < np; k++) {
            snprintf(what, sizeof what, "%s %s", head, pos_name(ps->items[k + 1]));
            check_value(c, ARG(k), pos_type(ps->items[k + 1]), what);
        }
    }
    DcStrSet seen = {0};
    for (size_t k = i; k < na; k++) {
        const Sx *a = ARG(k);
        if (!KEYED(a)) {
            size_t nk = ka && ka->n ? ka->n - 1 : 0;
            char **names = xm((nk ? nk : 1) * sizeof *names), reg[600] = "", s50[51];
            for (size_t j = 0; j < nk; j++) names[j] = ka->items[j + 1]->items[0]->text;
            qsort(names, nk, sizeof *names, cmp_str);
            for (size_t j = 0; j < nk; j++) { if (j) strncat(reg, ", ", sizeof reg - strlen(reg) - 1); strncat(reg, names[j], sizeof reg - strlen(reg) - 1); }
            free(names);
            snprintf(s50, sizeof s50, "%.50s", shw(a, b, sizeof b));
            cerr(c, a, "%s: unknown argument %s (registered: %s)", head, s50, nk ? reg : "none");
            continue;
        }
        const char *an = a->items[0]->text;
        if (dc_ss_has(&seen, an)) cerr(c, a, "%s: duplicate argument %s", head, an);
        dc_ss_add(&seen, an);
        const char *ty = dc_reg_str(dc_reg_get(dc_reg_get(ka, an), "type"));
        if (!ty) ty = "expr";
        snprintf(what, sizeof what, "%s %s", head, an);
        if (!strcmp(ty, "grade") || !strcmp(ty, "pair")) { check_value(c, a, ty, what); continue; }
        if (a->n != 2) {
            if (!strcmp(ty, "names")) { for (size_t j = 1; j < a->n; j++) check_expr(c, a->items[j]); continue; }
            cerr(c, a, "%s: argument %s takes one value", head, an); continue;
        }
        check_value(c, a->items[1], ty, what);
    }
    for (size_t j = 1; ka && j < ka->n; j++) {
        const Sx *e = ka->items[j];
        const char *an = dc_reg_str(e->items[0]);
        if (an && dc_reg_true(dc_reg_get(e->items[1], "required")) && !dc_ss_has(&seen, an))
            cerr(c, rq, "%s: missing required argument %s", head, an);
    }
    dc_ss_free(&seen);
    #undef ARG
    #undef KEYED
}

/* ------------------------------------------------------------ part 4: hygiene */
static int is_binder(const char *h) {
    const Sx *libs = reg_section("libraries");
    for (size_t i = 1; libs && i < libs->n; i++)
        if (dc_reg_list_has(dc_reg_get(libs->items[i]->items[1], "binders"), h)) return 1;
    return 0;
}
static int is_var(const Sx *x) { return x && x->kind == SX_SYM && x->text[0] == '$'; }
/* collect_vars */
static void collect_vars(const Sx *x, DcStrSet *out) {
    if (is_var(x)) dc_ss_add(out, x->text);
    else if (x->kind == SX_LIST) for (size_t i = 0; i < x->n; i++) collect_vars(x->items[i], out);
}
/* bound_vars */
static void bound_vars(const Sx *x, DcStrSet *out) {
    if (x->kind != SX_LIST || !x->n) return;
    const Sx *h = x->items[0];
    const char *hd = h->kind == SX_SYM ? h->text : NULL;
    if (hd && is_binder(hd) && x->n > 1 && x->items[1]->kind != SX_LIST) dc_ss_add(out, x->items[1]->text);
    if (hd && !strcmp(hd, "Body") && x->n >= 2 && x->items[1]->kind == SX_LIST)
        for (size_t i = 0; i < x->items[1]->n; i++) if (is_var(x->items[1]->items[i])) dc_ss_add(out, x->items[1]->items[i]->text);
    if (hd && !strcmp(hd, "Cases"))
        for (size_t i = 1; i < x->n; i++) if (x->items[i]->kind == SX_LIST && x->items[i]->n) collect_vars(x->items[i]->items[0], out);
    if (hd && (!strcmp(hd, "For") || !strcmp(hd, "LetResult")) && x->n > 1 && x->items[1]->kind != SX_LIST)
        dc_ss_add(out, x->items[1]->text);
    if (hd && (!strcmp(hd, "Parameters") || !strcmp(hd, "Lambda")))
        for (size_t i = 1; i < x->n; i++) {
            const Sx *b = x->items[i];
            if (b->kind != SX_LIST) continue;
            if (b->n && is_var(b->items[0])) dc_ss_add(out, b->items[0]->text);
            for (size_t k = 0; k < b->n; k++)
                if (b->items[k]->kind == SX_LIST && b->items[k]->n && is_var(b->items[k]->items[0])) dc_ss_add(out, b->items[k]->items[0]->text);
        }
    if (hd && !strcmp(hd, "Query") && x->n > 2) collect_vars(x->items[2], out);
    for (size_t i = 0; i < x->n; i++) bound_vars(x->items[i], out);
}
/* first occurrence of variable v in x, for the location */
static const Sx *find_var(const Sx *x, const char *v) {
    if (is_var(x) && !strcmp(x->text, v)) return x;
    if (x->kind == SX_LIST) for (size_t i = 0; i < x->n; i++) { const Sx *r = find_var(x->items[i], v); if (r) return r; }
    return NULL;
}
/* check_hygiene */
static void check_hygiene(Ctx *c, const Sx *item) {
    DcStrSet bound = {0}, used = {0};
    bound_vars(item, &bound); collect_vars(item, &used);
    if (used.n) qsort(used.v, used.n, sizeof *used.v, cmp_str);
    for (size_t i = 0; i < used.n; i++)
        if (!dc_ss_has(&bound, used.v[i])) cerr(c, find_var(item, used.v[i]), "unbound variable %s", used.v[i]);
    dc_ss_free(&bound); dc_ss_free(&used);
}

/* ------------------------------------------------------------ part 4b: declarations and bodies */
static int body_head_ok(const char *kind, const char *h) {
    static const char *const CE[] = { "Enum", "Product", "All", "Subset", "Reach", "Query", 0 };
    static const char *const MB[] = { "Cases", "Body", "Table", "Choice", "Query", 0 };
    static const char *const TB[] = { "SymmetricTable", "DirectedTable", "Pullback", "OneMinusAbsoluteDifference", "Discrete", "Trivial", 0 };
    static const char *const MS[] = { "Uniform", "Masses", "Product", 0 };
    const char *const *l = !strcmp(kind, "carrier-expr") ? CE : !strcmp(kind, "map-body") ? MB
                         : !strcmp(kind, "tolerance-body") ? TB : !strcmp(kind, "measure-body") ? MS : NULL;
    if (l && in_list(h, l)) return 1;
    return dc_reg_list_has(dc_reg_get(reg_section("body_heads_added"), kind), h);   /* e.g. ex1: tolerance Meet */
}
/* check_body */
static void check_body(Ctx *c, const char *kind, const Sx *x) {
    char b[512], s[61];
    if (!strcmp(kind, "fields")) {
        if (!(x->kind == SX_LIST && x->n == 2)) cerr(c, x, "record field must be (name type): %s", shw(x, b, sizeof b));
        return;
    }
    if (!(x->kind == SX_LIST && x->n && x->items[0]->kind == SX_SYM && body_head_ok(kind, x->items[0]->text))) {
        snprintf(s, 51, "%.50s", shw(x, b, sizeof b));
        cerr(c, x, "expected a %s, found %s", kind, s); return;
    }
    if (sx_is_sym(x->items[0], "Reach")) {
        DcADecl *d = x->n > 1 && x->items[1]->kind == SX_SYM ? find_decl(c->m, x->items[1]->text) : NULL;
        if (x->n < 3 || !d || strcmp(d->kind, "Machine")) cerr(c, x, "Reach needs a declared machine: %s", shw(x, b, sizeof b));
        int frm = 0;
        for (size_t i = 2; i < x->n; i++) if (sx_head_is(x->items[i], "From")) frm = 1;
        if (!frm) cerr(c, x, "Reach needs (From e+)");
        return;
    }
    if (sx_is_sym(x->items[0], "Enum")) return;
    check_expr(c, x);
}
/* map_instance_ok */
static void map_instance_ok(Ctx *c, const Sx *mp) {
    char b[512], s[61];
    if (mp->kind != SX_LIST) { check_ref(c, mp, "Map|TransitionKernel"); return; }
    if (mp->n && mp->items[0]->kind == SX_SYM) {
        DcADecl *d = find_decl(c->m, mp->items[0]->text);
        if (d && !strcmp(d->kind, "Map") && sx_find(d->form, "Parameters", 0)) {
            for (size_t i = 1; i < mp->n; i++) check_expr(c, mp->items[i]);
            return;
        }
    }
    snprintf(s, sizeof s, "%.60s", shw(mp, b, sizeof b));
    cerr(c, mp, "expected a map or an instance of a parameterized map, found %s", s);
}
static int have_binders(void) {
    const Sx *libs = reg_section("libraries");
    for (size_t i = 1; libs && i < libs->n; i++) { const Sx *v = dc_reg_get(libs->items[i]->items[1], "binders"); if (v && v->n > 1) return 1; }
    return 0;
}
/* check_machine_items */
static void check_machine_items(Ctx *c, const Sx *item) {
    char b[512], s[61];
    for (size_t i = 2; i < item->n; i++) {
        const Sx *x = item->items[i];
        if (!(x->kind == SX_LIST && x->n && x->items[0]->kind == SX_SYM)) continue;
        const char *hd = x->items[0]->text;
        if (strcmp(hd, "Observe") && strcmp(hd, "Action") && strcmp(hd, "Merge") && strcmp(hd, "Available")) continue;
        const Sx *core[2] = {0}; size_t ncore = 0, nfor = 0;
        for (size_t k = 1; k < x->n; k++) {
            const Sx *y = x->items[k];
            if (sx_head_is(y, "For") || sx_head_is(y, "Values")) { if (sx_head_is(y, "For")) nfor++; continue; }
            if (!strcmp(hd, "Available")) { check_expr(c, y); continue; }
            if (ncore < 2) core[ncore] = y;
            ncore++;
        }
        if (!strcmp(hd, "Available")) continue;
        if (ncore != 2) { snprintf(s, sizeof s, "%.60s", shw(x, b, sizeof b)); cerr(c, x, "%s needs a label and a map: %s", hd, s); continue; }
        for (size_t k = 1; k < x->n; k++) {
            const Sx *f = x->items[k];
            if (!sx_head_is(f, "For")) continue;
            if (!(f->n == 3 && is_var(f->items[1]))) cerr(c, f, "For needs a variable and a carrier: %s", shw(f, b, sizeof b));
            else {
                DcADecl *d = f->items[2]->kind == SX_SYM ? find_decl(c->m, f->items[2]->text) : NULL;
                if (!d || strcmp(d->kind, "Carrier")) cerr(c, f, "For ranges over an undeclared carrier %s", key_of(f->items[2], b, sizeof b));
            }
        }
        if (nfor && !have_binders()) cerr(c, x, "For on a machine entry needs the Families library");
        if (core[0]->kind == SX_LIST) for (size_t k = 1; k < core[0]->n; k++) check_expr(c, core[0]->items[k]);
        map_instance_ok(c, core[1]);
        for (size_t k = 1; k < x->n; k++)
            if (sx_head_is(x->items[k], "Values") && x->items[k]->n > 1) check_ref(c, x->items[k]->items[1], "Tolerance");
    }
}
static void ctx_init(Ctx *c, DcAdmission *a, DcAModule *m, const Sx *at, const char *fmt, ...) {
    memset(c, 0, sizeof *c); c->a = a; c->m = m; c->at = at;
    va_list ap; va_start(ap, fmt); vsnprintf(c->where, sizeof c->where, fmt, ap); va_end(ap);
}
static void ctx_free(Ctx *c) {
    for (size_t i = 0; i < c->nres; i++) free(c->res[i].var);
    free(c->res); dc_ss_free(&c->bound);
}
/* check_declaration */
static void check_declaration(DcAdmission *a, DcAModule *m, const DcADecl *d) {
    char b[512], what[300], s[51];
    const Sx *spec = dc_reg_decl(d->kind), *item = d->form;
    Ctx c; ctx_init(&c, a, m, item, "%s:%s.%s", a->fname, m->name, d->name);
    check_hygiene(&c, item);
    const Sx *pos = dc_reg_get(spec, "positional"), *fields = dc_reg_get(spec, "fields");
    const char *body = dc_reg_str(dc_reg_get(spec, "body"));
    size_t np = pos && pos->n ? pos->n - 1 : 0;
    for (size_t j = 1; j < np && 1 + j < item->n; j++) {
        const Sx *val = item->items[1 + j];
        const char *pt = pos_type(pos->items[j + 1]), *pn = pos_name(pos->items[j + 1]);
        if (pt && !strcmp(pt, "request")) {
            if (val->kind != SX_LIST || !val->n) cerr(&c, val, "Derive needs a request");
            else check_request(&c, val);
        } else if (pt && strcmp(pt, "name")) {
            snprintf(what, sizeof what, "%s %s", d->kind, pn ? pn : "?");
            check_value(&c, val, pt, what);
        }
    }
    DcStrSet seen = {0};
    int body_seen = 0;
    for (size_t i = 1 + np; i < item->n; i++) {
        const Sx *x = item->items[i];
        const Sx *f = x->kind == SX_LIST && x->n && x->items[0]->kind == SX_SYM ? dc_reg_get(fields, x->items[0]->text) : NULL;
        if (f) {
            const char *fn = x->items[0]->text, *ft = dc_reg_str(dc_reg_get(f, "type"));
            if (dc_ss_has(&seen, fn) && !dc_reg_true(dc_reg_get(f, "repeatable"))) cerr(&c, x, "duplicate field %s", fn);
            dc_ss_add(&seen, fn);
            if (!ft) ft = "expr";
            if (!strcmp(ft, "expr") || !strcmp(ft, "names") || !strcmp(ft, "predicate")) {
                for (size_t k = 1; k < x->n; k++) check_expr(&c, x->items[k]);
            } else if (x->n == 2) {
                snprintf(what, sizeof what, "%s %s", d->kind, fn);
                check_value(&c, x->items[1], ft, what);
            } else cerr(&c, x, "field %s takes one value", fn);
        } else if (body && (!body_seen || !strcmp(body, "fields"))) {
            body_seen = 1;
            check_body(&c, body, x);
        } else {
            snprintf(s, sizeof s, "%.50s", shw(x, b, sizeof b));
            cerr(&c, x, "unknown field %s for %s", s, d->kind);
        }
    }
    for (size_t j = 1; fields && j < fields->n; j++) {
        const char *fn = dc_reg_str(fields->items[j]->items[0]);
        if (fn && dc_reg_true(dc_reg_get(fields->items[j]->items[1], "required")) && !dc_ss_has(&seen, fn))
            cerr(&c, item, "missing required field %s", fn);
    }
    if (body && strcmp(body, "fields") && !body_seen) cerr(&c, item, "%s needs a %s", d->kind, body);
    if (!strcmp(d->kind, "Machine") || !strcmp(d->kind, "MethodSystem")) check_machine_items(&c, item);
    dc_ss_free(&seen); ctx_free(&c);
}

/* ------------------------------------------------------------ part 5: module rules (check_module_rules) */
static void sym_atoms(const Sx *x, const DcAModule *m, const char *kind, DcStrSet *out) {
    if (x->kind == SX_SYM) { DcADecl *d = find_decl(m, x->text); if (d && !strcmp(d->kind, kind)) dc_ss_add(out, x->text); }
    else if (x->kind == SX_LIST) for (size_t i = 0; i < x->n; i++) sym_atoms(x->items[i], m, kind, out);
}
/* pattern variables with repeats, as printed keys */
static void pattern_vars(const Sx *x, char ***v, size_t *n, size_t *cap) {
    if (is_var(x)) { grow((void **)v, cap, *n, sizeof **v); (*v)[(*n)++] = x->text; }
    else if (x->kind == SX_LIST) for (size_t i = 0; i < x->n; i++) pattern_vars(x->items[i], v, n, cap);
}
static int has_dup(char **v, size_t n) {
    for (size_t i = 0; i < n; i++) for (size_t k = i + 1; k < n; k++) if (!strcmp(v[i], v[k])) return 1;
    return 0;
}
typedef struct { char *node; DcStrSet out; } DcEdge;
typedef struct { DcEdge *v; size_t n, cap; } DcGraph;
static DcStrSet *g_node(DcGraph *g, const char *n) {
    for (size_t i = 0; i < g->n; i++) if (!strcmp(g->v[i].node, n)) return &g->v[i].out;
    grow((void **)&g->v, &g->cap, g->n, sizeof *g->v);
    memset(&g->v[g->n], 0, sizeof g->v[g->n]); g->v[g->n].node = xs(n);
    return &g->v[g->n++].out;
}
static const DcStrSet *g_get(const DcGraph *g, const char *n) {
    for (size_t i = 0; i < g->n; i++) if (!strcmp(g->v[i].node, n)) return &g->v[i].out;
    return NULL;
}
static void g_free(DcGraph *g) {
    for (size_t i = 0; i < g->n; i++) { free(g->v[i].node); dc_ss_free(&g->v[i].out); }
    free(g->v); memset(g, 0, sizeof *g);
}
/* _find_cycle: DFS in sorted order; returns 1 and fills path text */
typedef struct { DcStrSet grey, black; char **path; size_t np, cap; } Dfs;
static int visit(const DcGraph *g, Dfs *s, const char *n, char *out, size_t on) {
    dc_ss_add(&s->grey, n);
    grow((void **)&s->path, &s->cap, s->np, sizeof *s->path); s->path[s->np++] = (char *)n;
    const DcStrSet *e = g_get(g, n);
    size_t k = e ? e->n : 0;
    char **nb = xm((k ? k : 1) * sizeof *nb);
    for (size_t i = 0; i < k; i++) nb[i] = e->v[i];
    qsort(nb, k, sizeof *nb, cmp_str);
    for (size_t i = 0; i < k; i++) {
        const char *m = nb[i];
        if (dc_ss_has(&s->grey, m) && !dc_ss_has(&s->black, m)) {
            size_t st = 0; while (strcmp(s->path[st], m)) st++;
            out[0] = 0;
            for (size_t j = st; j < s->np; j++) { strncat(out, s->path[j], on - strlen(out) - 1); strncat(out, " -> ", on - strlen(out) - 1); }
            strncat(out, m, on - strlen(out) - 1);
            free(nb); return 1;
        }
        if (!dc_ss_has(&s->grey, m) && visit(g, s, m, out, on)) { free(nb); return 1; }
    }
    free(nb); dc_ss_add(&s->black, n); s->np--; return 0;
}
static int find_cycle(const DcGraph *g, char *out, size_t on) {
    char **ns = xm((g->n ? g->n : 1) * sizeof *ns);
    for (size_t i = 0; i < g->n; i++) ns[i] = g->v[i].node;
    qsort(ns, g->n, sizeof *ns, cmp_str);
    Dfs s; memset(&s, 0, sizeof s);
    int r = 0;
    for (size_t i = 0; i < g->n && !r; i++) if (!dc_ss_has(&s.grey, ns[i])) r = visit(g, &s, ns[i], out, on);
    free(ns); dc_ss_free(&s.grey); dc_ss_free(&s.black); free(s.path);
    return r;
}
/* _resolve_type */
static const Sx *resolve_type(const DcAModule *m, const Sx *t, int depth) {
    if (t->kind != SX_SYM || depth > 32) return t;
    DcADecl *d = find_decl(m, t->text);
    if (d && !strcmp(d->kind, "Type") && d->form->n > 2) return resolve_type(m, d->form->items[2], depth + 1);
    return t;
}
/* decimal 2^n into buf (n small enough for buf) */
static void pow2(unsigned n, char *buf, size_t bn) {
    size_t len = 1; buf[0] = 1;                        /* little-endian digits */
    for (unsigned i = 0; i < n && len < bn - 1; i++) {
        int carry = 0;
        for (size_t k = 0; k < len; k++) { int d = buf[k] * 2 + carry; buf[k] = (char)(d % 10); carry = d / 10; }
        if (carry && len < bn - 1) buf[len++] = (char)carry;
    }
    for (size_t k = 0; k < len / 2; k++) { char t = buf[k]; buf[k] = buf[len - 1 - k]; buf[len - 1 - k] = t; }
    for (size_t k = 0; k < len; k++) buf[k] += '0';
    buf[len] = 0;
}
/* _element_ok */
static int element_ok(const DcAModule *m, const Sx *t0, const Sx *e) {
    char b1[512], b2[512];
    const Sx *t = resolve_type(m, t0, 0);
    if (e->kind == SX_SYM) {
        DcADecl *d = find_decl(m, e->text);
        if (d && !strcmp(d->kind, "Const"))
            return d->form->n > 2 && !strcmp(shw(resolve_type(m, d->form->items[2], 0), b1, sizeof b1), shw(t, b2, sizeof b2));
    }
    if (sx_is_sym(t, "Symbol")) return e->kind == SX_SYM && !is_num(e) && e->text[0] != '$';
    if (sx_is_sym(t, "Nat") || sx_is_sym(t, "Int") || sx_is_sym(t, "Bit")) {
        if (!is_num(e)) return 0;
        if (sx_is_sym(t, "Int")) return 1;
        return num_cmp(e->text, "0") >= 0 && (!sx_is_sym(t, "Bit") || num_cmp(e->text, "1") <= 0);
    }
    if (sx_is_sym(t, "Bool")) return sx_is_sym(e, "True") || sx_is_sym(e, "False");
    if (sx_is_sym(t, "Rational") || sx_is_sym(t, "Rational01")) {
        const char *p, *q;
        if (is_num(e)) { p = e->text; q = "1"; }
        else if (sx_head_is(e, "Rat") && e->n == 3 && is_num(e->items[1]) && is_num(e->items[2]) && num_cmp(e->items[2]->text, "0") > 0)
            { p = e->items[1]->text; q = e->items[2]->text; }
        else return 0;
        return sx_is_sym(t, "Rational") || (num_cmp("0", p) <= 0 && num_cmp(p, q) <= 0);
    }
    if (sx_head_is(t, "BitVector") && t->n == 2 && is_num(t->items[1])) {
        if (!is_num(e) || num_cmp(e->text, "0") < 0) return 0;
        if (t->items[1]->text[0] == '-' || strlen(t->items[1]->text) > 4) return 0;
        unsigned w = (unsigned)atoi(t->items[1]->text);
        char *lim = xm(w + 8); pow2(w, lim, w + 8);
        int ok = num_cmp(e->text, lim) < 0; free(lim); return ok;
    }
    if (sx_head_is(t, "Tuple")) {
        if (!(sx_head_is(e, "Tuple") && e->n == t->n)) return 0;
        for (size_t i = 1; i < t->n; i++) if (!element_ok(m, t->items[i], e->items[i])) return 0;
        return 1;
    }
    return 0;
}
static void check_module_rules(DcAdmission *a, DcAModule *m) {
    char b[512], s[61], where[320], cyc[2048];
    DcGraph calls = {0}, deps = {0};
    for (size_t di = 0; di < m->ndecl; di++) {
        const DcADecl *d = &m->decls[di];
        if (!d->own) continue;
        const Sx *it = d->form;
        snprintf(where, sizeof where, "%s:%s.%s", a->fname, m->name, d->name);
        if (!strcmp(d->kind, "Map")) {
            for (size_t i = 2; i < it->n; i++) {
                const Sx *x = it->items[i];
                if (x->kind != SX_LIST || !x->n) continue;
                if (sx_is_sym(x->items[0], "Cases"))
                    for (size_t k = 1; k < x->n; k++) {
                        const Sx *c = x->items[k];
                        if (c->kind != SX_LIST || !c->n) continue;
                        char **v = NULL; size_t n = 0, cap = 0;
                        pattern_vars(c->items[0], &v, &n, &cap);
                        if (has_dup(v, n)) { snprintf(s, sizeof s, "%.60s", shw(c->items[0], b, sizeof b)); diag(a, m->name, c->items[0], where, "nonlinear pattern %s", s); }
                        free(v);
                    }
                if (sx_is_sym(x->items[0], "Body") && x->n > 1 && x->items[1]->kind == SX_LIST) {
                    const Sx *bl = x->items[1];
                    int dup = 0;
                    for (size_t p = 0; p < bl->n && !dup; p++) for (size_t q = p + 1; q < bl->n; q++) if (sx_equal(bl->items[p], bl->items[q])) { dup = 1; break; }
                    if (dup) diag(a, m->name, bl, where, "nonlinear Body binders %s", shw(bl, b, sizeof b));
                }
                if (sx_is_sym(x->items[0], "From") || sx_is_sym(x->items[0], "To")) continue;
                sym_atoms(x, m, "Map", g_node(&calls, d->name));
            }
        } else if (!strcmp(d->kind, "Derive")) {
            DcStrSet *o = g_node(&deps, d->name);
            for (size_t i = 2; i < it->n; i++) sym_atoms(it->items[i], m, "Derive", o);
        } else if (!strcmp(d->kind, "Carrier")) {
            const Sx *of = NULL;
            for (size_t i = 2; i < it->n && !of; i++) if (sx_head_is(it->items[i], "Of") && it->items[i]->n == 2) of = it->items[i];
            for (size_t i = 2; of && i < it->n; i++) {
                const Sx *x = it->items[i];
                if (!sx_head_is(x, "Enum")) continue;
                for (size_t k = 1; k < x->n; k++)
                    if (!element_ok(m, of->items[1], x->items[k])) {
                        char e40[41], tb[512];
                        snprintf(e40, sizeof e40, "%.40s", shw(x->items[k], b, sizeof b));
                        diag(a, m->name, x->items[k], where, "Enum element %s is neither a symbol of a symbol-typed carrier nor a constant of %s",
                             e40, shw(of->items[1], tb, sizeof tb));
                    }
            }
        }
    }
    snprintf(where, sizeof where, "%s:%s", a->fname, m->name);
    if (find_cycle(&calls, cyc, sizeof cyc)) diag(a, m->name, m->form, where, "map-call cycle %s", cyc);
    if (find_cycle(&deps, cyc, sizeof cyc)) diag(a, m->name, m->form, where, "derivation cycle %s", cyc);
    g_free(&calls); g_free(&deps);
}

/* ------------------------------------------------------------ part 6: runs and the file */
/* check_run */
static void check_run(DcAdmission *a, const Sx *form) {
    char b[512], s[61];
    if (!(sx_head_is(form, "dc.run") && form->n == 3)) {
        snprintf(s, sizeof s, "%.60s", shw(form, b, sizeof b));
        diag(a, "", form, a->fname, "run form must be !(dc.run Module request): %s", s); return;
    }
    const char *mn = key_of(form->items[1], b, sizeof b);
    DcAModule *m = dc_admit_find(a, mn);
    if (!m) { diag(a, "", form, a->fname, "run of unknown module %s", mn); return; }
    const Sx *rq = form->items[2];
    char r40[41]; snprintf(r40, sizeof r40, "%.40s", shw(rq, b, sizeof b));
    Ctx c; ctx_init(&c, a, m, rq, "%s:run %s", a->fname, r40);
    if (rq->kind != SX_LIST) {
        DcADecl *d = find_decl(m, key_of(rq, b, sizeof b));
        if (!d || strcmp(d->kind, "Derive")) cerr(&c, rq, "%s is not a derivation of %s", b, m->name);
    } else check_request(&c, rq);
    ctx_free(&c);
}

/* Admit the modules of several parsed files as one universe (check_fixtures.py
 * main: imports resolve across every file of the package). */
static size_t admit_files(const Sx *const *alls, const char *const *fnames, size_t nf, DcAdmission *a, int runs) {
    char b[512], s[51];
    memset(a, 0, sizeof *a);
    for (size_t fi = 0; fi < nf; fi++) {
        const Sx *all = alls[fi]; const char *fname = fnames[fi];
        a->fname = fname;
        for (size_t i = 0; i < all->n; i++) {
            const Sx *f = all->items[i];
            if (sx_is_sym(f, "!") && i + 1 < all->n) { i++; continue; }
            if (!(sx_head_is(f, "DC.Module") && f->n >= 3)) {
                snprintf(s, sizeof s, "%.50s", shw(f, b, sizeof b));
                diag(a, "", f, fname, "top-level form is not a module: %s", s); continue;
            }
            const char *mn = key_of(f->items[1], b, sizeof b);
            DcAModule *m = dc_admit_find(a, mn);
            if (m) diag(a, mn, f, fname, "duplicate module %s", mn);
            else {
                grow((void **)&a->mods, &a->capmod, a->nmod, sizeof *a->mods);
                m = &a->mods[a->nmod++]; memset(m, 0, sizeof *m); m->name = xs(mn);
            }
            m->form = f; m->fname = fname;   /* the checker keeps the later module */
        }
    }
    for (size_t i = 0; i < a->nmod; i++) { a->fname = a->mods[i].fname; scan_module(a, &a->mods[i]); }
    for (size_t i = 0; i < a->nmod; i++) { a->fname = a->mods[i].fname; resolve_imports(a, &a->mods[i]); }
    for (size_t i = 0; i < a->nmod; i++) {
        DcAModule *m = &a->mods[i];
        a->fname = m->fname;
        for (size_t k = 0; k < m->ndecl; k++) if (m->decls[k].own) check_declaration(a, m, &m->decls[k]);
        check_module_rules(a, m);
    }
    for (size_t fi = 0; runs && fi < nf; fi++) {
        const Sx *all = alls[fi]; a->fname = fnames[fi];
        for (size_t i = 0; i + 1 < all->n; i++)
            if (sx_is_sym(all->items[i], "!")) { check_run(a, all->items[i + 1]); i++; }
    }
    a->fname = nf ? fnames[0] : NULL;
    return a->diag.n;
}

size_t dc_admit_files(const Sx *const *alls, const char *const *fnames, size_t nf, DcAdmission *a) {
    return admit_files(alls, fnames, nf, a, 1);
}
size_t dc_admit_file(const Sx *all, const char *fname, DcAdmission *a) {
    return admit_files(&all, &fname, 1, a, 1);
}
/* Modules only: run forms are left to dc_admit_run, one at a time, so a bad
 * run does not make the other runs of its module InvalidInput. */
size_t dc_admit_modules(const Sx *all, const char *fname, DcAdmission *a) {
    return admit_files(&all, &fname, 1, a, 0);
}
size_t dc_admit_run(DcAdmission *a, const Sx *run) {
    size_t before = a->diag.n;
    check_run(a, run);
    return a->diag.n - before;
}

void dc_admission_free(DcAdmission *a) {
    for (size_t i = 0; i < a->nmod; i++) {
        DcAModule *m = &a->mods[i];
        free(m->name);
        for (size_t k = 0; k < m->ndecl; k++) free(m->decls[k].name);
        free(m->decls); free(m->imports);
        dc_ss_free(&m->elements); dc_ss_free(&m->labels); dc_ss_free(&m->fields); dc_ss_free(&m->libraries);
    }
    free(a->mods);
    for (size_t i = 0; i < a->diag.n; i++) { free(a->diag.v[i].mod); free(a->diag.v[i].msg); }
    free(a->diag.v);
    memset(a, 0, sizeof *a);
}

/* First-release capability manifest (registry first_release): NULL when the
 * module's profile coordinates and libraries all lie inside the release,
 * else a reason, written to buf. */
/* M4 opt-in: Dynamics Stochastic and the stochastic libraries are admitted
 * beyond the first release; every other first-release gap still answers. */
static const char *const M4_LIBS[] = { "Linear", "Search", "Decisions", NULL };
static int m4_allowed(const char *key, const char *val) {
    if (!val) return 0;
    if (!strcmp(key, "dynamics")) return !strcmp(val, "Stochastic");
    if (!strcmp(key, "libraries")) { for (int i = 0; M4_LIBS[i]; i++) if (!strcmp(val, M4_LIBS[i])) return 1; }
    return 0;
}
static const char *admit_unsupported(const DcAModule *m, char *buf, size_t n, int beyond);
const char *dc_admit_unsupported(const DcAModule *m, char *buf, size_t n) { return admit_unsupported(m, buf, n, 0); }
const char *dc_admit_unsupported_beyond(const DcAModule *m, char *buf, size_t n) { return admit_unsupported(m, buf, n, 1); }
static const char *admit_unsupported(const DcAModule *m, char *buf, size_t n, int beyond) {
    const Sx *fr = reg_section("first_release");
    struct { const char *key, *val, *what; } co[] = {
        { "dynamics", m->dynamics, "Dynamics" }, { "values", m->values, "Values" }, { "carriers", m->carriers, "Carriers" } };
    for (int i = 0; i < 3; i++)
        if ((!co[i].val || !dc_reg_list_has(dc_reg_get(fr, co[i].key), co[i].val)) && !(beyond && m4_allowed(co[i].key, co[i].val))) {
            snprintf(buf, n, "Profile %s %s is outside the first release", co[i].what, co[i].val ? co[i].val : "None");
            return buf;
        }
    for (size_t i = 0; i < m->libraries.n; i++)
        if (!dc_reg_list_has(dc_reg_get(fr, "libraries"), m->libraries.v[i]) && !(beyond && m4_allowed("libraries", m->libraries.v[i]))) {
            snprintf(buf, n, "library %s is outside the first release", m->libraries.v[i]);
            return buf;
        }
    return NULL;
}
