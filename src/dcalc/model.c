/* Admission of DC.Module sources into the enumerated deterministic model. */
#include "model.h"
#include "api.h"   /* M4 opt-in flag */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

static int fail(char *err, size_t n, const char *fmt, ...) {
    va_list ap; va_start(ap, fmt); vsnprintf(err, n, fmt, ap); va_end(ap); return -1;
}
static int name_ok(const Sx *x) { return x && x->kind == SX_SYM && strlen(x->text) < DC_MAX_NAME; }

int dc_find_carrier(const DcModule *m, const char *s) { for (size_t i = 0; i < m->ncar; i++) if (!strcmp(m->car[i].name, s)) return (int)i; return -1; }
int dc_find_map(const DcModule *m, const char *s) { for (size_t i = 0; i < m->nmap; i++) if (!strcmp(m->map[i].name, s)) return (int)i; return -1; }
int dc_find_machine(const DcModule *m, const char *s) { for (size_t i = 0; i < m->nmach; i++) if (!strcmp(m->mach[i].name, s)) return (int)i; return -1; }
int dc_find_repr(const DcModule *m, const char *s) { for (size_t i = 0; i < m->nrep; i++) if (!strcmp(m->rep[i].name, s)) return (int)i; return -1; }
int dc_find_abs(const DcModule *m, const char *s) { for (size_t i = 0; i < m->nabs; i++) if (!strcmp(m->abs[i].name, s)) return (int)i; return -1; }
int dc_find_derive(const DcModule *m, const char *s) { for (size_t i = 0; i < m->nder; i++) if (!strcmp(m->der[i].name, s)) return (int)i; return -1; }
int dc_find_tol(const DcModule *m, const char *s) { for (size_t i = 0; i < m->ntol; i++) if (!strcmp(m->tol[i].name, s)) return (int)i; return -1; }
int dc_carrier_index(const DcCarrier *c, const Sx *v) { for (size_t i = 0; i < c->n; i++) if (sx_equal(c->elems[i], v)) return (int)i; return -1; }

/* ---- Cases evaluation: patterns are literals or (Tuple $x ...); bodies use
 * variables, literals, (Tuple ...), (Add a b), (Mul a b). ---- */
typedef struct { const char *var[16]; const Sx *val[16]; int n; } Env;

static int match(const Sx *pat, const Sx *v, Env *e) {
    if (pat->kind == SX_SYM && pat->text[0] == '$') {
        for (int i = 0; i < e->n; i++) if (!strcmp(e->var[i], pat->text)) return sx_equal(e->val[i], v);
        if (e->n >= 16) return 0;
        e->var[e->n] = pat->text; e->val[e->n] = v; e->n++; return 1;
    }
    if (pat->kind != SX_LIST) return sx_equal(pat, v);
    if (v->kind != SX_LIST || v->n != pat->n) return 0;
    for (size_t i = 0; i < pat->n; i++) if (!match(pat->items[i], v->items[i], e)) return 0;
    return 1;
}
static int parse_int(const Sx *x, long *out) {
    if (!x || x->kind != SX_SYM) return 0;
    /* review 4 F3: out-of-range literals are refused, not clamped */
    char *end; errno = 0; long v = strtol(x->text, &end, 10);
    if (end == x->text || *end) return 0;
    if (errno == ERANGE) return -1;
    *out = v; return 1;
}
static int allow_rat;   /* M2: set by admit_map only for a Graded map into a value carrier */
static Sx *eval_body(const Sx *b, const Env *e, int *ok) {
    if (b->kind == SX_SYM && b->text[0] == '$') {
        for (int i = 0; i < e->n; i++) if (!strcmp(e->var[i], b->text)) return sx_copy(e->val[i]);
        if (*ok == 1) *ok = 0;
        return sx_sym("?");
    }
    if (b->kind != SX_LIST) return sx_copy(b);
    if ((sx_head_is(b, "Add") || sx_head_is(b, "Mul")) && b->n == 3) {
        Sx *x = eval_body(b->items[1], e, ok), *y = eval_body(b->items[2], e, ok);
        long a, c; char buf[32];
        int pa = *ok == 1 ? parse_int(x, &a) : 0, pc = *ok == 1 ? parse_int(y, &c) : 0;
        if (pa < 0 || pc < 0) { *ok = 3; sx_free(x); sx_free(y); return sx_sym("?"); }   /* out-of-range literal */
        if (*ok != 1 || !pa || !pc) { if (*ok == 1) *ok = 0; sx_free(x); sx_free(y); return sx_sym("?"); }
        /* review 4 F3: checked arithmetic; overflow is an admission error (ok = 3) */
        long r;
        if (sx_head_is(b, "Add") ? __builtin_add_overflow(a, c, &r) : __builtin_mul_overflow(a, c, &r)) {
            *ok = 3; sx_free(x); sx_free(y); return sx_sym("?");
        }
        snprintf(buf, sizeof buf, "%ld", r);
        sx_free(x); sx_free(y); return sx_sym(buf);
    }
    if (allow_rat && sx_head_is(b, "Rat") && b->n == 3) return sx_copy(b);
    if (b->n && b->items[0]->kind == SX_SYM && strcmp(b->items[0]->text, "Tuple")) { if (*ok == 1) *ok = 2; return sx_sym("?"); }
    Sx *l = sx_list();
    for (size_t i = 0; i < b->n; i++) sx_push(l, eval_body(b->items[i], e, ok));
    return l;
}

/* review 3 F2: a carrier that fails admission is not counted in m->ncar, so
   dc_module_free cannot see it; release its partial element table here. */
static void car_drop(DcCarrier *c) {
    if (c->elems) { for (size_t j = 0; j < c->n; j++) sx_free(c->elems[j]); free(c->elems); }
    c->elems = NULL; c->n = 0;
}

/* ---- M2: forward-closed subsets (Carrier C (Of T) (Reach M (From e ...))) ----
 * The states of M reachable from the listed elements under every action of M,
 * in parent order.  Maps on the parent are used on C by restriction. */
static int admit_reach(DcModule *m, DcCarrier *c, const char *nm, const Sx *body, char *err, size_t es) {
    if (strcmp(m->profile, "Graded")) return -2;
    const Sx *fr = body->n == 3 ? body->items[2] : NULL;
    int mi = body->n == 3 && name_ok(body->items[1]) ? dc_find_machine(m, body->items[1]->text) : -1;
    if (mi < 0 || !sx_head_is(fr, "From") || fr->n < 2) return fail(err, es, "Carrier %s: expected (Reach Machine (From e ...)) after the machine is declared", nm);
    const DcMachine *mc = &m->mach[mi]; const DcCarrier *P = &m->car[mc->states]; size_t n = P->n;
    int *in = calloc(n ? n : 1, sizeof(int)), *qu = malloc((n ? n : 1) * sizeof(int)); size_t h = 0, t = 0;
    for (size_t k = 1; k < fr->n; k++) {
        int i = dc_carrier_index(P, fr->items[k]);
        if (i < 0) { char *x = sx_print(fr->items[k]); fail(err, es, "Carrier %s: Reach start %s is not a state of %s", nm, x, mc->name); free(x); free(in); free(qu); return -1; }
        if (!in[i]) { in[i] = 1; qu[t++] = i; }
    }
    while (h < t) { int x = qu[h++]; for (size_t a = 0; a < mc->nact; a++) { int y = m->map[mc->act[a].map].table[x]; if (!in[y]) { in[y] = 1; qu[t++] = y; } } }
    c->n = t; c->elems = calloc(t ? t : 1, sizeof(Sx *)); c->sub_idx = malloc((t ? t : 1) * sizeof(int));
    size_t k = 0; for (size_t i = 0; i < n; i++) if (in[i]) { c->elems[k] = sx_copy(P->elems[i]); c->sub_idx[k++] = (int)i; }
    c->reach_parent = mc->states + 1; free(in); free(qu);
    m->ncar++; return 0;
}
/* A map on the parent of a Reach carrier, restricted to it (same name).  With
 * to_sub set (an action) its values must stay inside the subset: an update that
 * leaves its carrier is InvalidInput.  Returns the map index, -1 on error. */
