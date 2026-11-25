/* Families elaborator (library Families, release 1; t-2026-11-24-mettadinc-families).
 * Source to source, before admission: a module that uses Families is rewritten into one without Families
 * forms, which the existing engines decide.  Source of every form: not doc01 but the PROPOSED registry patch
 * docs/e0/docs/03_four_worked_examples/validation_bundles/ex2_access_policy/ex2_registry_patch.json (2026-11-04):
 *   [L] libraries.Families.doc (Parameters, For, Switch total+exclusive, Exists/ForAll, Any in Successor)
 *   [P] declaration_fields.Map.Parameters   [A] declaration_fields.Machine.ActionsOf / Like
 *   [I] declaration_fields.BlockPartition.Invariant   [U] budget_units Unrollings (notes.Unrollings)
 * Forms (tag = citation above):
 *   (Carrier C (Of Symbol) (Enum a b ..))   symbol enumeration: a parameter domain only, dropped after use
 *   (Map f (From C) (To T) (Table (a v) ..)) on a symbol carrier: a lookup, folded at elaboration
 *   [L][P] (Map f (Parameters ($p C) ..) (From X) (To Y) (Body ($x) e)): a family of maps, (f p1 .. x) inlined
 *   [L] (Switch k (a e) .. (Any e)) on a known symbol: the matching arm, else the Any arm; total and exclusive
 *   [L] (Exists $v C e), (ForAll $v C e) over a symbol carrier: the Or / And of the instances
 *   [L] (For $v C) on an Observe or Action entry: one entry per element, named name.elem.., enumeration order
 *   (Const n T v): its value;  Import (Only ..), [A] ActionsOf, Like: expanded into explicit declarations/entries
 * Folded only where sound on words too: Eq of two enumeration symbols (to 1/0 in a Symbolic module, to True/False
 * otherwise; review 1 finding 1), Add of literals, Not and If on 0/1 (Symbolic modules only),
 * And with a 0 operand, Or dropping 0 operands; True/False are 1/0 in Symbolic modules.  Anything else the elaborator cannot
 * rewrite makes the request Unsupported with the reason, never InvalidInput. */
#include "families.h"
#include "ops_internal.h"
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FE_MAXD 512
#define FE_MAXV 16
#define FE_MAXM 16
#define FE_MAXE 512
#define FE_MAXI 1024
typedef struct { const char *var[FE_MAXV]; const Sx *val[FE_MAXV]; int n; } Env;
typedef struct { int obs; char pn[160]; char inst[32]; } Ent;
typedef struct { char name[64]; Ent *e; int n; } Mach;
typedef struct {
    const Sx *d[FE_MAXD]; int nd;
    Mach mach[FE_MAXM]; int nmach;
    char *ikey[FE_MAXI]; int ni;
    char *why; size_t wn; int bad, depth, sym;   /* sym: (Carriers Symbolic) module */
} Fe;

