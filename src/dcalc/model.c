/* Admission of DC.Module sources into the enumerated deterministic model. */
#include "model.h"
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

static int admit_carrier(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n < 4 || !name_ok(d->items[1])) return fail(err, es, "[M0] Carrier: expected (Carrier Name (Of T) (Enum ...)|(Product ...))");
    const char *nm = d->items[1]->text;
    if (dc_find_carrier(m, nm) >= 0) return fail(err, es, "Carrier %s: duplicate name", nm);
    if (m->ncar >= 32) return fail(err, es, "Carrier %s: too many carriers", nm);
    const Sx *body = d->items[3];
    DcCarrier *c = &m->car[m->ncar];
    memset(c, 0, sizeof *c); snprintf(c->name, sizeof c->name, "%s", nm);
    if (sx_head_is(body, "Enum")) {
        c->n = body->n - 1; c->elems = calloc(c->n ? c->n : 1, sizeof(Sx *));
        for (size_t i = 0; i < c->n; i++) {
            if (body->items[i + 1]->kind == SX_LIST) { car_drop(c); return fail(err, es, "[M0] Carrier %s: Enum element %zu is not atomic", nm, i); }
            for (size_t j = 0; j < i; j++) if (sx_equal(c->elems[j], body->items[i + 1])) { int rc = fail(err, es, "Carrier %s: duplicate Enum element %s", nm, body->items[i + 1]->text); car_drop(c); return rc; }
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

static int admit_map(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n != 5 || !name_ok(d->items[1])) return fail(err, es, "[M0] Map: expected (Map name (From C) (To C) (Table|Cases ...))");
    const char *nm = d->items[1]->text;
    if (dc_find_map(m, nm) >= 0) return fail(err, es, "Map %s: duplicate name", nm);
    if (m->nmap >= 64) return fail(err, es, "Map %s: too many maps", nm);
    const Sx *fr = d->items[2], *to = d->items[3], *body = d->items[4];
    if (!sx_head_is(fr, "From") || fr->n != 2 || !name_ok(fr->items[1])) return fail(err, es, "[M0] Map %s: field From", nm);
    if (!sx_head_is(to, "To") || to->n != 2 || !name_ok(to->items[1])) return fail(err, es, "[M0] Map %s: field To", nm);
    int f = dc_find_carrier(m, fr->items[1]->text), t = dc_find_carrier(m, to->items[1]->text);
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
            int a = dc_carrier_index(F, row->items[0]), b = dc_carrier_index(T, row->items[1]);
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
                Sx *v = eval_body(row->items[1], &e, &ok);
                if (ok == 2) { sx_free(v); free(mp->table); return fail(err, es, "[M0] Map %s: Cases row %zu uses an operator outside the M0 fragment", nm, j - 1); }
                if (ok == 3) { sx_free(v); free(mp->table); return fail(err, es, "Map %s: Cases row %zu: integer overflow or out-of-range literal in Add/Mul", nm, j - 1); }
                int b = ok ? dc_carrier_index(T, v) : -1; sx_free(v);
                if (b < 0) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu gives a value outside carrier %s", nm, j - 1, T->name); }
                mp->table[i] = b; break;
            }
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
    if (d->n > 3 && name_ok(d->items[1]) && name_ok(d->items[2]))
        return fail(err, es, "[M0] Machine %s: field %s with value tolerances is outside the M0 deterministic fragment", mc->name, field);
    /* (Observe label (map arg ...)): an applied, parameterised map is outside M0 */
    if (d->n == 3 && name_ok(d->items[1]) && d->items[2]->kind == SX_LIST) return -2;
    if (d->n != 3 || !name_ok(d->items[1]) || !name_ok(d->items[2])) return fail(err, es, "Machine %s: field %s expects (%s label map)", mc->name, field, field);
    if (*np >= 16) return fail(err, es, "Machine %s: field %s: too many", mc->name, field);
    int mp = dc_find_map(m, d->items[2]->text);
    if (mp < 0) return fail(err, es, "Machine %s: field %s names no declared map (%s)", mc->name, field, d->items[2]->text);
    if (m->map[mp].from != mc->states) return fail(err, es, "Machine %s: field %s map %s does not start at the state carrier", mc->name, field, d->items[2]->text);
    if (!is_obs && m->map[mp].to != mc->states) return fail(err, es, "Machine %s: field Action map %s does not end at the state carrier", mc->name, d->items[2]->text);
    for (size_t i = 0; i < *np; i++) if (!strcmp(ports[i].label, d->items[1]->text)) return fail(err, es, "Machine %s: field %s label %s repeated", mc->name, field, d->items[1]->text);
    snprintf(ports[*np].label, DC_MAX_NAME, "%s", d->items[1]->text); ports[*np].map = mp; (*np)++;
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

static int admit_derive(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n != 3 || !name_ok(d->items[1])) return fail(err, es, "Derive: expected (Derive Name Request)");
    const char *nm = d->items[1]->text;
    if (dc_find_derive(m, nm) >= 0) return fail(err, es, "Derive %s: duplicate name", nm);
    if (m->nder >= 32) return fail(err, es, "Derive %s: too many", nm);
    DcDerive *v = &m->der[m->nder]; snprintf(v->name, sizeof v->name, "%s", nm);
    v->request = sx_copy(d->items[2]);
    m->nder++; return 0;
}