static int restrict_map(DcModule *m, int mp, int sc, int to_sub, char *err, size_t es) {
    const DcCarrier *C = &m->car[sc];
    if (m->map[mp].from == sc || !C->reach_parent || C->reach_parent - 1 != m->map[mp].from) return mp;
    int par = C->reach_parent - 1, tsub = to_sub && m->map[mp].to == par;
    for (size_t i = 0; i < m->nmap; i++)
        if (!strcmp(m->map[i].name, m->map[mp].name) && m->map[i].from == sc && m->map[i].to == (tsub ? sc : m->map[mp].to)) return (int)i;
    if (m->nmap >= sizeof m->map / sizeof m->map[0]) { fail(err, es, "Map %s: too many maps after restriction to %s", m->map[mp].name, C->name); return -1; }
    int *tab = malloc((C->n ? C->n : 1) * sizeof(int));
    for (size_t i = 0; i < C->n; i++) {
        int v = m->map[mp].table[C->sub_idx[i]];
        if (tsub) {
            int j = -1; for (size_t k = 0; k < C->n; k++) if (C->sub_idx[k] == v) { j = (int)k; break; }
            if (j < 0) {
                char *x = sx_print(C->elems[i]), *y = sx_print(m->car[par].elems[v]);
                fail(err, es, "Map %s: the update sends %s to %s, which leaves carrier %s", m->map[mp].name, x, y, C->name);
                free(x); free(y); free(tab); return -1;
            }
            v = j;
        }
        tab[i] = v;
    }
    char nmb[DC_MAX_NAME]; memcpy(nmb, m->map[mp].name, DC_MAX_NAME);
    DcMap *r = &m->map[m->nmap]; memset(r, 0, sizeof *r); memcpy(r->name, nmb, DC_MAX_NAME);
    r->from = sc; r->to = tsub ? sc : m->map[mp].to; r->table = tab; return (int)m->nmap++;
}

static int admit_carrier(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n < 4 || !name_ok(d->items[1])) return fail(err, es, "[M0] Carrier: expected (Carrier Name (Of T) (Enum ...)|(Product ...))");
    const char *nm = d->items[1]->text;
    if (dc_find_carrier(m, nm) >= 0) return fail(err, es, "Carrier %s: duplicate name", nm);
    if (m->ncar >= 32) return fail(err, es, "Carrier %s: too many carriers", nm);
    const Sx *body = d->items[3];
    DcCarrier *c = &m->car[m->ncar];
    memset(c, 0, sizeof *c); snprintf(c->name, sizeof c->name, "%s", nm);
    if (sx_head_is(body, "Reach")) return admit_reach(m, c, nm, body, err, es);
    if (sx_head_is(body, "Enum")) {
        c->n = body->n - 1; c->elems = calloc(c->n ? c->n : 1, sizeof(Sx *));
        for (size_t i = 0; i < c->n; i++) {
            DcRat rq;   /* M6 opt-in: a (Use Contracts) carrier of Rational may list (Rat p q) elements */
            int ratel = body->items[i + 1]->kind == SX_LIST && m->contracts && sx_head_is(body->items[i + 1], "Rat") && !dc_sx_rat(body->items[i + 1], &rq);
            if (body->items[i + 1]->kind == SX_LIST && !ratel) { car_drop(c); return fail(err, es, "[M0] Carrier %s: Enum element %zu is not atomic", nm, i); }
            for (size_t j = 0; j < i; j++) if (sx_equal(c->elems[j], body->items[i + 1])) { int rc = fail(err, es, "Carrier %s: duplicate Enum element %zu", nm, i); car_drop(c); return rc; }
            c->elems[i] = sx_copy(body->items[i + 1]);
        }
    } else if (sx_head_is(body, "Product") && body->n >= 2) {
        size_t k = body->n - 1; int idx[8]; size_t total = 1;
        if (k > 8) return fail(err, es, "[M0] Carrier %s: Product of more than 8 factors", nm);
        for (size_t i = 0; i < k; i++) {
            if (!name_ok(body->items[i + 1]) || (idx[i] = dc_find_carrier(m, body->items[i + 1]->text)) < 0)
                return fail(err, es, "Carrier %s: Product factor %zu is not a declared carrier (%s)", nm, i, body->items[i + 1]->kind == SX_SYM ? body->items[i + 1]->text : "?");
            total *= m->car[idx[i]].n;
            if (total > 4096) return fail(err, es, "[M0] Carrier %s: more than 4096 elements", nm);
        }
        c->n = total; c->elems = calloc(total ? total : 1, sizeof(Sx *));
        for (size_t t = 0; t < total; t++) {          /* lexicographic, last factor fastest */
            Sx *tu = sx_list(); sx_push(tu, sx_sym("Tuple"));
            size_t r = t, digit[8];
            for (size_t i = k; i-- > 0;) { digit[i] = r % m->car[idx[i]].n; r /= m->car[idx[i]].n; }
            for (size_t i = 0; i < k; i++) sx_push(tu, sx_copy(m->car[idx[i]].elems[digit[i]]));
            c->elems[t] = tu;
        }
    } else return fail(err, es, "[M0] Carrier %s: only Enum and Product carriers are in the M0 fragment", nm);
    m->ncar++; return 0;
}