static Sx *fe_fail(Fe *f, const char *fmt, ...) {
    if (!f->bad) { va_list ap; va_start(ap, fmt); vsnprintf(f->why, f->wn, fmt, ap); va_end(ap); f->bad = 1; }
    return NULL;
}
static int digits(const char *s) { if (!s || !*s) return 0; for (; *s; s++) if (*s < '0' || *s > '9') return 0; return 1; }
static int is_lit(const Sx *x) { return x && x->kind == SX_SYM && digits(x->text); }
static int is_bit(const Sx *x) { return sx_is_sym(x, "0") || sx_is_sym(x, "1"); }
static const Sx *field(const Sx *d, const char *h) { for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], h)) return d->items[i]; return NULL; }
static const Sx *decl(const Fe *f, const char *head, const char *nm) {
    for (int i = 0; i < f->nd; i++) { const Sx *d = f->d[i]; if (sx_head_is(d, head) && d->n >= 2 && sx_is_sym(d->items[1], nm)) return d; }
    return NULL;
}
static const Sx *sym_enum(const Fe *f, const char *c) {   /* the Enum of a symbol carrier, or NULL */
    const Sx *d = decl(f, "Carrier", c), *of = d ? field(d, "Of") : NULL;
    if (!of || of->n != 2 || !sx_is_sym(of->items[1], "Symbol")) return NULL;
    return field(d, "Enum");
}
static const Sx *sym_table(const Fe *f, const char *nm) {   /* the Table of a map on a symbol carrier, or NULL */
    const Sx *d = decl(f, "Map", nm), *fr = d ? field(d, "From") : NULL, *tb = d ? field(d, "Table") : NULL;
    if (!tb || !fr || fr->n != 2 || fr->items[1]->kind != SX_SYM || !sym_enum(f, fr->items[1]->text)) return NULL;
    return tb;
}
static const Sx *body_map(const Fe *f, const char *nm) { const Sx *d = decl(f, "Map", nm); return d && field(d, "Body") && !sym_table(f, nm) ? d : NULL; }
static const Sx *const_val(const Fe *f, const char *nm) { const Sx *d = decl(f, "Const", nm); return d && d->n == 4 ? d->items[3] : NULL; }
static int in_enum(const Sx *en, const Sx *x) { for (size_t k = 1; en && k < en->n; k++) if (sx_equal(en->items[k], x)) return 1; return 0; }
static int is_elem(const Fe *f, const Sx *x) {   /* an element of some symbol carrier */
    if (!x || x->kind != SX_SYM || digits(x->text)) return 0;
    for (int i = 0; i < f->nd; i++) {
        const Sx *d = f->d[i];
        if (sx_head_is(d, "Carrier") && d->n >= 2 && d->items[1]->kind == SX_SYM && in_enum(sym_enum(f, d->items[1]->text), x)) return 1;
    }
    return 0;
}
static Sx *fold(const char *h, Sx **p, int n) {   /* takes p[0..n) */
    int isand = !strcmp(h, "And"); Sx *r = NULL;
    if (isand) for (int i = 0; i < n; i++) if (sx_is_sym(p[i], "0")) { for (int k = 0; k < n; k++) sx_free(p[k]); return sx_sym("0"); }
    for (int i = 0; i < n; i++) {
        if (!isand && sx_is_sym(p[i], "0")) { sx_free(p[i]); continue; }
        r = r ? dc_form(h, r, p[i], NULL) : p[i];
    }
    return r ? r : sx_sym(isand ? "1" : "0");
}