static int admit_tol(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n != 4 || !name_ok(d->items[1])) return -2;
    const char *nm = d->items[1]->text;
    const Sx *on = d->items[2], *body = d->items[3];
    if (!sx_head_is(body, "Trivial") || body->n != 1) return -2;   /* only Trivial is in M0 */
    if (dc_find_tol(m, nm) >= 0) return fail(err, es, "Tolerance %s: duplicate name", nm);
    if (m->ntol >= 16) return fail(err, es, "Tolerance %s: too many", nm);
    int c = (sx_head_is(on, "On") && on->n == 2 && name_ok(on->items[1])) ? dc_find_carrier(m, on->items[1]->text) : -1;
    if (c < 0) return fail(err, es, "Tolerance %s: field On names no declared carrier", nm);
    DcTol *t = &m->tol[m->ntol++]; snprintf(t->name, sizeof t->name, "%s", nm); t->on = c; t->trivial = 1;
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
                else if ((!strcmp(key, "Dynamics") && strcmp(val, "Deterministic")) || (!strcmp(key, "Carriers") && strcmp(val, "Enumerated")))
                    { if (!m->profile_unsupported[0]) snprintf(m->profile_unsupported, sizeof m->profile_unsupported, "Profile %s %s is outside the M0 fragment", key, val); }
                else if (strcmp(key, "Dynamics") && strcmp(key, "Carriers"))
                    { if (!m->profile_unsupported[0]) snprintf(m->profile_unsupported, sizeof m->profile_unsupported, "Profile field %s is outside the M0 fragment", key); }
            }
            continue;
        }
        else if (!strcmp(h, "Carrier")) rc = admit_carrier(m, d, err, es);
        else if (!strcmp(h, "Map")) rc = admit_map(m, d, err, es);
        else if (!strcmp(h, "Machine")) rc = admit_machine(m, d, err, es);
        else if (!strcmp(h, "Representation")) rc = admit_repr(m, d, err, es);
        else if (!strcmp(h, "AbstractionMap")) rc = admit_abs(m, d, err, es);
        else if (!strcmp(h, "Derive")) rc = admit_derive(m, d, err, es);
        else if (!strcmp(h, "Tolerance")) rc = admit_tol(m, d, err, es);
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
    for (size_t i = 0; i < m->ncar; i++) { for (size_t j = 0; j < m->car[i].n; j++) sx_free(m->car[i].elems[j]); free(m->car[i].elems); }
    for (size_t i = 0; i < m->nmap; i++) free(m->map[i].table);
    for (size_t i = 0; i < m->nabs; i++) sx_free(m->abs[i].source);
    for (size_t i = 0; i < m->nder; i++) sx_free(m->der[i].request);
    sx_free(m->source);
    memset(m, 0, sizeof *m);
}