/* ---- M2: inline Product sources, Body maps over FiniteSets, Merge ports ---- */
static int uses_lib(const DcModule *m, const char *lib) {
    const Sx *src = m->source;
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (sx_head_is(d, "Use")) for (size_t k = 1; k < d->n; k++) if (sx_is_sym(d->items[k], lib)) return 1;
    }
    return 0;
}
/* (Product A B) written inline in a Map's From field: a carrier named by its printed form. */
static int product_carrier(DcModule *m, const Sx *prod, char *err, size_t es) {
    char *nm = sx_print(prod); int at = nm ? dc_find_carrier(m, nm) : -1;
    if (!nm) { fail(err, es, "inline Product: out of memory"); return -1; }
    if (at >= 0) { free(nm); return at; }
    int a = prod->n == 3 && name_ok(prod->items[1]) ? dc_find_carrier(m, prod->items[1]->text) : -1;
    int b = prod->n == 3 && name_ok(prod->items[2]) ? dc_find_carrier(m, prod->items[2]->text) : -1;
    if (strlen(nm) >= DC_MAX_NAME || a < 0 || b < 0) { fail(err, es, "Map: inline carrier %s must be a binary Product of declared carriers", nm); free(nm); return -1; }
    size_t na = m->car[a].n, nb = m->car[b].n, total = na * nb;
    if (total > 4096 || m->ncar >= sizeof m->car / sizeof m->car[0]) { fail(err, es, "[M0] inline carrier %s: too large for the table engine", nm); free(nm); return -1; }
    DcCarrier *c = &m->car[m->ncar]; memset(c, 0, sizeof *c); snprintf(c->name, sizeof c->name, "%s", nm); free(nm);
    c->n = total; c->elems = calloc(total ? total : 1, sizeof(Sx *));
    for (size_t t = 0; t < total; t++) {
        Sx *tu = sx_list(); sx_push(tu, sx_sym("Tuple"));
        sx_push(tu, sx_copy(m->car[a].elems[t / nb])); sx_push(tu, sx_copy(m->car[b].elems[t % nb]));
        c->elems[t] = tu;
    }
    return (int)m->ncar++;
}
/* FiniteSets reading of packet symbols (spec Example 4.3): E = {}, U = {u}, V = {v}, B = {u, v}. */
static const char *RECEIPT[4] = {"Empty", "UOnly", "VOnly", "Both"};
static int receipt_bits(const Sx *v) {
    if (!v || v->kind != SX_SYM) return -1;
    for (int i = 0; i < 4; i++) if (!strcmp(v->text, RECEIPT[i])) return i;
    return -1;
}
/* Body expressions: the bound variable, literals, (GetTuple e i), (ReceiptUnion a b).
 * *ok: 1 fine, 0 ill-formed, 2 an operator outside the M2 Body fragment. */
/* M6 (Use Contracts, beyond release): rational Body expressions: the bound variable, rational
 * literals, (Add a b), (Sub a b), (Mul a b), and (h e) for an earlier declared Map h whose From
 * carrier holds the value of e (matched by rational value).  *ok: 1 fine, 0 ill-formed. */
static Sx *rat_sx(DcRat r);
static Sx *eval_rat_body(const DcModule *m, const Sx *b, const char *var, const Sx *val, int *ok) {
    DcRat r; int ovf = 0;
    if (b->kind == SX_SYM && !strcmp(b->text, var)) return sx_copy(val);
    if (!dc_sx_rat(b, &r)) return rat_sx(r);
    if (b->kind == SX_LIST && b->n == 3 && b->items[0]->kind == SX_SYM
        && (!strcmp(b->items[0]->text, "Add") || !strcmp(b->items[0]->text, "Sub") || !strcmp(b->items[0]->text, "Mul") || !strcmp(b->items[0]->text, "Div"))) {
        Sx *x = eval_rat_body(m, b->items[1], var, val, ok), *y = eval_rat_body(m, b->items[2], var, val, ok); DcRat u, v;
        int bad = *ok != 1 || dc_sx_rat(x, &u) || dc_sx_rat(y, &v); sx_free(x); sx_free(y);
        if (bad) { *ok = 0; return sx_sym("?"); }
        const char *op = b->items[0]->text;
        if (!strcmp(op, "Div") && v.n == 0) { *ok = 0; return sx_sym("?"); }   /* division by zero: no value */
        r = !strcmp(op, "Add") ? dc_rat_add(u, v, &ovf) : !strcmp(op, "Sub") ? dc_rat_sub(u, v, &ovf) : !strcmp(op, "Mul") ? dc_rat_mul(u, v, &ovf) : dc_rat_div(u, v, &ovf);
        if (ovf) { *ok = 0; return sx_sym("?"); }
        return rat_sx(r);
    }
    if (b->kind == SX_LIST && b->n == 2 && b->items[0]->kind == SX_SYM) {
        int k = dc_find_map(m, b->items[0]->text);
        if (k >= 0) {
            Sx *x = eval_rat_body(m, b->items[1], var, val, ok); DcRat u, w;
            const DcMap *g = &m->map[k]; const DcCarrier *G = &m->car[g->from];
            int bad = *ok != 1, isr = !bad && !dc_sx_rat(x, &u);
            /* rational arguments match by value; other values (symbols, tuples) by structure */
            if (!bad) for (size_t i = 0; i < G->n; i++)
                if ((isr ? !dc_sx_rat(G->elems[i], &w) && !dc_rat_cmp(u, w) : sx_equal(G->elems[i], x)) && g->table[i] >= 0) { sx_free(x); return sx_copy(m->car[g->to].elems[g->table[i]]); }
            sx_free(x); *ok = 0; return sx_sym("?");
        }
    }
    if (sx_head_is(b, "GetTuple") && b->n == 3) {   /* M6: tuple projection */
        Sx *t = eval_rat_body(m, b->items[1], var, val, ok), *r; long i;
        if (*ok == 1 && parse_int(b->items[2], &i) == 1 && sx_head_is(t, "Tuple") && i >= 0 && (size_t)i + 1 < t->n) r = sx_copy(t->items[i + 1]);
        else { *ok = 0; r = sx_sym("?"); }
        sx_free(t); return r;
    }
    if (sx_head_is(b, "ReceiptUnion") && b->n == 3 && uses_lib(m, "FiniteSets")) {   /* M6: FiniteSets packet union */
        Sx *x = eval_rat_body(m, b->items[1], var, val, ok), *y = eval_rat_body(m, b->items[2], var, val, ok);
        int bx = receipt_bits(x), by = receipt_bits(y); sx_free(x); sx_free(y);
        if (*ok != 1 || bx < 0 || by < 0) { *ok = 0; return sx_sym("?"); }
        return sx_sym(RECEIPT[bx | by]);
    }
    *ok = 0; return sx_sym("?");
}
static Sx *eval_set_body(const Sx *b, const char *var, const Sx *val, int *ok) {
    if (b->kind == SX_SYM) {
        if (!strcmp(b->text, var)) return sx_copy(val);
        if (b->text[0] == '$' && *ok == 1) *ok = 0;
        return sx_copy(b);
    }
    if (sx_head_is(b, "GetTuple") && b->n == 3) {
        Sx *t = eval_set_body(b->items[1], var, val, ok), *r; long i;
        if (parse_int(b->items[2], &i) == 1 && sx_head_is(t, "Tuple") && i >= 0 && (size_t)i + 1 < t->n) r = sx_copy(t->items[i + 1]);
        else { if (*ok == 1) *ok = 0; r = sx_sym("?"); }
        sx_free(t); return r;
    }
    if (sx_head_is(b, "ReceiptUnion") && b->n == 3) {
        Sx *x = eval_set_body(b->items[1], var, val, ok), *y = eval_set_body(b->items[2], var, val, ok);
        int bx = receipt_bits(x), by = receipt_bits(y); sx_free(x); sx_free(y);
        if (bx < 0 || by < 0) { if (*ok == 1) *ok = 0; return sx_sym("?"); }
        return sx_sym(RECEIPT[bx | by]);
    }
    *ok = 2; return sx_sym("?");
}