static Sx *term(Fe *f, const Sx *t, const Env *e);
static Sx *term_list(Fe *f, const Sx *t, const Env *e) {
    const char *h = t->items[0]->text; size_t n = t->n;
    if (!strcmp(h, "Exists") || !strcmp(h, "ForAll")) {
        const Sx *en = n == 4 && t->items[1]->kind == SX_SYM && t->items[2]->kind == SX_SYM ? sym_enum(f, t->items[2]->text) : NULL;
        if (!en) return fe_fail(f, "Families: %s expects (%s $v C body) over a symbol carrier C", h, h);
        if (e->n >= FE_MAXV) return fe_fail(f, "Families: too many nested binders");
        int k = (int)en->n - 1; Sx **p = calloc((size_t)(k ? k : 1), sizeof *p);
        Env e2 = *e; e2.var[e2.n++] = t->items[1]->text;
        for (int i = 0; i < k; i++) {
            e2.val[e2.n - 1] = en->items[i + 1];
            if (!(p[i] = term(f, t->items[3], &e2))) { for (int j = 0; j < i; j++) sx_free(p[j]); free(p); return NULL; }
        }
        Sx *r = fold(!strcmp(h, "Exists") ? "Or" : "And", p, k); free(p); return r;
    }
    if (!strcmp(h, "Switch")) {
        if (n < 3) return fe_fail(f, "Families: Switch expects (Switch key (symbol expr) ..)");
        Sx *k = term(f, t->items[1], e); if (!k) return NULL;
        char kb[96]; { char *ks = sx_print(k); snprintf(kb, sizeof kb, "%s", ks); free(ks); }
        int ok = is_elem(f, k); sx_free(k);
        if (!ok) return fe_fail(f, "Families: Switch on %s, which is not an element of a symbol carrier at elaboration", kb);
        const Sx *arm = NULL, *any = NULL;
        for (size_t i = 2; i < n; i++) {
            const Sx *a = t->items[i];
            if (a->kind != SX_LIST || a->n != 2 || a->items[0]->kind != SX_SYM) return fe_fail(f, "Families: a Switch arm must be (symbol expr)");
            for (size_t j = 2; j < i; j++)   /* ex2_registry_patch.json: Switch must be total and exclusive */
                if (!strcmp(t->items[j]->items[0]->text, a->items[0]->text))
                    return fe_fail(f, "Families: Switch is not exclusive: two arms for %s", a->items[0]->text);
            if (!arm && !strcmp(a->items[0]->text, kb)) arm = a;
            if (!any && !strcmp(a->items[0]->text, "Any")) any = a;
        }
        if (!arm) arm = any;
        if (!arm) return fe_fail(f, "Families: Switch has no arm for %s and no Any arm", kb);
        return term(f, arm->items[1], e);
    }
    const Sx *tb = sym_table(f, h);
    if (tb) {
        if (n != 2) return fe_fail(f, "Families: table %s applied to %zu arguments", h, n - 1);
        Sx *k = term(f, t->items[1], e); if (!k) return NULL;
        for (size_t i = 1; i < tb->n; i++) {
            const Sx *r = tb->items[i];
            if (r->kind == SX_LIST && r->n == 2 && sx_equal(r->items[0], k)) { sx_free(k); return sx_copy(r->items[1]); }
        }
        char kb[96]; { char *ks = sx_print(k); snprintf(kb, sizeof kb, "%s", ks); free(ks); } sx_free(k);
        return fe_fail(f, "Families: table %s has no row for %s", h, kb);
    }
    const Sx *md = body_map(f, h);
    if (md) {
        const Sx *pr = field(md, "Parameters"), *bo = field(md, "Body");
        size_t np = pr ? pr->n - 1 : 0;
        if (bo->n != 3 || bo->items[1]->kind != SX_LIST || bo->items[1]->n != 1 || bo->items[1]->items[0]->kind != SX_SYM)
            return fe_fail(f, "Families: map %s: expected (Body ($x) expr)", h);
        if (n - 1 != np + 1) return fe_fail(f, "Families: map %s applied to %zu arguments; it takes %zu parameters and the argument", h, n - 1, np);
        if (np + 1 > FE_MAXV) return fe_fail(f, "Families: map %s has too many parameters", h);
        Sx *av[FE_MAXV]; Env e2; e2.n = 0;
        for (size_t i = 0; i <= np; i++) {
            const Sx *b = i < np ? pr->items[i + 1] : NULL, *v = b ? (b->kind == SX_LIST && b->n == 2 ? b->items[0] : NULL) : bo->items[1]->items[0];
            if (!v || v->kind != SX_SYM) { for (size_t j = 0; j < i; j++) sx_free(av[j]); return fe_fail(f, "Families: map %s: a parameter must be ($p Carrier)", h); }
            if (!(av[i] = term(f, t->items[i + 1], e))) { for (size_t j = 0; j < i; j++) sx_free(av[j]); return NULL; }
            const Sx *en = b && b->items[1]->kind == SX_SYM ? sym_enum(f, b->items[1]->text) : NULL;
            if (b && (!en || !in_enum(en, av[i]))) {
                char ab[96]; { char *s = sx_print(av[i]); snprintf(ab, sizeof ab, "%s", s); free(s); }
                for (size_t j = 0; j <= i; j++) sx_free(av[j]);
                return fe_fail(f, en ? "Families: map %s: argument %s is not an element of its parameter carrier" : "Families: map %s: parameter carrier of %s is not a symbol carrier", h, ab);
            }
            e2.var[e2.n] = v->text; e2.val[e2.n] = av[i]; e2.n++;
        }
        Sx *r = term(f, bo->items[2], &e2);
        for (size_t i = 0; i <= np; i++) sx_free(av[i]);
        return r;
    }
    Sx **a = calloc(n, sizeof *a); Sx *r = NULL;
    for (size_t i = 1; i < n; i++) if (!(a[i] = term(f, t->items[i], e))) { for (size_t j = 1; j < i; j++) sx_free(a[j]); free(a); return NULL; }
    int alllit = n >= 2;
    for (size_t i = 1; i < n; i++) if (!is_lit(a[i])) alllit = 0;
    if (!strcmp(h, "Add") && alllit) {
        unsigned long long s = 0; for (size_t i = 1; i < n; i++) s += strtoull(a[i]->text, NULL, 10);
        char b[32]; snprintf(b, sizeof b, "%llu", s); r = sx_sym(b);
    } else if (!strcmp(h, "Eq") && n == 3 && is_elem(f, a[1]) && is_elem(f, a[2])) r = sx_sym(strcmp(a[1]->text, a[2]->text) ? (f->sym ? "0" : "False") : (f->sym ? "1" : "True"));
    else if (!strcmp(h, "Not") && n == 2 && f->sym && is_bit(a[1])) r = sx_sym(sx_is_sym(a[1], "0") ? "1" : "0");
    else if ((!strcmp(h, "And") || !strcmp(h, "Or")) && n >= 2) { r = fold(h, a + 1, (int)n - 1); free(a); return r; }
    else if (!strcmp(h, "If") && n == 4 && f->sym && is_bit(a[1])) { int pk = sx_is_sym(a[1], "1") ? 2 : 3; r = a[pk]; a[pk] = NULL; }
    if (r) { for (size_t i = 1; i < n; i++) if (a[i]) sx_free(a[i]); free(a); return r; }
    Sx *l = sx_list(); sx_push(l, sx_sym(h));
    for (size_t i = 1; i < n; i++) sx_push(l, a[i]);
    free(a); return l;
}
static Sx *term(Fe *f, const Sx *t, const Env *e) {
    if (f->bad) return NULL;
    if (t->kind == SX_SYM) {
        for (int i = e->n - 1; i >= 0; i--) if (!strcmp(e->var[i], t->text)) return sx_copy(e->val[i]);
        if (f->sym && !strcmp(t->text, "True")) return sx_sym("1");
        if (f->sym && !strcmp(t->text, "False")) return sx_sym("0");
        const Sx *c = const_val(f, t->text);
        return sx_copy(c ? c : t);
    }
    if (t->kind != SX_LIST || !t->n || t->items[0]->kind != SX_SYM) return sx_copy(t);
    if (++f->depth > 200) { f->depth--; return fe_fail(f, "Families: elaboration nested too deeply (a recursive map?)"); }
    Sx *r = term_list(f, t, e); f->depth--; return r;
}