static int admit_map(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n != 5 || !name_ok(d->items[1])) return fail(err, es, "[M0] Map: expected (Map name (From C) (To C) (Table|Cases ...))");
    const char *nm = d->items[1]->text;
    if (dc_find_map(m, nm) >= 0) return fail(err, es, "Map %s: duplicate name", nm);
    if (m->nmap >= 64) return fail(err, es, "Map %s: too many maps", nm);
    const Sx *fr = d->items[2], *to = d->items[3], *body = d->items[4];
    int fprod = -1;
    if (sx_head_is(fr, "From") && fr->n == 2 && sx_head_is(fr->items[1], "Product") && !strcmp(m->profile, "Graded")) {
        fprod = product_carrier(m, fr->items[1], err, es); if (fprod < 0) return -1; }
    if (fprod < 0 && (!sx_head_is(fr, "From") || fr->n != 2 || !name_ok(fr->items[1]))) return fail(err, es, "[M0] Map %s: field From", nm);
    if (!sx_head_is(to, "To") || to->n != 2 || !name_ok(to->items[1])) return fail(err, es, "[M0] Map %s: field To", nm);
    int f = fprod >= 0 ? fprod : dc_find_carrier(m, fr->items[1]->text), t = dc_find_carrier(m, to->items[1]->text);
    if (t < 0 && !strcmp(m->profile, "Graded")) t = dc_value_carrier(m, to->items[1]->text);
    if (f < 0) return fail(err, es, "Map %s: field From names no declared carrier (%s)", nm, fr->items[1]->text);
    if (t < 0) return fail(err, es, "Map %s: field To names no declared carrier (%s)", nm, to->items[1]->text);
    DcCarrier *F = &m->car[f], *T = &m->car[t];
    DcMap *mp = &m->map[m->nmap]; memset(mp, 0, sizeof *mp);
    snprintf(mp->name, sizeof mp->name, "%s", nm); mp->from = f; mp->to = t;
    mp->table = malloc((F->n ? F->n : 1) * sizeof(int));
    for (size_t i = 0; i < F->n; i++) mp->table[i] = -1;
    if (sx_head_is(body, "Table")) {
        for (size_t j = 1; j < body->n; j++) {
            const Sx *row = body->items[j];
            if (row->kind != SX_LIST || row->n != 2) { free(mp->table); return fail(err, es, "Map %s: Table row %zu is not a pair", nm, j - 1); }
            int a = dc_carrier_index(F, row->items[0]), b = T->value ? dc_value_add(T, row->items[1]) : dc_carrier_index(T, row->items[1]);
            if (a < 0) { free(mp->table); return fail(err, es, "Map %s: Table row %zu key outside carrier %s", nm, j - 1, F->name); }
            if (b < 0) { free(mp->table); return fail(err, es, "Map %s: Table row %zu value outside carrier %s", nm, j - 1, T->name); }
            if (mp->table[a] >= 0) { free(mp->table); return fail(err, es, "Map %s: Table key at row %zu repeated", nm, j - 1); }
            mp->table[a] = b;
        }
    } else if (sx_head_is(body, "Cases")) {
        for (size_t i = 0; i < F->n; i++) {
            for (size_t j = 1; j < body->n; j++) {
                const Sx *row = body->items[j]; Env e = {0}; int ok = 1;
                if (row->kind != SX_LIST || row->n != 2) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu is not a pair", nm, j - 1); }
                if (!match(row->items[0], F->elems[i], &e)) continue;
                allow_rat = T->value; Sx *v = eval_body(row->items[1], &e, &ok); allow_rat = 0;
                if (ok == 2) { sx_free(v); free(mp->table); return fail(err, es, "[M0] Map %s: Cases row %zu uses an operator outside the M0 fragment", nm, j - 1); }
                if (ok == 3) { sx_free(v); free(mp->table); return fail(err, es, "Map %s: Cases row %zu: integer overflow or out-of-range literal in Add/Mul", nm, j - 1); }
                int b = ok ? (T->value ? dc_value_add(T, v) : dc_carrier_index(T, v)) : -1; sx_free(v);
                if (b < 0) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu gives a value outside carrier %s", nm, j - 1, T->name); }
                /* spec 5.4: every input matches exactly one case; overlapping cases are
                 * rejected even when they agree (source order never decides a value) */
                for (size_t j2 = j + 1; j2 < body->n; j2++) {
                    const Sx *r2 = body->items[j2]; Env e2 = {0};
                    if (r2->kind != SX_LIST || r2->n != 2) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu is not a pair", nm, j2 - 1); }
                    if (match(r2->items[0], F->elems[i], &e2)) {
                        char *xs = sx_print(F->elems[i]);
                        fail(err, es, "Map %s: input %s matches Cases rows %zu and %zu; overlapping cases are rejected", nm, xs, j - 1, j2 - 1);
                        free(xs); free(mp->table); return -1;
                    }
                }
                mp->table[i] = b; break;
            }
        }
    } else if (sx_head_is(body, "Body") && body->n == 3 && !strcmp(m->profile, "Graded") && uses_lib(m, "FiniteSets") && !(m->contracts && T->value)
               && body->items[1]->kind == SX_LIST && body->items[1]->n == 1 && body->items[1]->items[0]->kind == SX_SYM
               && body->items[1]->items[0]->text[0] == '$') {
        const char *var = body->items[1]->items[0]->text;
        for (size_t i = 0; i < F->n; i++) {
            int ok = 1; Sx *v = eval_set_body(body->items[2], var, F->elems[i], &ok);
            int b = ok == 1 ? dc_carrier_index(T, v) : -1;
            if (ok == 2) { sx_free(v); free(mp->table); return fail(err, es, "[M0] Map %s: Body uses an operator outside the M2 FiniteSets fragment", nm); }
            if (b < 0) {
                char *xs = sx_print(F->elems[i]), *vs = sx_print(v);
                fail(err, es, "Map %s: Body sends %s to %s, which is not in carrier %s", nm, xs, vs, T->name);
                free(xs); free(vs); sx_free(v); free(mp->table); return -1;
            }
            sx_free(v); mp->table[i] = b;
        }
    } else if (sx_head_is(body, "Body") && body->n == 3 && m->contracts && T->value && body->items[1]->kind == SX_LIST
               && body->items[1]->n == 1 && body->items[1]->items[0]->kind == SX_SYM && body->items[1]->items[0]->text[0] == '$') {   /* M6 opt-in */
        const char *var = body->items[1]->items[0]->text;
        for (size_t i = 0; i < F->n; i++) {
            int ok = 1; Sx *v = eval_rat_body(m, body->items[2], var, F->elems[i], &ok);
            int b = ok == 1 ? dc_value_add(T, v) : -1;
            if (b < 0) {
                char *xs = sx_print(F->elems[i]); fail(err, es, "Map %s: Body has no rational value in %s on %s", nm, T->name, xs);
                free(xs); sx_free(v); free(mp->table); return -1;
            }
            sx_free(v); mp->table[i] = b;
        }
    } else { free(mp->table); return fail(err, es, "[M0] Map %s: only Table and Cases maps are in the M0 deterministic fragment", nm); }
    for (size_t i = 0; i < F->n; i++) if (mp->table[i] < 0) {
        char *s = sx_print(F->elems[i]); fail(err, es, "Map %s: not total; no value for %s", nm, s); free(s); free(mp->table); return -1;
    }
    m->nmap++; return 0;
}

static int admit_ports(DcModule *m, DcMachine *mc, const Sx *d, int is_obs, char *err, size_t es) {
    DcPort *ports = is_obs ? mc->obs : mc->act; size_t *np = is_obs ? &mc->nobs : &mc->nact;
    const char *field = is_obs ? "Observe" : "Action";
    int ptol = -1;
    /* M2: (Observe label map (Values Tol)) in a Graded module; the tolerance must sit on the map's target */
    if (is_obs && d->n == 4 && !strcmp(m->profile, "Graded") && name_ok(d->items[1]) && name_ok(d->items[2])
        && sx_head_is(d->items[3], "Values") && d->items[3]->n == 2 && name_ok(d->items[3]->items[1])) {
        ptol = dc_find_tol(m, d->items[3]->items[1]->text);
        if (ptol < 0) return fail(err, es, "Machine %s: field Observe names no declared tolerance (%s)", mc->name, d->items[3]->items[1]->text);
        int mp0 = dc_find_map(m, d->items[2]->text);
        if (mp0 >= 0 && m->map[mp0].to != m->tol[ptol].on)
            return fail(err, es, "Machine %s: field Observe tolerance %s is not on the target of map %s", mc->name, m->tol[ptol].name, d->items[2]->text);
        mc->graded_obs = 1;
    }
    if (ptol < 0 && d->n > 3 && name_ok(d->items[1]) && name_ok(d->items[2]))
        return fail(err, es, "[M0] Machine %s: field %s with value tolerances is outside the M0 deterministic fragment", mc->name, field);
    /* (Observe label (map arg ...)): an applied, parameterised map is outside M0 */
    if (d->n == 3 && name_ok(d->items[1]) && d->items[2]->kind == SX_LIST) return -2;
    if ((ptol < 0 && d->n != 3) || !name_ok(d->items[1]) || !name_ok(d->items[2])) return fail(err, es, "Machine %s: field %s expects (%s label map)", mc->name, field, field);
    if (*np >= 16) return fail(err, es, "Machine %s: field %s: too many", mc->name, field);
    int mp = dc_find_map(m, d->items[2]->text);
    if (mp < 0) return fail(err, es, "Machine %s: field %s names no declared map (%s)", mc->name, field, d->items[2]->text);
    if ((mp = restrict_map(m, mp, mc->states, !is_obs, err, es)) < 0) return -1;
    if (m->map[mp].from != mc->states) return fail(err, es, "Machine %s: field %s map %s does not start at the state carrier", mc->name, field, d->items[2]->text);
    if (!is_obs && m->map[mp].to != mc->states) return fail(err, es, "Machine %s: field Action map %s does not end at the state carrier", mc->name, d->items[2]->text);
    for (size_t i = 0; i < *np; i++) if (!strcmp(ports[i].label, d->items[1]->text)) return fail(err, es, "Machine %s: field %s label %s repeated", mc->name, field, d->items[1]->text);
    snprintf(ports[*np].label, DC_MAX_NAME, "%s", d->items[1]->text); ports[*np].map = mp; ports[*np].tol = ptol; (*np)++;
    return 0;
}

/* M2: (Merge label map) on a Graded machine; map goes from the product of the
 * states with themselves (in carrier order) to the states. */
static int admit_merge(DcModule *m, DcMachine *mc, const Sx *d, char *err, size_t es) {
    if (strcmp(m->profile, "Graded")) return -2;
    if (d->n != 3 || !name_ok(d->items[1]) || !name_ok(d->items[2])) return fail(err, es, "Machine %s: field Merge expects (Merge label map)", mc->name);
    if (mc->nmerge >= sizeof mc->merge / sizeof mc->merge[0]) return fail(err, es, "Machine %s: field Merge: too many", mc->name);
    int mp = dc_find_map(m, d->items[2]->text);
    if (mp < 0) return fail(err, es, "Machine %s: field Merge names no declared map (%s)", mc->name, d->items[2]->text);
    const DcCarrier *S = &m->car[mc->states], *P = &m->car[m->map[mp].from]; size_t n = S->n;
    int ok = P->n == n * n && m->map[mp].to == mc->states;
    for (size_t t = 0; ok && t < P->n; t++) {
        const Sx *e = P->elems[t];
        ok = sx_head_is(e, "Tuple") && e->n == 3 && sx_equal(e->items[1], S->elems[t / n]) && sx_equal(e->items[2], S->elems[t % n]);
    }
    if (!ok) return fail(err, es, "Machine %s: Merge map %s is not from (Product %s %s) to %s", mc->name, d->items[2]->text, S->name, S->name, S->name);
    for (size_t i = 0; i < mc->nmerge; i++) if (!strcmp(mc->merge[i].label, d->items[1]->text)) return fail(err, es, "Machine %s: field Merge label %s repeated", mc->name, d->items[1]->text);
    DcPort *p = &mc->merge[mc->nmerge++]; snprintf(p->label, DC_MAX_NAME, "%s", d->items[1]->text); p->map = mp; p->tol = -1;
    return 0;
}

static int admit_machine(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n < 3 || !name_ok(d->items[1])) return fail(err, es, "Machine: expected (Machine Name (States C) ...)");
    const char *nm = d->items[1]->text;
    if (dc_find_machine(m, nm) >= 0) return fail(err, es, "Machine %s: duplicate name", nm);
    if (m->nmach >= 16) return fail(err, es, "Machine %s: too many machines", nm);
    DcMachine *mc = &m->mach[m->nmach]; memset(mc, 0, sizeof *mc);
    snprintf(mc->name, sizeof mc->name, "%s", nm);
    const Sx *st = sx_find(d, "States", 2);
    if (!st || st->n != 2 || !name_ok(st->items[1]) || (mc->states = dc_find_carrier(m, st->items[1]->text)) < 0)
        return fail(err, es, "Machine %s: field States names no declared carrier (%s)", nm, st && st->n == 2 && st->items[1]->kind == SX_SYM ? st->items[1]->text : "?");
    for (size_t i = 2; i < d->n; i++) {
        const Sx *f = d->items[i];
        if (sx_head_is(f, "States")) continue;
        if (sx_head_is(f, "Observe")) { { int prc = admit_ports(m, mc, f, 1, err, es); if (prc) return prc; } }
        else if (sx_head_is(f, "Action")) { { int prc = admit_ports(m, mc, f, 0, err, es); if (prc) return prc; } }
        else if (sx_head_is(f, "Merge")) { int prc = admit_merge(m, mc, f, err, es); if (prc) return prc; }
        else return fail(err, es, "[M0] Machine %s: field %s is outside the M0 deterministic fragment", nm, f->kind == SX_LIST && f->n ? f->items[0]->text : "?");
    }
    m->nmach++; return 0;
}

static int declared_in_source(const DcModule *m, const char *head, const char *name) {
    const Sx *src = m->source;
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (sx_head_is(d, head) && d->n > 1 && sx_is_sym(d->items[1], name)) return 1;
    }
    return 0;
}