/* ---- machine entries: For expansion, instance maps, ActionsOf and Like ---- */
static int add_ent(Fe *f, Mach *mc, int obs, const char *pn, const char *inst) {
    if (mc->n >= FE_MAXE) { fe_fail(f, "Families: machine %s has more than %d entries after expansion", mc->name, FE_MAXE); return -1; }
    if (!mc->e) mc->e = calloc(FE_MAXE, sizeof *mc->e);
    Ent *x = &mc->e[mc->n++]; x->obs = obs;
    snprintf(x->pn, sizeof x->pn, "%s", pn); snprintf(x->inst, sizeof x->inst, "%s", inst);
    return 0;
}
static int fe_entry(Fe *f, Sx *o, Mach *mc, const Sx *ent, const char *states, size_t from, const Env *e) {
    for (size_t i = from; i < ent->n; i++) {
        const Sx *fo = ent->items[i];
        if (!sx_head_is(fo, "For")) continue;
        const Sx *en = fo->n == 3 && fo->items[1]->kind == SX_SYM && fo->items[2]->kind == SX_SYM ? sym_enum(f, fo->items[2]->text) : NULL;
        if (!en) { fe_fail(f, "Families: (For $v C) on a machine entry needs a symbol carrier C"); return -1; }
        if (e->n >= FE_MAXV) { fe_fail(f, "Families: too many For fields"); return -1; }
        Env e2 = *e; e2.var[e2.n++] = fo->items[1]->text;
        for (size_t k = 1; k < en->n; k++) { e2.val[e2.n - 1] = en->items[k]; if (fe_entry(f, o, mc, ent, states, i + 1, &e2)) return -1; }
        return 0;
    }
    int obs = sx_head_is(ent, "Observe");
    if (ent->n < 3) { fe_fail(f, "Families: expected (%s port map (For $v C) ..)", obs ? "Observe" : "Action"); return -1; }
    for (size_t i = 3; i < ent->n; i++)
        if (!sx_head_is(ent->items[i], "For")) { fe_fail(f, "Families: a field other than For on a machine entry is outside the Families elaborator"); return -1; }
    char pn[160] = "";
    if (ent->items[1]->kind == SX_SYM) snprintf(pn, sizeof pn, "%s", ent->items[1]->text);
    else if (ent->items[1]->kind == SX_LIST) {
        for (size_t i = 0; i < ent->items[1]->n; i++) {
            Sx *p = term(f, ent->items[1]->items[i], e); if (!p) return -1;
            if (p->kind != SX_SYM) { sx_free(p); fe_fail(f, "Families: a port name must elaborate to symbols"); return -1; }
            size_t l = strlen(pn); snprintf(pn + l, sizeof pn - l, "%s%s", i ? "." : "", p->text); sx_free(p);
        }
    } else { fe_fail(f, "Families: bad port name"); return -1; }
    const Sx *call = ent->items[2];
    const char *bn = call->kind == SX_SYM ? call->text : call->kind == SX_LIST && call->n && call->items[0]->kind == SX_SYM ? call->items[0]->text : NULL;
    if (call->kind == SX_SYM && bn) {   /* a plain map, used as declared whatever its body form */
        const Sx *pd = decl(f, "Map", bn);
        if (pd && !field(pd, "Parameters")) return add_ent(f, mc, obs, pn, bn);
    }
    const Sx *bd = bn ? body_map(f, bn) : NULL;
    if (!bd) { fe_fail(f, "Families: the map of port %s is not a declared map with a Body", pn); return -1; }
    if (call->kind == SX_SYM && !field(bd, "Parameters")) return add_ent(f, mc, obs, pn, bn);   /* plain map, used as declared */
    Sx *cl = sx_list();
    if (call->kind == SX_SYM) sx_push(cl, sx_copy(call)); else for (size_t i = 0; i < call->n; i++) sx_push(cl, sx_copy(call->items[i]));
    sx_push(cl, sx_sym("$fam_x"));
    Sx *body = term(f, cl, e); sx_free(cl);
    if (!body) return -1;
    const Sx *to = field(bd, "To");
    if (!to) { sx_free(body); fe_fail(f, "Families: map %s has no To", bn); return -1; }
    char *bs = sx_print(body), *ts = sx_print(to); size_t kl = strlen(bs) + strlen(ts) + 2; char *key = malloc(kl);
    snprintf(key, kl, "%s|%s", ts, bs); free(bs); free(ts);
    int hit = -1; for (int i = 0; i < f->ni; i++) if (!strcmp(f->ikey[i], key)) { hit = i; break; }
    char in[32];
    if (hit >= 0) { free(key); sx_free(body); }
    else {
        if (f->ni >= FE_MAXI) { free(key); sx_free(body); fe_fail(f, "Families: more than %d map instances", FE_MAXI); return -1; }
        hit = f->ni; f->ikey[f->ni++] = key;
        snprintf(in, sizeof in, "fam-inst-%d", hit);
        sx_push(o, dc_form("Map", dc_sym(in), dc_form("From", dc_sym(states), NULL), sx_copy(to),
                           dc_form("Body", dc_form("$fam_x", NULL), body, NULL), NULL));
    }
    snprintf(in, sizeof in, "fam-inst-%d", hit);
    return add_ent(f, mc, obs, pn, in);
}
static Mach *find_mach(Fe *f, const char *nm) { for (int i = 0; i < f->nmach; i++) if (!strcmp(f->mach[i].name, nm)) return &f->mach[i]; return NULL; }
static Sx *fe_machine(Fe *f, Sx *o, const Sx *d) {
    const Sx *st = field(d, "States");
    if (d->n < 3 || d->items[1]->kind != SX_SYM || !st || st->n != 2 || st->items[1]->kind != SX_SYM) return fe_fail(f, "Families: expected (Machine Name (States C) ..)");
    if (f->nmach >= FE_MAXM) return fe_fail(f, "Families: too many machines");
    Mach *mc = &f->mach[f->nmach++]; memset(mc, 0, sizeof *mc); snprintf(mc->name, sizeof mc->name, "%s", d->items[1]->text);
    Sx *extra = sx_list(); Env e0; e0.n = 0;
    for (size_t i = 2; i < d->n && !f->bad; i++) {
        const Sx *x = d->items[i];
        if (sx_head_is(x, "States")) continue;
        if (sx_head_is(x, "Observe") || sx_head_is(x, "Action")) { fe_entry(f, o, mc, x, st->items[1]->text, 3, &e0); continue; }
        if (sx_head_is(x, "ActionsOf") || sx_head_is(x, "Like")) {
            Mach *src = x->n == 2 && x->items[1]->kind == SX_SYM ? find_mach(f, x->items[1]->text) : NULL;
            if (!src) { fe_fail(f, "Families: %s names no machine declared before %s", x->items[0]->text, mc->name); break; }
            int acts = sx_head_is(x, "ActionsOf");
            for (int k = 0; k < src->n; k++) if (!acts || !src->e[k].obs) add_ent(f, mc, src->e[k].obs, src->e[k].pn, src->e[k].inst);
            continue;
        }
        Sx *y = term(f, x, &e0); if (y) sx_push(extra, y);
    }
    if (f->bad) { sx_free(extra); return NULL; }
    Sx *m = dc_form("Machine", dc_sym(mc->name), sx_copy(st), NULL);
    for (int k = 0; k < mc->n; k++) sx_push(m, dc_form(mc->e[k].obs ? "Observe" : "Action", dc_sym(mc->e[k].pn), dc_sym(mc->e[k].inst), NULL));
    for (size_t k = 0; k < extra->n; k++) sx_push(m, sx_copy(extra->items[k]));
    sx_free(extra);
    return m;
}