static int admit_repr(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n < 4 || !name_ok(d->items[1])) return fail(err, es, "Representation: expected (Representation Name (Of M) (Encode map) ...)");
    const char *nm = d->items[1]->text;
    if (dc_find_repr(m, nm) >= 0) return fail(err, es, "Representation %s: duplicate name", nm);
    /* review 4 F2: capacity is checked before the slot is touched */
    if (m->nrep >= sizeof m->rep / sizeof m->rep[0]) return fail(err, es, "Representation %s: too many representations", nm);
    DcRepr *r = &m->rep[m->nrep]; memset(r, 0, sizeof *r); snprintf(r->name, sizeof r->name, "%s", nm);
    const Sx *of = sx_find(d, "Of", 2), *en = sx_find(d, "Encode", 2), *co = sx_find(d, "Codes", 2);
    if (of && of->n == 2 && name_ok(of->items[1]) && dc_find_machine(m, of->items[1]->text) < 0
        && declared_in_source(m, "Machine", of->items[1]->text)) return -2;   /* machine outside M0 */
    if (!of || of->n != 2 || !name_ok(of->items[1]) || (r->machine = dc_find_machine(m, of->items[1]->text)) < 0)
        return fail(err, es, "Representation %s: field Of names no declared machine (%s)", nm, of && of->n == 2 && of->items[1]->kind == SX_SYM ? of->items[1]->text : "?");
    if (!en || en->n != 2 || !name_ok(en->items[1]) || (r->encode = dc_find_map(m, en->items[1]->text)) < 0)
        return fail(err, es, "Representation %s: field Encode names no declared map (%s)", nm, en && en->n == 2 && en->items[1]->kind == SX_SYM ? en->items[1]->text : "?");
    if ((r->encode = restrict_map(m, r->encode, m->mach[r->machine].states, 0, err, es)) < 0) return -1;
    if (m->map[r->encode].from != m->mach[r->machine].states)
        return fail(err, es, "Representation %s: field Encode map does not start at the states of %s", nm, m->mach[r->machine].name);
    r->codes = DC_CODES_EXACT; r->tol = -1;
    if (co) {
        int t = (co->n == 2 && name_ok(co->items[1])) ? dc_find_tol(m, co->items[1]->text) : -1;
        if (t < 0) return -2;   /* undeclared or non-M0 code tolerance: outside M0 */
        if (m->tol[t].on != m->map[r->encode].to)
            return fail(err, es, "Representation %s: field Codes tolerance is not on the code carrier", nm);
        r->codes = DC_CODES_ALL; r->tol = t;
    }
    for (size_t i = 2; i < d->n; i++)
        if (!sx_head_is(d->items[i], "Of") && !sx_head_is(d->items[i], "Encode") && !sx_head_is(d->items[i], "Codes")) return -2;
    m->nrep++; return 0;
}

static int admit_abs(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n < 5 || !name_ok(d->items[1])) return fail(err, es, "AbstractionMap: expected (AbstractionMap Name (Source S) (Target M) (Map f))");
    const char *nm = d->items[1]->text;
    if (dc_find_abs(m, nm) >= 0) return fail(err, es, "AbstractionMap %s: duplicate name", nm);
    if (m->nabs >= 16) return fail(err, es, "AbstractionMap %s: too many", nm);
    const Sx *so = sx_find(d, "Source", 2), *ta = sx_find(d, "Target", 2), *mp = sx_find(d, "Map", 2);
    for (size_t i = 2; i < d->n; i++)
        if (!sx_head_is(d->items[i], "Source") && !sx_head_is(d->items[i], "Target") && !sx_head_is(d->items[i], "Map")) return -2;
    DcAbsMap *a = &m->abs[m->nabs]; memset(a, 0, sizeof *a); snprintf(a->name, sizeof a->name, "%s", nm);
    if (!so || so->n != 2) return fail(err, es, "AbstractionMap %s: field Source missing", nm);
    if (!ta || ta->n != 2 || !name_ok(ta->items[1]) || (a->target = dc_find_machine(m, ta->items[1]->text)) < 0)
        return fail(err, es, "AbstractionMap %s: field Target names no declared machine (%s)", nm, ta && ta->n == 2 && ta->items[1]->kind == SX_SYM ? ta->items[1]->text : "?");
    if (!mp || mp->n != 2 || !name_ok(mp->items[1]) || (a->map = dc_find_map(m, mp->items[1]->text)) < 0)
        return fail(err, es, "AbstractionMap %s: field Map names no declared map (%s)", nm, mp && mp->n == 2 && mp->items[1]->kind == SX_SYM ? mp->items[1]->text : "?");
    if (m->map[a->map].to != m->mach[a->target].states)
        return fail(err, es, "AbstractionMap %s: field Map does not end at the states of %s", nm, m->mach[a->target].name);
    a->source = sx_copy(so->items[1]);
    m->nabs++; return 0;
}

int dc_find_meas(const DcModule *m, const char *s) { for (size_t i = 0; i < m->nmeas; i++) if (!strcmp(m->meas[i].name, s)) return (int)i; return -1; }
/* M2: (Measure Name (On C) (Uniform)); other laws stay outside the fragment (-2). */
static int admit_meas(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n != 4 || !name_ok(d->items[1]) || !sx_head_is(d->items[3], "Uniform") || d->items[3]->n != 1) return -2;
    const char *nm = d->items[1]->text; const Sx *on = d->items[2];
    if (dc_find_meas(m, nm) >= 0) return fail(err, es, "Measure %s: duplicate name", nm);
    if (m->nmeas >= sizeof m->meas / sizeof m->meas[0]) return fail(err, es, "Measure %s: too many", nm);
    int c = sx_head_is(on, "On") && on->n == 2 && name_ok(on->items[1]) ? dc_find_carrier(m, on->items[1]->text) : -1;
    if (c < 0) return -2;
    if (m->car[c].n == 0) return fail(err, es, "Measure %s: the uniform law needs a nonempty carrier", nm);
    DcMeas *u = &m->meas[m->nmeas++]; memset(u, 0, sizeof *u);
    snprintf(u->name, sizeof u->name, "%s", nm); u->on = c; u->uniform = 1; return 0;
}
static int admit_derive(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n != 3 || !name_ok(d->items[1])) return fail(err, es, "Derive: expected (Derive Name Request)");
    const char *nm = d->items[1]->text;
    if (dc_find_derive(m, nm) >= 0) return fail(err, es, "Derive %s: duplicate name", nm);
    if (m->nder >= 32) return fail(err, es, "Derive %s: too many", nm);
    DcDerive *v = &m->der[m->nder]; snprintf(v->name, sizeof v->name, "%s", nm);
    v->request = sx_copy(d->items[2]);
    m->nder++; return 0;
}

/* ---- M2 value carriers, rational literals and graded tolerances ---- */
int dc_sx_rat(const Sx *v, DcRat *out) {
    if (!v) return -1;
    if (v->kind == SX_SYM) return dc_rat_parse(v->text, out);
    if (v->kind == SX_LIST && v->n == 3 && sx_is_sym(v->items[0], "Rat") && v->items[1]->kind == SX_SYM && v->items[2]->kind == SX_SYM) {
        DcRat a, b; int ovf = 0;
        if (dc_rat_parse(v->items[1]->text, &a) || dc_rat_parse(v->items[2]->text, &b) || b.n <= 0 || a.d != 1 || b.d != 1) return -1;
        *out = dc_rat(a.n, b.n, &ovf); return ovf ? -1 : 0;
    }
    return -1;
}
static Sx *rat_sx(DcRat r) {
    char b[32]; Sx *l = sx_list(); sx_push(l, sx_sym("Rat"));
    snprintf(b, sizeof b, "%lld", (long long)r.n); sx_push(l, sx_sym(b));
    snprintf(b, sizeof b, "%lld", (long long)r.d); sx_push(l, sx_sym(b)); return l;
}
int dc_value_carrier(DcModule *m, const char *name) {
    if (strcmp(name, "Rational01") && strcmp(name, "Rational")) return -1;
    for (size_t i = 0; i < m->ncar; i++) if (m->car[i].value && !strcmp(m->car[i].name, name)) return (int)i;
    if (m->ncar >= sizeof m->car / sizeof m->car[0]) return -1;
    DcCarrier *c = &m->car[m->ncar]; memset(c, 0, sizeof *c);
    snprintf(c->name, sizeof c->name, "%s", name); c->value = 1; return (int)m->ncar++;
}
/* Adds a rational value in canonical (Rat n d) form; Rational01 values must lie in [0,1]. */
int dc_value_add(DcCarrier *c, const Sx *v) {
    DcRat r; if (dc_sx_rat(v, &r)) return -1;
    if (!strcmp(c->name, "Rational01") && (r.n < 0 || r.n > r.d)) return -1;
    Sx *k = rat_sx(r); int at = dc_carrier_index(c, k);
    if (at >= 0) { sx_free(k); return at; }
    if (c->n >= 4096) { sx_free(k); return -1; }
    Sx **e = realloc(c->elems, (c->n + 1) * sizeof *e); if (!e) { sx_free(k); return -1; }
    c->elems = e; c->elems[c->n] = k; return (int)c->n++;
}
DcRat dc_tol_dist(const DcModule *m, int tol, int i, int j, int *ovf) {
    const DcTol *t = &m->tol[tol]; DcRat z = {0, 1}, one = {1, 1};
    switch (t->kind) {
    case DC_TOL_TRIVIAL: return z;
    case DC_TOL_DISCRETE: return i == j ? z : one;
    case DC_TOL_ONE_MINUS_ABS: {
        DcRat a, b; const DcCarrier *c = &m->car[t->on];
        if (dc_sx_rat(c->elems[i], &a) || dc_sx_rat(c->elems[j], &b)) { *ovf = 1; return z; }
        return dc_rat_abs(dc_rat_sub(a, b, ovf)); }
    case DC_TOL_SYM_TABLE: return dc_rat_sub(one, t->table[(size_t)i * m->car[t->on].n + j], ovf);
    }
    return z;
}

static int admit_tol(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n != 4 || !name_ok(d->items[1])) return -2;
    const char *nm = d->items[1]->text;
    const Sx *on = d->items[2], *body = d->items[3];
    DcTolKind kind;
    if (sx_head_is(body, "Trivial") && body->n == 1) kind = DC_TOL_TRIVIAL;
    else if (sx_head_is(body, "Discrete") && body->n == 1) kind = DC_TOL_DISCRETE;
    else if (sx_head_is(body, "OneMinusAbsoluteDifference") && body->n == 1) kind = DC_TOL_ONE_MINUS_ABS;
    else if (sx_head_is(body, "SymmetricTable") && body->n >= 2) kind = DC_TOL_SYM_TABLE;
    else return -2;
    if (dc_find_tol(m, nm) >= 0) return fail(err, es, "Tolerance %s: duplicate name", nm);
    if (m->ntol >= 16) return fail(err, es, "Tolerance %s: too many", nm);
    int c = -1;
    if (sx_head_is(on, "On") && on->n == 2 && name_ok(on->items[1])) {
        c = dc_find_carrier(m, on->items[1]->text);
        if (c < 0 && kind == DC_TOL_ONE_MINUS_ABS) c = dc_value_carrier(m, on->items[1]->text);
    }
    if (c < 0) return fail(err, es, "Tolerance %s: field On names no declared carrier", nm);
    if (kind == DC_TOL_ONE_MINUS_ABS && !m->car[c].value) return fail(err, es, "Tolerance %s: OneMinusAbsoluteDifference needs a rational carrier", nm);
    DcRat *tab = NULL;
    if (kind == DC_TOL_SYM_TABLE) {
        size_t n = m->car[c].n; tab = calloc(n ? n * n : 1, sizeof *tab); char *set = calloc(n ? n * n : 1, 1);
        if (!tab || !set) { free(tab); free(set); return fail(err, es, "Tolerance %s: out of memory", nm); }
        int bad = 0; DcRat diag = {1, 1};
        for (size_t k = 1; k < body->n && !bad; k++) {
            const Sx *e = body->items[k]; DcRat v;
            if (sx_head_is(e, "Diagonal") && e->n == 2) { if (dc_sx_rat(e->items[1], &diag)) bad = 1; continue; }
            if (e->kind != SX_LIST || e->n != 3 || dc_sx_rat(e->items[2], &v)) { bad = 1; break; }
            int a = dc_carrier_index(&m->car[c], e->items[0]), b = dc_carrier_index(&m->car[c], e->items[1]);
            if (a < 0 || b < 0 || a == b || v.n < 0 || v.n > v.d || set[(size_t)a * n + b]) { bad = 1; break; }
            tab[(size_t)a * n + b] = tab[(size_t)b * n + a] = v; set[(size_t)a * n + b] = set[(size_t)b * n + a] = 1;
        }
        for (size_t a = 0; a < n && !bad; a++) for (size_t b = 0; b < n; b++)
            if (a == b) tab[a * n + b] = diag; else if (!set[a * n + b]) bad = 2;
        free(set);
        if (bad) { free(tab); return fail(err, es, bad == 2 ? "Tolerance %s: SymmetricTable misses a pair" : "Tolerance %s: malformed SymmetricTable entry", nm); }
    }
    DcTol *t = &m->tol[m->ntol++]; memset(t, 0, sizeof *t); snprintf(t->name, sizeof t->name, "%s", nm);
    t->on = c; t->kind = kind; t->trivial = kind == DC_TOL_TRIVIAL; t->table = tab;
    return 0;
}

static void note_unsupported(DcModule *m, const char *what) {
    if (!m->unsupported_decls++) snprintf(m->unsupported_first, sizeof m->unsupported_first, "%s", what);
}
int dc_is_skipped(const DcModule *m, const char *name) {
    for (size_t i = 0; i < m->nskip; i++) if (!strcmp(m->skipped[i], name)) return 1;
    return 0;
}
/* An admission error that only references a skipped declaration ("... (Name)")
 * is a fragment limit too. */
static int refers_to_skipped(const DcModule *m, const char *err) {
    const char *o = strrchr(err, '('), *c = o ? strchr(o, ')') : NULL;
    if (!o || !c || c - o - 1 >= DC_MAX_NAME) return 0;
    char nm[DC_MAX_NAME]; memcpy(nm, o + 1, (size_t)(c - o - 1)); nm[c - o - 1] = 0;
    static const char *const builtin[] = { "Nat", "Int", "Rational", "Rational01", "Real", "Symbol", "String", "Bool", "PBit", "Dist", NULL };
    for (int i = 0; builtin[i]; i++) if (!strcmp(builtin[i], nm)) return 1;
    return dc_is_skipped(m, nm);
}