/* ---- the module ---- */
static int uses_families(const Sx *raw) {
    for (size_t i = 2; i < raw->n; i++) if (sx_head_is(raw->items[i], "Use"))
        for (size_t k = 1; k < raw->items[i]->n; k++) if (sx_is_sym(raw->items[i]->items[k], "Families")) return 1;
    return 0;
}
static void inline_types(Sx *o) {   /* (From|To (BitVector k)) on a Map: a carrier BitVector-k (All), declared once after the last carrier */
    Sx *add = sx_list(); size_t last = 2;
    for (size_t i = 2; i < o->n; i++) {
        Sx *d = o->items[i];
        if (sx_head_is(d, "Carrier")) last = i + 1;
        if (!sx_head_is(d, "Map")) continue;
        for (size_t k = 2; k < d->n; k++) {
            Sx *fl = d->items[k];
            if (!(sx_head_is(fl, "From") || sx_head_is(fl, "To")) || fl->n != 2 || !sx_head_is(fl->items[1], "BitVector") || fl->items[1]->n != 2 || !is_lit(fl->items[1]->items[1])) continue;
            char nm[48]; snprintf(nm, sizeof nm, "BitVector-%s", fl->items[1]->items[1]->text);
            int have = 0;
            for (size_t j = 2; j < o->n; j++) if (sx_head_is(o->items[j], "Carrier") && o->items[j]->n >= 2 && sx_is_sym(o->items[j]->items[1], nm)) have = 1;
            for (size_t j = 0; j < add->n; j++) if (sx_is_sym(add->items[j]->items[1], nm)) have = 1;
            if (!have) sx_push(add, dc_form("Carrier", dc_sym(nm), dc_form("Of", sx_copy(fl->items[1]), NULL), dc_form("All", NULL), NULL));
            sx_free(fl->items[1]); fl->items[1] = sx_sym(nm);
        }
    }
    if (add->n) {
        size_t na = add->n, n0 = o->n;
        for (size_t j = 0; j < na; j++) sx_push(o, NULL);
        memmove(o->items + last + na, o->items + last, (n0 - last) * sizeof *o->items);
        for (size_t j = 0; j < na; j++) o->items[last + j] = add->items[j];
        add->n = 0;
    }
    sx_free(add);
}
int dc_families_expand(const Sx *all, const Sx *raw, Sx **out, char *why, size_t wn) {
    *out = NULL;
    if (!raw || !uses_families(raw)) return 0;
    Fe *f = calloc(1, sizeof *f); f->why = why; f->wn = wn;
    for (size_t i = 2; i < raw->n && !f->bad; i++) {
        const Sx *d = raw->items[i];
        if (!sx_head_is(d, "Import")) { if (f->nd < FE_MAXD) f->d[f->nd++] = d; else fe_fail(f, "Families: too many declarations"); continue; }
        const Sx *only = field(d, "Only"), *src = NULL;
        for (size_t k = 0; all && d->n >= 2 && k < all->n; k++)
            if (sx_head_is(all->items[k], "DC.Module") && all->items[k]->n >= 2 && sx_equal(all->items[k]->items[1], d->items[1])) src = all->items[k];
        if (!only || !src) { fe_fail(f, "Families: (Import M (Only ..)) needs a module M of this file and an Only list"); break; }
        for (size_t k = 2; k < src->n; k++) {
            const Sx *e = src->items[k];
            if (e->kind != SX_LIST || e->n < 2 || e->items[1]->kind != SX_SYM) continue;
            for (size_t j = 1; j < only->n; j++) if (sx_equal(only->items[j], e->items[1])) { if (f->nd < FE_MAXD) f->d[f->nd++] = e; break; }
        }
    }
    Sx *o = sx_list(); sx_push(o, sx_copy(raw->items[0])); sx_push(o, sx_copy(raw->items[1]));
    for (int i = 0; i < f->nd; i++) if (sx_head_is(f->d[i], "Profile") || sx_head_is(f->d[i], "Use")) sx_push(o, sx_copy(f->d[i]));
    for (int i = 0; i < f->nd; i++) if (sx_head_is(f->d[i], "Profile"))
        for (size_t k = 1; k < f->d[i]->n; k++) { const Sx *q = f->d[i]->items[k]; if (sx_head_is(q, "Carriers") && q->n == 2 && sx_is_sym(q->items[1], "Symbolic")) f->sym = 1; }
    if (f->sym && !decl(f, "Carrier", "Bool")) sx_push(o, dc_form("Carrier", dc_sym("Bool"), dc_form("Of", dc_sym("Nat"), NULL), dc_form("Enum", dc_sym("0"), dc_sym("1"), NULL), NULL));
    Env e0; e0.n = 0;
    for (int i = 0; i < f->nd && !f->bad; i++) {
        const Sx *d = f->d[i];
        if (sx_head_is(d, "Profile") || sx_head_is(d, "Use") || sx_head_is(d, "Const")) continue;
        if (sx_head_is(d, "Carrier") && d->n >= 2 && d->items[1]->kind == SX_SYM && sym_enum(f, d->items[1]->text)) {
            if (!f->sym) sx_push(o, sx_copy(d));   /* an M0 module reads symbol carriers itself: keep it */
            continue;
        }
        if (f->sym && sx_head_is(d, "Carrier") && field(d, "Of") && field(d, "Of")->n == 2 && sx_is_sym(field(d, "Of")->items[1], "Symbol"))
            { fe_fail(f, "Families: symbol carrier %s needs (Enum ..)", d->n >= 2 && d->items[1]->kind == SX_SYM ? d->items[1]->text : "?"); break; }
        if (sx_head_is(d, "Map") && d->n >= 2 && d->items[1]->kind == SX_SYM && !f->sym && sym_table(f, d->items[1]->text) && !field(d, "Parameters")) { sx_push(o, sx_copy(d)); continue; }
        if (sx_head_is(d, "Map") && d->n >= 2 && d->items[1]->kind == SX_SYM && (sym_table(f, d->items[1]->text) || field(d, "Parameters"))) continue;
        if (sx_head_is(d, "Machine")) { Sx *m = fe_machine(f, o, d); if (m) sx_push(o, m); continue; }
        Sx *y = term(f, d, &e0); if (y) sx_push(o, y);
    }
    for (int i = 0; i < f->nmach; i++) free(f->mach[i].e);
    for (int i = 0; i < f->ni; i++) free(f->ikey[i]);
    int bad = f->bad, sym = f->sym; free(f);
    if (bad) { sx_free(o); return -2; }
    if (sym) inline_types(o);
    *out = o; return 0;
}