int dc_admit(const Sx *form, DcModule *m, char *err, size_t es) {
    memset(m, 0, sizeof *m);
    if (!sx_head_is(form, "DC.Module") || form->n < 2 || !name_ok(form->items[1]))
        return fail(err, es, "DC.Module: expected (DC.Module Name decl...)");
    snprintf(m->name, sizeof m->name, "%s", form->items[1]->text);
    m->source = sx_copy(form);
    char *canon = sx_print(form); dc_sha256_hex(canon, strlen(canon), m->digest); free(canon);
    m->contracts = uses_lib(m, "Contracts") && dc_eval_beyond_release();   /* M6 opt-in */
    m->hives = uses_lib(m, "Hives") && dc_eval_beyond_release();   /* M6 opt-in */
    m->transfers = uses_lib(m, "Transfers") && dc_eval_beyond_release();   /* M6 opt-in */
    for (size_t i = 2; i < form->n; i++) {
        const Sx *d = form->items[i]; int rc = 0;
        if (d->kind != SX_LIST || d->n == 0 || d->items[0]->kind != SX_SYM)
            return fail(err, es, "DC.Module %s: declaration %zu is not a form", m->name, i - 2);
        const char *h = d->items[0]->text;
        if (!strcmp(h, "Profile")) {
            /* (Profile Name) or (Profile (Dynamics D) (Values V) (Carriers C)).
             * M0 admits Deterministic dynamics on Enumerated carriers; any other
             * profile is a well-formed module outside M0: Unsupported, not InvalidInput. */
            if (d->n == 2 && name_ok(d->items[1])) {
                const char *pn = d->items[1]->text;
                snprintf(m->profile, sizeof m->profile, "%s", pn);
                /* review 2 F4: the single-symbol form must gate like (Dynamics ...):
                 * Nondeterministic and Stochastic modules are outside M0. */
                if (!strcmp(pn, "Stochastic") && dc_eval_beyond_release()) { m->stochastic = 1; continue; }   /* M4 opt-in */
                if (!strcmp(pn, "Nondeterministic") && dc_eval_beyond_release()) { m->nondet = 1; continue; }   /* M5 opt-in */
                if ((!strcmp(pn, "Nondeterministic") || !strcmp(pn, "Stochastic")) && !m->profile_unsupported[0])
                    snprintf(m->profile_unsupported, sizeof m->profile_unsupported, "Profile %s is outside the M0 fragment", pn);
                continue;
            }
            for (size_t k = 1; k < d->n; k++) {
                const Sx *f = d->items[k];
                if (f->kind != SX_LIST || f->n != 2 || !name_ok(f->items[0]) || !name_ok(f->items[1]))
                    return fail(err, es, "Profile: field %zu is not (Key Value)", k);
                const char *key = f->items[0]->text, *val = f->items[1]->text;
                if (!strcmp(key, "Values")) snprintf(m->profile, sizeof m->profile, "%s", val);
                else if (!strcmp(key, "Carriers") && !strcmp(val, "Symbolic")) m->symbolic = 1;   /* M3 */
                else if (!strcmp(key, "Dynamics") && !strcmp(val, "Stochastic") && dc_eval_beyond_release()) m->stochastic = 1;   /* M4 opt-in */
                else if (!strcmp(key, "Dynamics") && !strcmp(val, "Nondeterministic") && dc_eval_beyond_release()) m->nondet = 1;   /* M5 opt-in */
                else if ((!strcmp(key, "Dynamics") && strcmp(val, "Deterministic")) || (!strcmp(key, "Carriers") && strcmp(val, "Enumerated")))
                    { if (!m->profile_unsupported[0]) snprintf(m->profile_unsupported, sizeof m->profile_unsupported, "Profile %s %s is outside the M0 fragment", key, val); }
                else if (strcmp(key, "Dynamics") && strcmp(key, "Carriers"))
                    { if (!m->profile_unsupported[0]) snprintf(m->profile_unsupported, sizeof m->profile_unsupported, "Profile field %s is outside the M0 fragment", key); }
            }
            continue;
        }
        else if (m->stochastic && strcmp(h, "Derive")) continue;   /* M4: stochastic decls are read by stoch.c from m->source */
        else if (m->contracts && !strcmp(h, "Implementation")) continue;   /* M6: read by ops_contracts.c from m->source */
        else if (m->nondet && strcmp(h, "Derive")) continue;   /* M5: nondeterministic decls are read by ops_nondet.c from m->source */
        else if (m->symbolic && strcmp(h, "Derive")) continue;   /* M3: symbolic decls are read by sym.c from m->source */
        else if (!strcmp(h, "Carrier")) rc = admit_carrier(m, d, err, es);
        else if (!strcmp(h, "Map")) rc = admit_map(m, d, err, es);
        else if (!strcmp(h, "Machine")) rc = admit_machine(m, d, err, es);
        else if (!strcmp(h, "Representation")) rc = admit_repr(m, d, err, es);
        else if (!strcmp(h, "AbstractionMap")) rc = admit_abs(m, d, err, es);
        else if (!strcmp(h, "Derive")) rc = admit_derive(m, d, err, es);
        else if (!strcmp(h, "Tolerance")) rc = admit_tol(m, d, err, es);
        else if (!strcmp(h, "Measure")) rc = admit_meas(m, d, err, es);
        else rc = -2;
        if (rc == -1 && (strstr(err, "[M0]") || refers_to_skipped(m, err))) rc = -2;
        if (rc == -2 && !strcmp(h, "Import")) {
            /* imported names come from another module: outside M0 */
            const Sx *only = sx_find(d, "Only", 2);
            for (size_t k = 1; only && k < only->n; k++)
                if (only->items[k]->kind == SX_SYM && m->nskip < 64)
                    snprintf(m->skipped[m->nskip++], DC_MAX_NAME, "%.63s", only->items[k]->text);
        }
        if (rc == -2) {
            if (d->n > 1 && d->items[1]->kind == SX_SYM && m->nskip < 64)
                snprintf(m->skipped[m->nskip++], DC_MAX_NAME, "%.63s", d->items[1]->text);
            char what[DC_MAX_NAME + 32];
            snprintf(what, sizeof what, "%s %s", h, d->n > 1 && d->items[1]->kind == SX_SYM ? d->items[1]->text : "");
            note_unsupported(m, what); rc = 0;
        }
        if (rc) return -1;
    }
    return 0;
}

void dc_module_free(DcModule *m) {
    for (size_t i = 0; i < m->ncar; i++) { for (size_t j = 0; j < m->car[i].n; j++) sx_free(m->car[i].elems[j]); free(m->car[i].elems); free(m->car[i].sub_idx); }
    for (size_t i = 0; i < m->nmap; i++) free(m->map[i].table);
    for (size_t i = 0; i < m->ntol; i++) free(m->tol[i].table);
    for (size_t i = 0; i < m->nabs; i++) sx_free(m->abs[i].source);
    for (size_t i = 0; i < m->nder; i++) sx_free(m->der[i].request);
    sx_free(m->source);
    memset(m, 0, sizeof *m);
}
