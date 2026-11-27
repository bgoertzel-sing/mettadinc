/* Admission of DC.Module sources into the enumerated deterministic model. */
#include "model.h"
#include "maprules.h"
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

static int name_frag(const DcModule *m, const char *nm);   /* lowering-unsupported */
/* The implicit Bool carrier is never found by name: only a (To Bool) Observe map reaches it (bool_carrier). */
int dc_find_carrier(const DcModule *m, const char *s) { for (size_t i = 0; i < m->ncar; i++) if (!m->car[i].builtin_bool && !strcmp(m->car[i].name, s)) return (int)i; return -1; }
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
static int allow_xor;   /* M7: set by admit_map only on a (Use Neural) module in beyond-release: (Xor a b) on bits */
static int allow_nat;   /* NatArith (beyond-release opt-in): set with allow_xor around eval_body on a (Use NatArith) module */
static int nat_head(const Sx *b) {
    if (b->kind != SX_LIST || !b->n || b->items[0]->kind != SX_SYM) return 0;
    const char *h = b->items[0]->text;
    return !strcmp(h, "Le") || !strcmp(h, "Lt") || !strcmp(h, "Min") || !strcmp(h, "Max") || !strcmp(h, "Quot") || !strcmp(h, "Rem");
}
static int nat_failed(const Sx *v) { return v && v->kind == SX_LIST && v->n == 2 && v->items[0]->kind == SX_SYM && !strcmp(v->items[0]->text, "Failed"); }
static int allow_bool;  /* set only by admit_bool_observe_map: (To Bool) resolves to the implicit Bool carrier */
static char pending_why[256];   /* a form-specific reason for the declaration being admitted when it returns -2 (Bool Observe maps, type-form maps, Like machines and what uses them), "" if none */
/* ---- If/Eq/And/Or/Not in Cases bodies (t-2026-11-23-mettadinc-m0-cases-logic) ----
 * Spec 5.1 grammar (l.1721): map-body ::= (Cases (pattern expr)+); spec 5.4 (l.1858): admitted
 * expressions include "registered pure primitives, each total on its declared input type".  The
 * registry lists Eq, If, Not, And and Or among the Core primitives (libraries.Core.primitives) and
 * Bool among Core's builtin types.  Meaning, as in Ben's reference evaluators (docs/e0 mg_eval.py
 * World.ev, ls_eval.py, metta_eval.py):
 *   (Eq a b)        True iff a and b are the same value (literal equality; integer literals by value at
 *                   every depth, so (Tuple 1) and (Tuple 01) are the same value)
 *   (If c a b)      a if c is True, b if c is False; only the chosen branch is evaluated
 *   (Not c)         the Boolean complement
 *   (And c1 c2 ...) True iff every ci is True;  (Or c1 c2 ...) True iff some ci is True (two or more operands)
 * Lowered only in the Crisp profile (allow_logic, set where a Crisp module's Cases body is tabulated).
 * Malformed uses (If/Eq/Not with the wrong number of arguments; an If condition or a Not/And/Or
 * operand that is not True or False) set *ok = 4, the reason in logic_why: InvalidInput.
 * And/Or with fewer than two operands, a Const name read by one of these forms (anywhere in an operand
 * it evaluates: directly, or nested in a Tuple, Add or Mul; review 1 F1), and these forms in a non-Crisp
 * module, stay outside the fragment (*ok = 2), the form named in logic_why: Unsupported. */
static int allow_logic;
static const DcModule *logic_mod;   /* with allow_logic: the module (its Const declarations) */
static char logic_why[200];         /* the reason when eval_body sets *ok to 4, or to 2 on a logic form; "" otherwise */
static void logic_bad(int *ok, int code, const char *fmt, ...) {
    if (*ok != 1) return;
    va_list ap; va_start(ap, fmt); vsnprintf(logic_why, sizeof logic_why, fmt, ap); va_end(ap); *ok = code;
}
static int logic_head(const Sx *b) {
    if (b->kind != SX_LIST || !b->n || b->items[0]->kind != SX_SYM) return 0;
    const char *h = b->items[0]->text;
    return !strcmp(h, "If") || !strcmp(h, "Eq") || !strcmp(h, "Not") || !strcmp(h, "And") || !strcmp(h, "Or");
}
static const Sx *find_decl(const DcModule *m, const char *head, const char *name);
static Sx *eval_body(const Sx *b, const Env *e, int *ok);
static int logic_head(const Sx *b);
/* review 1 F1: the first Const name in an operand tree, or NULL.  A nested logic form is not entered: it
 * checks its own operands when (and only if) it is evaluated, so an untaken If branch is not read. */
static const char *logic_const_in(const Sx *a) {
    if (a->kind == SX_SYM) return a->text[0] != '$' && find_decl(logic_mod, "Const", a->text) ? a->text : NULL;
    if (a->kind != SX_LIST || logic_head(a)) return NULL;
    for (size_t i = 0; i < a->n; i++) { const char *c = logic_const_in(a->items[i]); if (c) return c; }
    return NULL;
}
/* an operand of a logic form; a Const name is not resolved by this lowering (outside the fragment) */
static Sx *logic_arg(const char *h, const Sx *a, const Env *e, int *ok) {
    const char *c = logic_mod ? logic_const_in(a) : NULL;
    if (c) {
        logic_bad(ok, 2, "(%s ...) reads the Const %s, which the M0 lowering of %s does not resolve", h, c, h);
        return sx_sym("?");
    }
    return eval_body(a, e, ok);
}
/* review 1 F2: Eq's value equality, integer literals by value at every depth (the reference compares Python values) */
static int parse_int(const Sx *x, long *out);
static int logic_eq(const Sx *x, const Sx *y) {
    if (x->kind != y->kind) return 0;
    if (x->kind == SX_LIST) {
        if (x->n != y->n) return 0;
        for (size_t i = 0; i < x->n; i++) if (!logic_eq(x->items[i], y->items[i])) return 0;
        return 1;
    }
    long a, c;
    if (x->kind == SX_SYM && parse_int(x, &a) == 1 && parse_int(y, &c) == 1) return a == c;
    return sx_equal(x, y);
}
static void logic_on(const DcModule *m) { allow_logic = !strcmp(m->profile, "Crisp"); logic_mod = m; logic_why[0] = 0; }   /* around eval_body only */
static void logic_off(void) { allow_logic = 0; logic_mod = NULL; }
static int bool_of(const Sx *v) { return sx_is_sym(v, "True") ? 1 : sx_is_sym(v, "False") ? 0 : -1; }
static int parse_int(const Sx *x, long *out);
static Sx *eval_logic(const Sx *b, const Env *e, int *ok) {
    const char *h = b->items[0]->text; size_t na = b->n - 1;
    if (!strcmp(h, "Eq")) {
        if (na != 2) { logic_bad(ok, 4, "(Eq ...) takes 2 arguments, not %zu", na); return sx_sym("?"); }
        Sx *x = logic_arg(h, b->items[1], e, ok), *y = logic_arg(h, b->items[2], e, ok);
        if (*ok != 1) { sx_free(x); sx_free(y); return sx_sym("?"); }
        int eq = logic_eq(x, y);
        sx_free(x); sx_free(y); return sx_sym(eq ? "True" : "False");
    }
    if (!strcmp(h, "If")) {
        if (na != 3) { logic_bad(ok, 4, "(If ...) takes 3 arguments (condition, then, else), not %zu", na); return sx_sym("?"); }
        Sx *c = logic_arg(h, b->items[1], e, ok);
        if (*ok != 1) { sx_free(c); return sx_sym("?"); }
        int t = bool_of(c);
        if (t < 0) { char *s = sx_print(c); logic_bad(ok, 4, "the condition of (If ...) gives %s, which is not True or False", s); free(s); sx_free(c); return sx_sym("?"); }
        sx_free(c);
        return logic_arg(h, b->items[t ? 2 : 3], e, ok);
    }
    if (!strcmp(h, "Not") && na != 1) { logic_bad(ok, 4, "(Not ...) takes 1 argument, not %zu", na); return sx_sym("?"); }
    if (strcmp(h, "Not") && na < 2) { logic_bad(ok, 2, "(%s ...) with %zu operand%s is outside the M0 fragment, which admits %s with two or more", h, na, na == 1 ? "" : "s", h); return sx_sym("?"); }
    int acc = !strcmp(h, "Or") ? 0 : 1;
    for (size_t i = 1; i < b->n; i++) {
        Sx *v = logic_arg(h, b->items[i], e, ok);
        if (*ok != 1) { sx_free(v); return sx_sym("?"); }
        int t = bool_of(v);
        if (t < 0) { char *s = sx_print(v); logic_bad(ok, 4, "operand %zu of (%s ...) gives %s, which is not True or False", i, h, s); free(s); sx_free(v); return sx_sym("?"); }
        sx_free(v);
        if (!strcmp(h, "Not")) acc = !t; else if (!strcmp(h, "And")) acc = acc && t; else acc = acc || t;
    }
    return sx_sym(acc ? "True" : "False");
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
    if (allow_nat && nat_head(b) && b->n == 3) {   /* NatArith: doc03 s3.13 l.1170-1172 and B.1 l.4395-4398 */
        const char *h = b->items[0]->text;
        Sx *x = eval_body(b->items[1], e, ok), *y = eval_body(b->items[2], e, ok);
        if (*ok == 1 && nat_failed(x)) { sx_free(y); return x; }   /* a tagged failure propagates */
        if (*ok == 1 && nat_failed(y)) { sx_free(x); return y; }
        long a, c; char buf[32];
        int pa = *ok == 1 ? parse_int(x, &a) : 0, pc = *ok == 1 ? parse_int(y, &c) : 0;
        sx_free(x); sx_free(y);
        if (pa < 0 || pc < 0) { *ok = 3; return sx_sym("?"); }   /* out-of-range literal */
        if (*ok != 1 || !pa || !pc) { if (*ok == 1) *ok = 0; return sx_sym("?"); }
        if (!strcmp(h, "Le")) return sx_sym(a <= c ? "True" : "False");
        if (!strcmp(h, "Lt")) return sx_sym(a < c ? "True" : "False");
        long r;
        if (!strcmp(h, "Min")) r = a < c ? a : c;
        else if (!strcmp(h, "Max")) r = a > c ? a : c;
        else {
            /* doc03 B.1 l.4395-4396: "Quot and Rem need a positive divisor and return a tagged failure value
             * otherwise"; tag shape from spec s12.7 l.3368-3369 (Failed Reason) */
            if (c <= 0) { Sx *f = sx_list(); sx_push(f, sx_sym("Failed")); sx_push(f, sx_sym("NonPositiveDivisor")); return f; }
            long q = a / c; if (a % c != 0 && a < 0) q--;   /* doc03 l.1166: Quot is floor division (c > 0) */
            r = !strcmp(h, "Quot") ? q : a - q * c;
        }
        snprintf(buf, sizeof buf, "%ld", r); return sx_sym(buf);
    }
    if (allow_nat && !allow_logic && sx_head_is(b, "If") && b->n == 4) {   /* doc03 s3.13 l.1172: If evaluates only one branch */
        Sx *cnd = eval_body(b->items[1], e, ok);
        if (*ok == 1 && nat_failed(cnd)) return cnd;
        int t = *ok == 1 ? bool_of(cnd) : -1; sx_free(cnd);
        if (*ok != 1) return sx_sym("?");
        if (t < 0) { *ok = 4; return sx_sym("?"); }
        return eval_body(b->items[t ? 2 : 3], e, ok);
    }
    if (allow_xor && sx_head_is(b, "Xor") && b->n == 3) {   /* M7 opt-in: bitwise xor of two 0/1 literals */
        Sx *x = eval_body(b->items[1], e, ok), *y = eval_body(b->items[2], e, ok); long a = -1, c = -1;
        int pa = *ok == 1 ? parse_int(x, &a) : 0, pc = *ok == 1 ? parse_int(y, &c) : 0; sx_free(x); sx_free(y);
        if (*ok != 1 || pa != 1 || pc != 1 || (a != 0 && a != 1) || (c != 0 && c != 1)) { if (*ok == 1) *ok = 0; return sx_sym("?"); }
        return sx_sym(a != c ? "1" : "0");
    }
    if (allow_rat && sx_head_is(b, "Rat") && b->n == 3) return sx_copy(b);
    if (allow_logic && logic_head(b)) return eval_logic(b, e, ok);
    if (logic_mod && logic_head(b)) { logic_bad(ok, 2, "(%s ...) in a Cases body is lowered only in a Crisp module, not in profile %s", b->items[0]->text, logic_mod->profile); return sx_sym("?"); }
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
/* spec 5.3 l.1810-1812 "Reachability scopes": (Reach M (From s...)) is the forward closure of the
 * initial set under the actions of M.  One closure for both backends: the M0 lowering (admit_reach,
 * successors = the images of the action maps) and the stochastic reader (stoch.c, successors = the
 * support of the action kernels, mass > 0).  in[0..n) marks the starts on entry and the closure on
 * return; succ writes the successors of x into out (at most maxs) and returns their count.
 * Returns the closure size, or (size_t)-1 if memory runs out. */
size_t dc_forward_closure(size_t n, int *in, size_t maxs, size_t (*succ)(void *ctx, int x, int *out), void *ctx) {
    int *qu = malloc((n ? n : 1) * sizeof(int)), *out = malloc((maxs ? maxs : 1) * sizeof(int)); size_t h = 0, t = 0;
    if (!qu || !out) { free(qu); free(out); return (size_t)-1; }
    for (size_t i = 0; i < n; i++) if (in[i]) qu[t++] = (int)i;
    while (h < t) {
        int x = qu[h++]; size_t k = succ(ctx, x, out);
        for (size_t j = 0; j < k && j < maxs; j++) { int y = out[j]; if (y >= 0 && (size_t)y < n && !in[y]) { in[y] = 1; qu[t++] = y; } }
    }
    free(qu); free(out); return t;
}
typedef struct { const DcModule *m; const DcMachine *mc; } ReachDet;
static size_t reach_det_succ(void *ctx, int x, int *out) {
    const ReachDet *r = ctx;
    for (size_t a = 0; a < r->mc->nact; a++) out[a] = r->m->map[r->mc->act[a].map].table[x];
    return r->mc->nact;
}
static const Sx *find_decl(const DcModule *m, const char *head, const char *name);
static int admit_reach(DcModule *m, DcCarrier *c, const char *nm, const Sx *body, char *err, size_t es) {
    /* spec 5.3 "Reachability scopes": (Reach M (From s...)) denotes the forward closure of the
     * initial set under the actions of M.  Enumerated: bounded by M's state carrier (<= 4096). */
    if (strcmp(m->profile, "Graded") && strcmp(m->profile, "Crisp")) return -2;
    const Sx *fr = body->n == 3 ? body->items[2] : NULL;
    int mi = body->n == 3 && name_ok(body->items[1]) ? dc_find_machine(m, body->items[1]->text) : -1;
    /* a machine skipped as outside the fragment makes its Reach scope outside it too */
    if (mi < 0 && body->n == 3 && name_ok(body->items[1]) && dc_is_skipped(m, body->items[1]->text)) { snprintf(pending_why, sizeof pending_why, "%s", dc_skip_why(m, body->items[1]->text)); return -2; }
    if (mi < 0 || !sx_head_is(fr, "From") || fr->n < 2) return fail(err, es, "Carrier %s: expected (Reach Machine (From e ...)) after the machine is declared", nm);
    const DcMachine *mc = &m->mach[mi]; const DcCarrier *P = &m->car[mc->states]; size_t n = P->n;
    int *in = calloc(n ? n : 1, sizeof(int));
    for (size_t k = 1; k < fr->n; k++) {
        int i = dc_carrier_index(P, fr->items[k]);
        if (i < 0 && name_ok(fr->items[k])) {   /* a start may name a declared (Const name Carrier value) */
            const Sx *cd = find_decl(m, "Const", fr->items[k]->text);
            if (cd && cd->n == 4) i = dc_carrier_index(P, cd->items[3]);
        }
        if (i < 0) { char *x = sx_print(fr->items[k]); fail(err, es, "Carrier %s: Reach start %s is not a state of %s", nm, x, mc->name); free(x); free(in); return -1; }
        in[i] = 1;
    }
    ReachDet rd = { m, mc }; size_t t = dc_forward_closure(n, in, mc->nact, reach_det_succ, &rd);
    if (t == (size_t)-1) { free(in); return fail(err, es, "Carrier %s: out of memory computing the Reach scope", nm); }
    c->n = t; c->elems = calloc(t ? t : 1, sizeof(Sx *)); c->sub_idx = malloc((t ? t : 1) * sizeof(int));
    size_t k = 0; for (size_t i = 0; i < n; i++) if (in[i]) { c->elems[k] = sx_copy(P->elems[i]); c->sub_idx[k++] = (int)i; }
    c->reach_parent = mc->states + 1; free(in);
    m->ncar++; return 0;
}
/* ---- (Carrier C (Of T) (Subset P p)) ----
 * spec 5.3 (l.1774): "(Subset C p) restricts a carrier by an admitted predicate"; grammar
 * carrier-expr (Subset carrier predicate-map).  Enumerated: the elements x of P, in P's
 * order, with p(x) = True.  p is a (Map p (From P|T) (To Bool) (Cases ...)) where T is P's
 * (Of T) type; every element must match exactly one case and give True or False.  The size
 * is bounded by P (Enum/Product <= 4096).  Maps on P are used on C by restriction. */
static const Sx *find_decl(const DcModule *m, const char *head, const char *name) {
    const Sx *src = m->source;
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (sx_head_is(d, head) && d->n > 1 && sx_is_sym(d->items[1], name)) return d;
    }
    return NULL;
}
static int admit_subset(DcModule *m, DcCarrier *c, const char *nm, const Sx *body, char *err, size_t es) {
    int pi = body->n == 3 && name_ok(body->items[1]) ? dc_find_carrier(m, body->items[1]->text) : -1;
    if (pi < 0 && body->n == 3 && name_ok(body->items[1]) && dc_is_skipped(m, body->items[1]->text)) return -2;
    if (pi < 0 || !name_ok(body->items[2])) return fail(err, es, "Carrier %s: expected (Subset Carrier predicate) after the carrier is declared", nm);
    const char *pn = body->items[2]->text;
    const Sx *pd = find_decl(m, "Map", pn), *pc = find_decl(m, "Carrier", m->car[pi].name);
    if (!pd || pd->n != 5) return fail(err, es, "Carrier %s: Subset predicate %s is not a declared map", nm, pn);
    const Sx *fr = pd->items[2], *to = pd->items[3], *cs = pd->items[4];
    const Sx *ptype = pc && pc->n >= 3 && sx_head_is(pc->items[2], "Of") && pc->items[2]->n == 2 ? pc->items[2]->items[1] : NULL;
    if (!sx_head_is(fr, "From") || fr->n != 2 || !(sx_is_sym(fr->items[1], m->car[pi].name) || (ptype && sx_equal(fr->items[1], ptype))))
        return fail(err, es, "Carrier %s: Subset predicate %s does not start at carrier %s or its type", nm, pn, m->car[pi].name);
    if (!sx_head_is(to, "To") || to->n != 2 || !sx_is_sym(to->items[1], "Bool")) return fail(err, es, "Carrier %s: Subset predicate %s must map to Bool", nm, pn);
    if (!sx_head_is(cs, "Cases")) return fail(err, es, "[M0] Carrier %s: Subset predicate %s: only Cases predicates are in the M0 fragment", nm, pn);
    const DcCarrier *P = &m->car[pi]; size_t n = P->n, t = 0;
    int *in = calloc(n ? n : 1, sizeof(int));
    for (size_t i = 0; i < n; i++) {
        int hit = 0;
        for (size_t j = 1; j < cs->n; j++) {
            const Sx *row = cs->items[j]; Env e = {0}; int ok = 1;
            if (row->kind != SX_LIST || row->n != 2) { free(in); return fail(err, es, "Carrier %s: Subset predicate %s: Cases row %zu is not a pair", nm, pn, j - 1); }
            if (!match(row->items[0], P->elems[i], &e)) continue;
            if (hit) { char *x = sx_print(P->elems[i]); fail(err, es, "Carrier %s: Subset predicate %s: input %s matches more than one case", nm, pn, x); free(x); free(in); return -1; }
            hit = 1; logic_on(m); Sx *v = eval_body(row->items[1], &e, &ok); logic_off();
            if (ok == 4) { char *x = sx_print(P->elems[i]); fail(err, es, "Carrier %s: Subset predicate %s on %s: %s", nm, pn, x, logic_why); free(x); sx_free(v); free(in); return -1; }
            if (ok == 2 && logic_why[0]) { sx_free(v); free(in); fail(err, es, "[M0] Carrier %s: Subset predicate %s: %s", nm, pn, logic_why); snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1; }
            if (ok == 2 || ok == 3) { sx_free(v); free(in); return fail(err, es, "[M0] Carrier %s: Subset predicate %s uses an operator outside the M0 fragment", nm, pn); }
            int b = ok == 1 && sx_is_sym(v, "True") ? 1 : ok == 1 && sx_is_sym(v, "False") ? 0 : -1; sx_free(v);
            if (b < 0) { char *x = sx_print(P->elems[i]); fail(err, es, "Carrier %s: Subset predicate %s gives no Bool on %s", nm, pn, x); free(x); free(in); return -1; }
            if (b) { in[i] = 1; t++; }
        }
        if (!hit) { char *x = sx_print(P->elems[i]); fail(err, es, "Carrier %s: Subset predicate %s has no case for %s", nm, pn, x); free(x); free(in); return -1; }
    }
    c->n = t; c->elems = calloc(t ? t : 1, sizeof(Sx *)); c->sub_idx = malloc((t ? t : 1) * sizeof(int));
    size_t k = 0; for (size_t i = 0; i < n; i++) if (in[i]) { c->elems[k] = sx_copy(P->elems[i]); c->sub_idx[k++] = (int)i; }
    c->reach_parent = pi + 1; free(in);
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
    if (sx_head_is(body, "Subset")) return admit_subset(m, c, nm, body, err, es);
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
    if (strlen(nm) >= DC_MAX_NAME || a < 0 || b < 0) {
        /* lowering-unsupported: factors that are declared but not table carriers (e.g. a BitVector carrier) are a fragment limit */
        int frag = strlen(nm) < DC_MAX_NAME && prod->n == 3 && name_ok(prod->items[1]) && name_ok(prod->items[2])
                   && (a >= 0 || name_frag(m, prod->items[1]->text)) && (b >= 0 || name_frag(m, prod->items[2]->text));
        fail(err, es, "%sMap: inline carrier %s must be a binary Product of declared carriers", frag ? "[M0] " : "", nm); free(nm); return -1; }
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

/* ---- (To Bool) maps as Observe ports (t-2026-11-23-mettadinc-m0-bool-observe) ----
 * Bool is a builtin type of the Core library (registry libraries.Core.builtin_types) whose values are the
 * Core constants True and False.  Spec Def 3.1/3.2 (txt l.676-700): each query label j of an interface has a
 * value type Y_j with crisp equality unless declared otherwise, and o_j : X -> Y_j is total.  An
 * (Observe label map) whose map is (Map f (From C) (To Bool) (Cases|Table ...)) is therefore the query
 * o_j = f with Y_j = Bool = {False, True} under literal equality, exactly as an Enum carrier with those two
 * elements would be.  Spec 5.4 (l.1851-1857): every input matches exactly one case and outputs stay in the
 * declared type, so a case giving anything other than True or False, a missing or an overlapping case is
 * InvalidInput.  Only this use is lowered: the carrier is made on demand for a Crisp Observe port, it is
 * never found by name (no Tolerance, Carrier or Product can name it), and a Representation whose Encode map
 * targets Bool stays Unsupported with that reason. */
static int bool_carrier(DcModule *m) {
    for (size_t i = 0; i < m->ncar; i++) if (m->car[i].builtin_bool) return (int)i;
    if (m->ncar >= sizeof m->car / sizeof m->car[0]) return -1;
    DcCarrier *c = &m->car[m->ncar]; memset(c, 0, sizeof *c);
    snprintf(c->name, sizeof c->name, "Bool"); c->builtin_bool = 1;
    c->n = 2; c->elems = calloc(2, sizeof(Sx *)); c->elems[0] = sx_sym("False"); c->elems[1] = sx_sym("True");
    return (int)m->ncar++;
}
static int admit_map(DcModule *m, const Sx *d, char *err, size_t es);
static const Sx *find_decl(const DcModule *m, const char *head, const char *name);
static int is_tmap(const DcModule *m, const char *s);
static int typed_map_on(DcModule *m, const char *nm, int dom, int tgt, char *err, size_t es);
/* The map named by an Observe port was skipped at its declaration because its target (To Bool) named no
 * carrier.  Admit it now, on the implicit Bool carrier.  Returns the map index, -2 when this is not that form
 * (the caller keeps its old behaviour), -1 with err set when admission fails.
 * t-2026-11-24-mettadinc-m0-gap-g (repro g): when the map's From is a type form, e.g. (From (Tuple Symbol Symbol)),
 * admit_map takes the type-form path (admit_typed_map: shape, pattern and fragment checks) and the map is
 * tabulated here on dom, the machine's state carrier, by typed_map_on, as for any type-form map used as an
 * Observe port; its values must be True or False (elements of the implicit Bool carrier), otherwise InvalidInput.
 * The meaning is the one of the two lowerings it combines: o_j = f restricted to the states, Y_j = Bool. */
static int admit_bool_observe_map(DcModule *m, const char *name, int dom, char *err, size_t es) {
    if (strcmp(m->profile, "Crisp") || !dc_is_skipped(m, name) || dc_find_carrier(m, "Bool") >= 0) return -2;
    const Sx *d = find_decl(m, "Map", name);
    if (!d || d->n != 5 || !sx_head_is(d->items[3], "To") || d->items[3]->n != 2 || !sx_is_sym(d->items[3]->items[1], "Bool")) return -2;
    allow_bool = 1; int rc = admit_map(m, d, err, es); allow_bool = 0;
    if (rc) return -1;
    int at = (int)m->nmap - 1;
    if (is_tmap(m, name)) {   /* type-form From: tabulated on the states where it is used */
        bool_carrier(m);
        if ((at = typed_map_on(m, name, dom, -1, err, es)) < 0) { m->ntmap--; return -1; }   /* not admitted: stays skipped */
    }
    for (size_t i = 0; i < m->nskip; i++) if (!strcmp(m->skipped[i], name)) {   /* admitted now: no longer skipped */
        memmove(m->skipped[i], m->skipped[i + 1], (m->nskip - i - 1) * sizeof m->skipped[0]); m->nskip--; break; }
    if (m->unsupported_decls > 0) m->unsupported_decls--;
    return at;
}
const char *dc_skip_why(const DcModule *m, const char *name) {
    for (size_t i = 0; i < m->nskipwhy; i++) if (!strcmp(m->skipwhy[i].name, name)) return m->skipwhy[i].why;
    return "";
}
/* ---- M0: maps declared with a type form in From or To ----
 * Spec 5.1 grammar: a declaration is (head name field* [body]) with heads and fields from the
 * registry, and the registry gives Map's From and To the field type "expr" (a carrier name or a
 * type expression), so (Map f (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol)) (Cases ...))
 * is well formed.  Spec 5.2: every carrier states its element type, (Carrier C (Of T) ...).
 * Spec 5.3 (admission obligations): on an enumerated carrier, admission checks coverage of the
 * cases, absence of overlaps and that outputs stay in the carrier, by enumeration.
 * Lowering (Crisp profile only):
 *  - a map whose From is a type T is a function on values of T; it is tabulated on the carrier
 *    where it is used (a machine's states for Observe/Action/Encode, the Source machine's states
 *    for an AbstractionMap), which must declare (Of T); coverage and overlaps are checked there;
 *  - a map whose From is a carrier P is tabulated on P at declaration, and on a Subset or Reach
 *    carrier of P where used, as for any map on P;
 *  - a To type U: every value must have type U.  Where the value must be a state (Action,
 *    AbstractionMap) the state carrier must declare (Of U) and the value must be one of its
 *    elements, otherwise InvalidInput (the update leaves the carrier).  Elsewhere (Observe,
 *    Encode) the values are collected in an image carrier named by the printed type U, shared by
 *    all maps into U; values are compared by equality, as in Ben's reference evaluator.
 * Supported type forms: (Tuple T ...) with T among Symbol, Bool, Nat, Int or a nested Tuple.
 * Other type forms are Unsupported, naming the form; a malformed one is InvalidInput. */
static int is_tmap(const DcModule *m, const char *s) { for (size_t i = 0; i < m->ntmap; i++) if (!strcmp(m->tmap[i], s)) return 1; return 0; }
/* 1: a type form inside the M0 fragment; 0: malformed; -1: a type outside the M0 fragment */
static int type_form_ok(const Sx *t) {
    if (t->kind == SX_SYM)
        return !strcmp(t->text, "Symbol") || !strcmp(t->text, "Bool") || !strcmp(t->text, "Nat") || !strcmp(t->text, "Int") ? 1 : -1;
    if (t->kind != SX_LIST || t->n == 0 || t->items[0]->kind != SX_SYM || t->items[0]->text[0] == '$') return 0;
    if (!sx_head_is(t, "Tuple")) return -1;
    if (t->n < 2) return 0;
    int r = 1;
    for (size_t i = 1; i < t->n; i++) { int k = type_form_ok(t->items[i]); if (k == 0) return 0; if (k < 0) r = -1; }
    return r;
}
static int int_lit(const Sx *v, int nat) {
    if (!v || v->kind != SX_SYM) return 0;
    const char *p = v->text; if (*p == '-') { if (nat) return 0; p++; }
    if (!*p) return 0;
    for (; *p; p++) if (*p < '0' || *p > '9') return 0;
    return 1;
}
/* v has (a supported) type t */
static int has_type(const Sx *v, const Sx *t) {
    if (t->kind == SX_SYM) {
        if (!strcmp(t->text, "Bool")) return sx_is_sym(v, "True") || sx_is_sym(v, "False");
        if (!strcmp(t->text, "Nat")) return int_lit(v, 1);
        if (!strcmp(t->text, "Int")) return int_lit(v, 0);
        if (!strcmp(t->text, "Symbol")) return v->kind == SX_SYM && v->text[0] != '$' && strcmp(v->text, "?");
        return 0;
    }
    if (!sx_head_is(v, "Tuple") || v->n != t->n) return 0;
    for (size_t i = 1; i < t->n; i++) if (!has_type(v->items[i], t->items[i])) return 0;
    return 1;
}
/* a Cases pattern can match some value of type t */
static int pattern_fits(const Sx *pat, const Sx *t) {
    if (pat->kind == SX_SYM && pat->text[0] == '$') return 1;
    if (pat->kind != SX_LIST) return has_type(pat, t);
    if (t->kind != SX_LIST || !sx_head_is(pat, "Tuple") || pat->n != t->n) return 0;
    for (size_t i = 1; i < t->n; i++) if (!pattern_fits(pat->items[i], t->items[i])) return 0;
    return 1;
}
/* operators of a Cases body that eval_body evaluates (anything else is outside the M0 fragment) */
static int frag_ok(const DcModule *m, const Sx *b, int logic) {   /* logic: admit If/Eq/And/Or/Not (Cases bodies); 0 for Body maps, which main lowers with Tuple/Add/Mul only */
    if (b->kind != SX_LIST) return 1;
    if (b->n && b->items[0]->kind == SX_SYM) {
        const char *h = b->items[0]->text;
        /* If/Eq/And/Or/Not at any arity: a malformed arity is InvalidInput, a short And/Or Unsupported, when tabulated (eval_logic) */
        if (!(!strcmp(h, "Tuple") || ((!strcmp(h, "Add") || !strcmp(h, "Mul")) && b->n == 3) || (m->neural && !strcmp(h, "Xor") && b->n == 3)
              || (m->natarith && nat_head(b) && b->n == 3) || (m->natarith && !strcmp(h, "If") && b->n == 4)
              || (logic && !strcmp(m->profile, "Crisp") && logic_head(b)))) return 0;
        for (size_t i = 1; i < b->n; i++) if (!frag_ok(m, b->items[i], logic)) return 0;
        return 1;
    }
    for (size_t i = 0; i < b->n; i++) if (!frag_ok(m, b->items[i], logic)) return 0;
    return 1;
}
static int body_in_fragment(const DcModule *m, const Sx *b) { return frag_ok(m, b, 1); }
/* ---- M0: (Body ($v) e) maps in a Crisp module (t-2026-11-24-mettadinc-m0-body-maps) ----
 * Spec 5.1 grammar (txt l.1721): map-body ::= (Cases (pattern expr)+) | (Body ($v) expr) | (Table ...) | ...
 * Spec 5.4 (l.1856): "Body binds its single argument lexically": the map sends x to the value of expr
 * with $v bound to x, and to nothing else.  That is the one-case map (Cases ($v expr)), whose variable
 * pattern every input matches exactly once; Ben's reference evaluator reads it the same way
 * (docs/e0 .../04_omega_memory_goals_part1/validation_bundle/mg_eval.py, World.call: ev(expr, {$v: arg})).
 * Lowering (Crisp profile only): expr is evaluated by eval_body, the evaluator of Cases bodies, with $v
 * bound to each element of the carrier the map is tabulated on (its From carrier; for a type-form map the
 * carrier where it is used, as for Cases), and the map becomes a table.  Spec 5.3 admission obligations
 * (l.1784-1786), by enumeration: totality (an element on which expr has no value, e.g. Add on a symbol, is
 * InvalidInput) and outputs stay in To (InvalidInput).  Spec 5.4: a variable other than $v is unbound
 * (InvalidInput, binding failure, s2.8); a malformed (Body ...) is InvalidInput.  An operator outside the
 * Cases-body fragment (body_in_fragment) is Unsupported, the reason naming the operator. */
static const char *body_var(const Sx *body) {   /* $v of a well-formed (Body ($v) expr), else NULL */
    if (!sx_head_is(body, "Body") || body->n != 3) return NULL;
    const Sx *b = body->items[1];
    if (b->kind != SX_LIST || b->n != 1 || b->items[0]->kind != SX_SYM || b->items[0]->text[0] != '$' || !b->items[0]->text[1]) return NULL;
    return b->items[0]->text;
}
static const char *body_free_var(const Sx *x, const char *var) {   /* a $-variable of x other than var */
    if (x->kind == SX_SYM) return x->text[0] == '$' && strcmp(x->text, var) ? x->text : NULL;
    if (x->kind != SX_LIST) return NULL;
    for (size_t i = 0; i < x->n; i++) { const char *r = body_free_var(x->items[i], var); if (r) return r; }
    return NULL;
}
/* the outermost operator of b that body_in_fragment rejects (tested with its arguments replaced by in-fragment atoms) */
static const char *body_foreign(const DcModule *m, const Sx *b) {
    if (b->kind != SX_LIST || frag_ok(m, b, 0)) return NULL;
    if (b->n && b->items[0]->kind == SX_SYM) {
        Sx *s = sx_list(); sx_push(s, sx_copy(b->items[0]));
        for (size_t i = 1; i < b->n; i++) sx_push(s, sx_sym("0"));
        int head_ok = frag_ok(m, s, 0); sx_free(s);
        if (!head_ok) return b->items[0]->text;
    }
    for (size_t i = 0; i < b->n; i++) { const char *r = body_foreign(m, b->items[i]); if (r) return r; }
    return "a form";
}
/* shape, binding and fragment checks of a Body map: 0 fine; -1 with err set ("[M0]" and pending_why when Unsupported) */
static int body_check(const DcModule *m, const char *nm, const Sx *body, char *err, size_t es) {
    const char *var = body_var(body);
    if (!var) return fail(err, es, "Map %s: a Body must be (Body ($v) expr), one variable binding the argument", nm);
    const char *fv = body_free_var(body->items[2], var);
    if (fv) return fail(err, es, "Map %s: Body uses %s, which it does not bind (it binds %s)", nm, fv, var);
    const char *op = body_foreign(m, body->items[2]);
    if (op) {
        fail(err, es, "[M0] Map %s: Body uses %s, an operator outside the M0 fragment, which admits Tuple, Add and Mul in map bodies", nm, op);
        snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1;
    }
    return 0;
}
/* the declared element type of carrier c: (Of T) of its declaration, or an image carrier's type */
static const Sx *carrier_type(const DcModule *m, int c) {
    if (m->car[c].type) return m->car[c].type;
    const Sx *d = find_decl(m, "Carrier", m->car[c].name);
    return d && d->n >= 3 && sx_head_is(d->items[2], "Of") && d->items[2]->n == 2 ? d->items[2]->items[1] : NULL;
}
static int image_carrier(DcModule *m, const Sx *t, char *err, size_t es) {
    char *nm = sx_print(t);
    if (!nm) return fail(err, es, "Map: out of memory");
    for (size_t i = 0; i < m->ncar; i++) if (m->car[i].image && !strcmp(m->car[i].name, nm)) { free(nm); return (int)i; }
    if (strlen(nm) >= DC_MAX_NAME || m->ncar >= sizeof m->car / sizeof m->car[0]) {
        fail(err, es, "[M0] Map: To type %s needs a value carrier the table engine cannot hold", nm); snprintf(pending_why, sizeof pending_why, "%s", err + 5); free(nm); return -1;
    }
    DcCarrier *c = &m->car[m->ncar]; memset(c, 0, sizeof *c);
    snprintf(c->name, sizeof c->name, "%s", nm); free(nm);
    c->image = 1; c->type = sx_copy(t);
    return (int)m->ncar++;
}
static int image_add(DcCarrier *c, const Sx *v) {
    int at = dc_carrier_index(c, v);
    if (at >= 0) return at;
    if (c->n >= 4096) return -1;
    Sx **e = realloc(c->elems, (c->n + 1) * sizeof *e); if (!e) return -1;
    c->elems = e; c->elems[c->n] = sx_copy(v); return (int)c->n++;
}
/* Tabulates the type-form map nm on carrier dom.  tgt >= 0: every value must be an element of
 * carrier tgt (an Action or an AbstractionMap); tgt < 0: values go to the declared To carrier or
 * to the image carrier of the To type.  An identical earlier instance is reused.
 * Returns the map index, or -1 with err set. */
static int typed_map_on(DcModule *m, const char *nm, int dom, int tgt, char *err, size_t es) {
    const Sx *d = find_decl(m, "Map", nm);
    if (!d || d->n != 5) return fail(err, es, "Map %s: declaration not found", nm);
    const Sx *fr = d->items[2]->items[1], *to = d->items[3]->items[1], *body = d->items[4];
    const DcCarrier *D = &m->car[dom];
    if (fr->kind == SX_SYM) {
        int p = dc_find_carrier(m, fr->text);
        if (!(dom == p || (D->reach_parent && D->reach_parent - 1 == p)))
            return fail(err, es, "Map %s: From carrier %s does not contain carrier %s, where the map is used", nm, fr->text, D->name);
    } else {
        const Sx *dt = carrier_type(m, dom);
        if (!dt || !sx_equal(dt, fr)) {
            char *a = sx_print(fr), *b = dt ? sx_print(dt) : NULL;
            fail(err, es, "Map %s: From type %s is not the element type of carrier %s, where the map is used, which is %s", nm, a, D->name, b ? b : "undeclared");
            free(a); free(b); return -1;
        }
    }
    const Sx *totype = to->kind == SX_LIST ? to : NULL; int tc;
    if (tgt >= 0) {
        if (totype) {
            const Sx *tt = carrier_type(m, tgt);
            if (!tt || !sx_equal(tt, totype)) {
                char *a = sx_print(totype), *b = tt ? sx_print(tt) : NULL;
                fail(err, es, "Map %s: To type %s is not the element type of carrier %s, where its values must lie, which is %s", nm, a, m->car[tgt].name, b ? b : "undeclared");
                free(a); free(b); return -1;
            }
        } else {
            int q = dc_find_carrier(m, to->text);
            if (!(q == tgt || (m->car[tgt].reach_parent && m->car[tgt].reach_parent - 1 == q)))
                return fail(err, es, "Map %s: To carrier %s does not contain carrier %s, where its values must lie", nm, to->text, m->car[tgt].name);
        }
        tc = tgt;
    } else if (totype) { if ((tc = image_carrier(m, totype, err, es)) < 0) return -1; }
    else tc = dc_find_carrier(m, to->text);
    /* (To Bool) with no declared Bool carrier: only admit_bool_observe_map admits such a type-form map (allow_bool) */
    if (tc < 0 && sx_is_sym(to, "Bool")) tc = bool_carrier(m);
    if (tc < 0) return fail(err, es, "Map %s: field To names no declared carrier", nm);
    for (size_t i = 0; i < m->nmap; i++) if (!strcmp(m->map[i].name, nm) && m->map[i].from == dom && m->map[i].to == tc) return (int)i;
    if (m->nmap >= sizeof m->map / sizeof m->map[0]) return fail(err, es, "Map %s: too many maps", nm);
    DcCarrier *T = &m->car[tc];
    int *tab = malloc((D->n ? D->n : 1) * sizeof(int)), cases = sx_head_is(body, "Cases");
    int *hitb = malloc((D->n ? D->n : 1) * sizeof(int));   /* shared map rules (maprules.h): mr = values, ov = inputs already matched by a row */
    DcMrTab mr, ov; dc_mr_init(&mr, (int)D->n, tab); dc_mr_init(&ov, (int)D->n, hitb);
    const char *bvar = body_var(body);   /* a Body map (shape checked by admit_typed_map): one case, $v bound to the input */
    char lab[32];   /* where a value comes from, for the reasons: "row N" or "Body" */
    for (size_t i = 0; i < D->n; i++) {
        size_t hit = 0; const Sx *out = NULL; Env e = {0};
        if (bvar) { hit = 1; out = body->items[2]; e.var[0] = bvar; e.val[0] = D->elems[i]; e.n = 1; dc_mr_mark(&ov, (int)i); }
        for (size_t j = 1; !bvar && j < body->n; j++) {
            const Sx *row = body->items[j]; Env e1 = {0};
            if (!(cases ? match(row->items[0], D->elems[i], &e1) : sx_equal(row->items[0], D->elems[i]))) continue;
            if (dc_mr_mark(&ov, (int)i) == DC_MR_DUP) {
                char *xs = sx_print(D->elems[i]);
                fail(err, es, cases ? "Map %s: input %s matches Cases rows %zu and %zu; overlapping cases are rejected" : "Map %s: input %s has Table rows %zu and %zu", nm, xs, hit - 1, j - 1);
                free(xs); free(tab); free(hitb); return -1;
            }
            hit = j; out = row->items[1]; e = e1;
        }
        if (dc_mr_missing(&ov, (int)i)) { char *xs = sx_print(D->elems[i]); fail(err, es, "Map %s: not total on carrier %s; no value for %s", nm, D->name, xs); free(xs); free(tab); free(hitb); return -1; }
        if (bvar) snprintf(lab, sizeof lab, "Body"); else snprintf(lab, sizeof lab, "row %zu", hit - 1);
        int ok = 1; allow_xor = m->neural; allow_nat = m->natarith; logic_on(m); Sx *v = cases || bvar ? eval_body(out, &e, &ok) : sx_copy(out); allow_xor = 0; allow_nat = 0; logic_off();
        if (ok == 4) { char *xs = sx_print(D->elems[i]); fail(err, es, "Map %s: %s%s on %s: %s", nm, bvar ? "" : "Cases ", lab, xs, logic_why); free(xs); sx_free(v); free(tab); free(hitb); return -1; }
        if (ok == 2 && logic_why[0]) { sx_free(v); free(tab); free(hitb); fail(err, es, "[M0] Map %s: %s%s: %s", nm, bvar ? "" : "Cases ", lab, logic_why); snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1; }
        if (ok == 2) { sx_free(v); free(tab); free(hitb); fail(err, es, "[M0] Map %s: %s%s uses an operator outside the M0 fragment", nm, bvar ? "" : "Cases ", lab); snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1; }
        if (ok == 3) { sx_free(v); free(tab); free(hitb); return fail(err, es, "Map %s: %s%s: integer overflow or out-of-range literal in Add/Mul", nm, bvar ? "" : "Cases ", lab); }
        if (ok != 1 || (totype && dc_mr_value(has_type(v, totype) ? 0 : -1) == DC_MR_CODOMAIN)) {   /* R3 To type (maprules.h) */
            char *xs = sx_print(D->elems[i]), *vs = sx_print(v), *ts = totype ? sx_print(totype) : NULL;
            if (ok != 1 && bvar) fail(err, es, "Map %s: Body has no value on %s, so the map is not total on carrier %s", nm, xs, D->name);
            else if (ok != 1) fail(err, es, "Map %s: %s gives no value on %s", nm, lab, xs);
            else fail(err, es, "Map %s: %s gives %s on %s, which is not of the To type %s", nm, lab, vs, xs, ts);
            free(xs); free(vs); free(ts); sx_free(v); free(tab); free(hitb); return -1;
        }
        int b = T->image ? image_add(T, v) : dc_carrier_index(T, v);
        if (dc_mr_value(b) == DC_MR_CODOMAIN) {
            char *xs = sx_print(D->elems[i]), *vs = sx_print(v);
            if (T->image) { fail(err, es, "[M0] Map %s: more than 4096 values of type %s", nm, T->name); snprintf(pending_why, sizeof pending_why, "%s", err + 5); }
            else fail(err, es, "Map %s: sends %s to %s, which leaves carrier %s", nm, xs, vs, T->name);
            free(xs); free(vs); sx_free(v); free(tab); free(hitb); return -1;
        }
        sx_free(v); (void)dc_mr_put(&mr, (int)i, b);
    }
    DcMap *mp = &m->map[m->nmap]; memset(mp, 0, sizeof *mp);
    snprintf(mp->name, sizeof mp->name, "%s", nm); mp->from = dom; mp->to = tc; mp->table = tab; free(hitb);
    return (int)m->nmap++;
}
/* Admission of a Crisp map with a type form in From or To (the other side a declared carrier
 * or a type form): shape checks here, tabulation where it is used (typed_map_on). */
static int admit_typed_map(DcModule *m, const Sx *d, const char *nm, char *err, size_t es) {
    const Sx *fr = d->items[2]->items[1], *to = d->items[3]->items[1], *body = d->items[4];
    const Sx *side[2] = { fr, to }; const char *fld[2] = { "From", "To" };
    for (int k = 0; k < 2; k++) {
        if (side[k]->kind != SX_LIST) continue;
        int t = type_form_ok(side[k]); char *s = sx_print(side[k]);
        if (t == 0) fail(err, es, "Map %s: field %s: %s is not a well-formed type", nm, fld[k], s);
        else if (t < 0) { fail(err, es, "[M0] Map %s: field %s: type %s is outside the M0 fragment, which admits Tuple types over Symbol, Bool, Nat and Int", nm, fld[k], s); snprintf(pending_why, sizeof pending_why, "%s", err + 5); }
        free(s);
        if (t <= 0) return -1;
    }
    int cases = sx_head_is(body, "Cases");
    if (sx_head_is(body, "Body")) {   /* t-2026-11-24-mettadinc-m0-body-maps: checks here, tabulation in typed_map_on */
        if (body_check(m, nm, body, err, es)) return -1;
    } else if (!cases && !sx_head_is(body, "Table")) {
        fail(err, es, "[M0] Map %s: a %s body on a type-form map is outside the M0 fragment, which admits Table, Cases and Body", nm, body->kind == SX_LIST && body->n && body->items[0]->kind == SX_SYM ? body->items[0]->text : "non-form");
        snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1;
    }
    for (size_t j = 1; !sx_head_is(body, "Body") && j < body->n; j++) {
        const Sx *row = body->items[j];
        if (row->kind != SX_LIST || row->n != 2) return fail(err, es, "Map %s: %s row %zu is not a pair", nm, cases ? "Cases" : "Table", j - 1);
        if (cases && !body_in_fragment(m, row->items[1])) {
            fail(err, es, "[M0] Map %s: Cases row %zu uses an operator outside the M0 fragment", nm, j - 1);
            snprintf(pending_why, sizeof pending_why, "Map %s: Cases row %zu of a type-form map uses an operator outside the M0 fragment, which admits Tuple, Add, Mul, If, Eq, And, Or and Not", nm, j - 1); return -1;
        }
        if (fr->kind == SX_LIST && !(cases ? pattern_fits(row->items[0], fr) : has_type(row->items[0], fr))) {
            char *ps = sx_print(row->items[0]), *ts = sx_print(fr);
            fail(err, es, "Map %s: %s row %zu: %s cannot be a value of the From type %s", nm, cases ? "Cases" : "Table", j - 1, ps, ts);
            free(ps); free(ts); return -1;
        }
        if (!cases && to->kind == SX_LIST && dc_mr_value(has_type(row->items[1], to) ? 0 : -1) == DC_MR_CODOMAIN) {   /* R3 To type (maprules.h) */
            char *vs = sx_print(row->items[1]), *ts = sx_print(to);
            fail(err, es, "Map %s: Table row %zu: %s is not of the To type %s", nm, j - 1, vs, ts);
            free(vs); free(ts); return -1;
        }
    }
    if (m->ntmap >= sizeof m->tmap / sizeof m->tmap[0]) return fail(err, es, "Map %s: too many maps", nm);
    if (fr->kind == SX_SYM && typed_map_on(m, nm, dc_find_carrier(m, fr->text), -1, err, es) < 0) return -1;
    snprintf(m->tmap[m->ntmap++], DC_MAX_NAME, "%s", nm);
    return 0;
}

static int admit_map(DcModule *m, const Sx *d, char *err, size_t es) {
    if (d->n != 5 || !name_ok(d->items[1])) return fail(err, es, "[M0] Map: expected (Map name (From C) (To C) (Table|Cases ...))");
    const char *nm = d->items[1]->text;
    if (dc_find_map(m, nm) >= 0 || is_tmap(m, nm)) return fail(err, es, "Map %s: duplicate name", nm);
    if (m->nmap >= 64) return fail(err, es, "Map %s: too many maps", nm);
    const Sx *fr = d->items[2], *to = d->items[3], *body = d->items[4];
    /* M0: a type form in From or To, the other side a type form or a declared carrier (Crisp) */
    if (!strcmp(m->profile, "Crisp") && sx_head_is(fr, "From") && fr->n == 2 && sx_head_is(to, "To") && to->n == 2
        && (fr->items[1]->kind == SX_LIST || to->items[1]->kind == SX_LIST)
        && (fr->items[1]->kind == SX_LIST || (name_ok(fr->items[1]) && dc_find_carrier(m, fr->items[1]->text) >= 0))
        && (to->items[1]->kind == SX_LIST || (name_ok(to->items[1]) && dc_find_carrier(m, to->items[1]->text) >= 0)
            || (allow_bool && fr->items[1]->kind == SX_LIST && sx_is_sym(to->items[1], "Bool"))))   /* gap g: a (To Bool) Observe map with a type-form From */
        return admit_typed_map(m, d, nm, err, es);
    int fprod = -1;
    if (sx_head_is(fr, "From") && fr->n == 2 && sx_head_is(fr->items[1], "Product") && !strcmp(m->profile, "Graded")) {
        fprod = product_carrier(m, fr->items[1], err, es); if (fprod < 0) return -1; }
    if (fprod < 0 && (!sx_head_is(fr, "From") || fr->n != 2 || !name_ok(fr->items[1]))) return fail(err, es, "[M0] Map %s: field From", nm);
    if (!sx_head_is(to, "To") || to->n != 2 || !name_ok(to->items[1])) return fail(err, es, "[M0] Map %s: field To", nm);
    int f = fprod >= 0 ? fprod : dc_find_carrier(m, fr->items[1]->text), t = dc_find_carrier(m, to->items[1]->text);
    if (t < 0 && !strcmp(m->profile, "Graded")) t = dc_value_carrier(m, to->items[1]->text);
    if (t < 0 && allow_bool && !strcmp(to->items[1]->text, "Bool")) t = bool_carrier(m);
    if (f < 0) return fail(err, es, "Map %s: field From names no declared carrier (%s)", nm, fr->items[1]->text);
    if (t < 0) return fail(err, es, "Map %s: field To names no declared carrier (%s)", nm, to->items[1]->text);
    DcCarrier *F = &m->car[f], *T = &m->car[t];
    DcMap *mp = &m->map[m->nmap]; memset(mp, 0, sizeof *mp);
    snprintf(mp->name, sizeof mp->name, "%s", nm); mp->from = f; mp->to = t;
    mp->table = malloc((F->n ? F->n : 1) * sizeof(int));
    DcMrTab mr; dc_mr_init(&mr, (int)F->n, mp->table);   /* shared map rules (maprules.h) */
    if (sx_head_is(body, "Table")) {
        for (size_t j = 1; j < body->n; j++) {
            const Sx *row = body->items[j];
            if (row->kind != SX_LIST || row->n != 2) { free(mp->table); return fail(err, es, "Map %s: Table row %zu is not a pair", nm, j - 1); }
            int a = dc_carrier_index(F, row->items[0]), b = T->value ? dc_value_add(T, row->items[1]) : dc_carrier_index(T, row->items[1]);
            int rc = dc_mr_put(&mr, a, b);
            if (rc == DC_MR_KEY) { free(mp->table); return fail(err, es, "Map %s: Table row %zu key outside carrier %s", nm, j - 1, F->name); }
            if (rc == DC_MR_CODOMAIN) { free(mp->table); return fail(err, es, "Map %s: Table row %zu value outside carrier %s", nm, j - 1, T->name); }
            if (rc == DC_MR_DUP) { free(mp->table); return fail(err, es, "Map %s: Table key at row %zu repeated", nm, j - 1); }
        }
    } else if (sx_head_is(body, "Cases")) {
        for (size_t i = 0; i < F->n; i++) {
            for (size_t j = 1; j < body->n; j++) {
                const Sx *row = body->items[j]; Env e = {0}; int ok = 1;
                if (row->kind != SX_LIST || row->n != 2) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu is not a pair", nm, j - 1); }
                if (!match(row->items[0], F->elems[i], &e)) continue;
                allow_rat = T->value; allow_xor = m->neural; allow_nat = m->natarith; logic_on(m); Sx *v = eval_body(row->items[1], &e, &ok); allow_rat = 0; allow_xor = 0; allow_nat = 0; logic_off();
                if (ok == 4) { char *xs = sx_print(F->elems[i]); fail(err, es, "Map %s: Cases row %zu on %s: %s", nm, j - 1, xs, logic_why); free(xs); sx_free(v); free(mp->table); return -1; }
                if (ok == 2 && logic_why[0]) { sx_free(v); free(mp->table); fail(err, es, "[M0] Map %s: Cases row %zu: %s", nm, j - 1, logic_why); snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1; }
                if (ok == 2) { sx_free(v); free(mp->table); return fail(err, es, "[M0] Map %s: Cases row %zu uses an operator outside the M0 fragment", nm, j - 1); }
                if (ok == 3) { sx_free(v); free(mp->table); return fail(err, es, "Map %s: Cases row %zu: integer overflow or out-of-range literal in Add/Mul", nm, j - 1); }
                int b = ok ? (T->value ? dc_value_add(T, v) : dc_carrier_index(T, v)) : -1; sx_free(v);
                if (dc_mr_put(&mr, (int)i, b) == DC_MR_CODOMAIN) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu gives a value outside carrier %s", nm, j - 1, T->name); }
                /* spec 5.4: every input matches exactly one case; overlapping cases are
                 * rejected even when they agree (source order never decides a value) */
                for (size_t j2 = j + 1; j2 < body->n; j2++) {
                    const Sx *r2 = body->items[j2]; Env e2 = {0};
                    if (r2->kind != SX_LIST || r2->n != 2) { free(mp->table); return fail(err, es, "Map %s: Cases row %zu is not a pair", nm, j2 - 1); }
                    if (match(r2->items[0], F->elems[i], &e2) && dc_mr_mark(&mr, (int)i) == DC_MR_DUP) {   /* a second row for input i */
                        char *xs = sx_print(F->elems[i]);
                        fail(err, es, "Map %s: input %s matches Cases rows %zu and %zu; overlapping cases are rejected", nm, xs, j - 1, j2 - 1);
                        free(xs); free(mp->table); return -1;
                    }
                }
                break;
            }
        }
    } else if (sx_head_is(body, "Body") && !strcmp(m->profile, "Crisp")) {   /* t-2026-11-24-mettadinc-m0-body-maps */
        if (body_check(m, nm, body, err, es)) { free(mp->table); return -1; }
        Env e = {0}; e.var[0] = body_var(body); e.n = 1;
        for (size_t i = 0; i < F->n; i++) {
            int ok = 1; e.val[0] = F->elems[i];
            allow_xor = m->neural; allow_nat = m->natarith; Sx *v = eval_body(body->items[2], &e, &ok); allow_xor = 0; allow_nat = 0;
            char *xs = sx_print(F->elems[i]);
            if (ok == 2) { fail(err, es, "[M0] Map %s: Body uses an operator outside the M0 fragment on %s", nm, xs); snprintf(pending_why, sizeof pending_why, "%s", err + 5); }
            else if (ok == 3) fail(err, es, "Map %s: Body on %s: integer overflow or out-of-range literal in Add/Mul", nm, xs);
            else if (ok != 1) fail(err, es, "Map %s: Body has no value on %s, so the map is not total on carrier %s", nm, xs, F->name);
            int b = ok == 1 ? dc_carrier_index(T, v) : -1;
            if (ok == 1 && b < 0) { char *vs = sx_print(v); fail(err, es, "Map %s: Body sends %s to %s, which is not in carrier %s", nm, xs, vs, T->name); free(vs); }
            free(xs); sx_free(v);
            if (b < 0) { free(mp->table); return -1; }
            (void)dc_mr_put(&mr, (int)i, b);
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
            sx_free(v); (void)dc_mr_put(&mr, (int)i, b);
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
            sx_free(v); (void)dc_mr_put(&mr, (int)i, b);
        }
    } else { free(mp->table); return fail(err, es, "[M0] Map %s: only Table and Cases maps are in the M0 deterministic fragment", nm); }
    int miss = -1;
    if (dc_mr_total(&mr, &miss)) {
        char *s = sx_print(F->elems[miss]); fail(err, es, "Map %s: not total; no value for %s", nm, s); free(s); free(mp->table); return -1;
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
    int mp;
    if (is_tmap(m, d->items[2]->text)) {   /* M0 type-form map: tabulated on the states; an Action's values must be states */
        if ((mp = typed_map_on(m, d->items[2]->text, mc->states, is_obs ? -1 : mc->states, err, es)) < 0) return -1;
    } else {
        mp = dc_find_map(m, d->items[2]->text);
        if (mp < 0 && is_obs && ptol < 0) {
            mp = admit_bool_observe_map(m, d->items[2]->text, mc->states, err, es);
            if (mp == -1) {   /* still outside the fragment: keep the reason, naming the form, for the requests */
                if (strstr(err, "[M0]")) snprintf(pending_why, sizeof pending_why, "Observe %s: %s", d->items[1]->text, strstr(err, "[M0] ") ? strstr(err, "[M0] ") + 5 : err);
                return -1;
            }
            const Sx *bd = mp == -2 && strcmp(m->profile, "Crisp") ? find_decl(m, "Map", d->items[2]->text) : NULL;
            if (bd && bd->n == 5 && sx_head_is(bd->items[3], "To") && bd->items[3]->n == 2 && sx_is_sym(bd->items[3]->items[1], "Bool"))
                snprintf(pending_why, sizeof pending_why, "Observe %s: map %s targets Bool; a (To Bool) Observe map is lowered only in a Crisp module", d->items[1]->text, d->items[2]->text);
        }
        if (mp < 0) return fail(err, es, "Machine %s: field %s names no declared map (%s)", mc->name, field, d->items[2]->text);
        if ((mp = restrict_map(m, mp, mc->states, !is_obs, err, es)) < 0) return -1;
    }
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

/* ---- (Machine M (States S) (Like N)) (t-2026-11-23-mettadinc-m0-like-machines) ----
 * Like is a keyed field of Machine in the registry, which spec 5.1 (txt l.1659-1662) makes the normative
 * definition of every declaration field; the field comes from the ex2 bundle patch adopted in
 * registry/mettadinc_registry.json, doc "the observe and action entries of another machine; States may
 * differ (a scope)" (doc04 Table 14, l.3805: TaskResume uses Like only).  The reference evaluator
 * (docs/e0/docs/04_omega_memory_goals_part1/validation_bundle/mg_eval.py, entry_exprs l.350-357) takes N's
 * Observe and Action entries for M.  Lowering: M gets exactly N's (Observe label map) and (Action label map)
 * entries, in N's declaration order, admitted on M's own States as if written there.  When S is a Subset or
 * Reach scope of N's state carrier the maps are used on S by restriction (spec 5.3 "Reachability scopes",
 * l.1810-1818, and Table 7 "Restrict to a forward-closed subset"); an action that leaves S is InvalidInput
 * (5.3 admission obligations: outputs stay in the carrier), as for the written-out machine.
 * Malformed (InvalidInput): a Like field that is not (Like Name), a repeated Like field (5.1 l.1752-1753:
 * duplicate keyed fields; admit.c refuses it first), N undeclared, N = M, a copied entry that fails on S.  Outside this lowering (Unsupported, the reason names
 * Like): a non-Crisp module, N outside the fragment, N declared after M, Like together with M's own
 * Observe/Action/Merge or other fields, N with Merge entries. */
static int admit_ports(DcModule *m, DcMachine *mc, const Sx *d, int is_obs, char *err, size_t es);
static int admit_like(DcModule *m, DcMachine *mc, const Sx *d, char *err, size_t es) {
    const char *nm = mc->name; const Sx *lk = NULL; size_t nlk = 0;
    for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], "Like")) { lk = d->items[i]; nlk++; }
    if (nlk > 1) return fail(err, es, "Machine %s: field Like repeated", nm);
    if (lk->n != 2 || !name_ok(lk->items[1])) return fail(err, es, "Machine %s: field Like expects (Like Machine)", nm);
    const char *tn = lk->items[1]->text;
    if (!strcmp(tn, nm)) return fail(err, es, "Machine %s: field Like names the machine itself", nm);
    int ti = dc_find_machine(m, tn);
    if (ti < 0 && !dc_is_skipped(m, tn) && !find_decl(m, "Machine", tn))
        return fail(err, es, "Machine %s: field Like names no declared machine (%s)", nm, tn);
#define LIKE_OUT(...) do { snprintf(pending_why, sizeof pending_why, __VA_ARGS__); return -2; } while (0)
    if (strcmp(m->profile, "Crisp")) LIKE_OUT("field Like is lowered only in a Crisp module");
    for (size_t i = 2; i < d->n; i++) {
        const Sx *f = d->items[i];
        if (sx_head_is(f, "States") || sx_head_is(f, "Like")) continue;
        LIKE_OUT("field Like together with the machine's own %s field is outside the M0 lowering",
                 f->kind == SX_LIST && f->n && f->items[0]->kind == SX_SYM ? f->items[0]->text : "?");
    }
    if (ti < 0 && dc_is_skipped(m, tn)) LIKE_OUT("field Like names machine %s, which is outside the M0 fragment", tn);
    if (ti < 0) LIKE_OUT("field Like names machine %s, declared after it; the M0 lowering reads Like in declaration order", tn);
    /* N was admitted, so its declaration is in the source; a Like on N leads to the declaration with the entries */
    const Sx *td = find_decl(m, "Machine", tn);
    for (int hop = 0; td; hop++) {
        const Sx *l2 = NULL;
        for (size_t i = 2; i < td->n; i++) if (sx_head_is(td->items[i], "Like")) l2 = td->items[i];
        if (!l2) break;
        if (hop > 16 || l2->n != 2 || !name_ok(l2->items[1])) { td = NULL; break; }
        td = find_decl(m, "Machine", l2->items[1]->text);
    }
    if (!td) return fail(err, es, "Machine %s: field Like: the entries of %s cannot be resolved", nm, tn);
    for (size_t i = 2; i < td->n; i++)
        if (sx_head_is(td->items[i], "Merge")) LIKE_OUT("field Like of machine %s, which has Merge entries, is outside the M0 lowering", tn);
#undef LIKE_OUT
    for (size_t i = 2; i < td->n; i++) {
        const Sx *f = td->items[i]; int prc = 0;
        if (sx_head_is(f, "Observe")) prc = admit_ports(m, mc, f, 1, err, es);
        else if (sx_head_is(f, "Action")) prc = admit_ports(m, mc, f, 0, err, es);
        if (prc == -1 && !strstr(err, "[M0]")) {   /* say where the failing entry came from */
            size_t k = strlen(err);
            if (k < es) snprintf(err + k, es - k, "; the entry is taken from machine %s by field Like", tn);
        }
        if (prc) return prc;
    }
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
    for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], "Like")) {
        int lrc = admit_like(m, mc, d, err, es); if (lrc) return lrc;
        m->nmach++; return 0;
    }
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
        && declared_in_source(m, "Machine", of->items[1]->text)) {   /* machine outside M0 */
        const char *why = dc_skip_why(m, of->items[1]->text);
        if (why[0]) snprintf(pending_why, sizeof pending_why, "Machine %s: %s", of->items[1]->text, why);
        return -2;
    }
    if (!of || of->n != 2 || !name_ok(of->items[1]) || (r->machine = dc_find_machine(m, of->items[1]->text)) < 0)
        return fail(err, es, "Representation %s: field Of names no declared machine (%s)", nm, of && of->n == 2 && of->items[1]->kind == SX_SYM ? of->items[1]->text : "?");
    if (en && en->n == 2 && name_ok(en->items[1]) && is_tmap(m, en->items[1]->text)) {   /* M0 type-form map */
        if ((r->encode = typed_map_on(m, en->items[1]->text, m->mach[r->machine].states, -1, err, es)) < 0) return -1;
    } else {
        if (!en || en->n != 2 || !name_ok(en->items[1]) || (r->encode = dc_find_map(m, en->items[1]->text)) < 0)
            return fail(err, es, "Representation %s: field Encode names no declared map (%s)", nm, en && en->n == 2 && en->items[1]->kind == SX_SYM ? en->items[1]->text : "?");
        if ((r->encode = restrict_map(m, r->encode, m->mach[r->machine].states, 0, err, es)) < 0) return -1;
    }
    if (m->map[r->encode].from != m->mach[r->machine].states)
        return fail(err, es, "Representation %s: field Encode map does not start at the states of %s", nm, m->mach[r->machine].name);
    if (m->car[m->map[r->encode].to].builtin_bool) {   /* only the Observe use of a Bool map is lowered */
        snprintf(pending_why, sizeof pending_why, "Encode map %s targets Bool; a (To Bool) map is lowered only as an Observe port", m->map[r->encode].name);
        return -2;
    }
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
    if (mp && mp->n == 2 && name_ok(mp->items[1]) && is_tmap(m, mp->items[1]->text)) {
        /* M0 type-form map: tabulated on the Source machine's states into the Target's states */
        int si = so->items[1]->kind == SX_SYM ? dc_find_machine(m, so->items[1]->text) : -1;
        if (si < 0 && so->items[1]->kind == SX_SYM && dc_is_skipped(m, so->items[1]->text)) { snprintf(pending_why, sizeof pending_why, "%s", dc_skip_why(m, so->items[1]->text)); return -2; }
        if (si < 0 && so->items[1]->kind != SX_SYM) { fail(err, es, "[M0] AbstractionMap %s: a type-form Map with a derived Source is outside the M0 fragment", nm); snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1; }
        if (si < 0) return fail(err, es, "AbstractionMap %s: field Source names no declared machine (%s)", nm, so->items[1]->text);
        if ((a->map = typed_map_on(m, mp->items[1]->text, m->mach[si].states, m->mach[a->target].states, err, es)) < 0) return -1;
    } else
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
        return dc_rat_min(one, dc_rat_abs(dc_rat_sub(a, b, ovf))); }  /* spec l.686-694: d = min(1, |p - q|) */
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
    if (c < 0) {   /* lowering-unsupported: On names a carrier this engine skipped/cannot table -> fragment limit */
        int frag = sx_head_is(on, "On") && on->n == 2 && name_ok(on->items[1]) && name_frag(m, on->items[1]->text);
        return fail(err, es, "%sTolerance %s: field On names no declared carrier", frag ? "[M0] " : "", nm);
    }
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
/* The recorded reason of the skipped declaration an admission error references ("... (Name)"), or "". */
static const char *referenced_why(const DcModule *m, const char *err) {
    const char *o = strrchr(err, '('), *c = o ? strchr(o, ')') : NULL;
    if (!o || !c || c - o - 1 >= DC_MAX_NAME) return "";
    char nm[DC_MAX_NAME]; memcpy(nm, o + 1, (size_t)(c - o - 1)); nm[c - o - 1] = 0;
    return dc_skip_why(m, nm);
}
/* An admission error that only references a skipped declaration ("... (Name)")
 * is a fragment limit too. */
static int refers_to_skipped(const DcModule *m, const char *err) {
    const char *o = strrchr(err, '('), *c = o ? strchr(o, ')') : NULL;
    if (!o || !c || c - o - 1 >= DC_MAX_NAME) return 0;
    char nm[DC_MAX_NAME]; memcpy(nm, o + 1, (size_t)(c - o - 1)); nm[c - o - 1] = 0;
    return name_frag(m, nm);
}
/* lowering-unsupported: a name the table engine cannot resolve is a fragment limit
 * (Unsupported) when it is a builtin type, a declaration this engine skipped, or the
 * module has an (Import ..) whose transitive declarations the engine does not inline
 * (M1 admission has already resolved every name before the engine runs). */
static int name_frag(const DcModule *m, const char *nm) {
    static const char *const builtin[] = { "Nat", "Int", "Rational", "Rational01", "Real", "Symbol", "String", "Bool", "PBit", "Dist", NULL };
    if (!nm) return 0;
    for (int i = 0; builtin[i]; i++) if (!strcmp(builtin[i], nm)) return 1;
    if (dc_is_skipped(m, nm)) return 1;
    const Sx *src = m->source; int imp = 0;
    for (size_t i = 2; src && i < src->n; i++) {
        const Sx *d = src->items[i];
        if (sx_head_is(d, "Import")) imp = 1;
        /* review 1 finding 4: a name declared locally (Carrier, or another kind such as a Map named where a
         * carrier is expected) is resolved by admission; an unresolved reference to it is a wrong-kind spec
         * violation (InvalidInput), not an import fragment limit. */
        if (!sx_head_is(d, "Import") && d->n >= 2 && d->items[1]->kind == SX_SYM && !strcmp(d->items[1]->text, nm)) return 0;
    }
    return imp;
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
    m->hyperseed = uses_lib(m, "Hyperseed") && dc_eval_beyond_release();   /* M7 opt-in */
    m->neural = uses_lib(m, "Neural") && dc_eval_beyond_release();   /* M7 opt-in */
    m->natarith = uses_lib(m, "NatArith") && dc_eval_beyond_release();   /* NatArith opt-in (not in the release-1 manifest) */
    m->discovery = uses_lib(m, "Discovery") && dc_eval_beyond_release();   /* M7 opt-in */
    m->bitvectors = uses_lib(m, "BitVectors") && dc_eval_beyond_release();   /* M7 opt-in */
    m->finitesets = uses_lib(m, "FiniteSets") && dc_eval_beyond_release();   /* M7 opt-in */
    for (size_t i = 2; i < form->n; i++) {
        const Sx *d = form->items[i]; int rc = 0; pending_why[0] = 0;
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
                else if (!strcmp(key, "Carriers") && !strcmp(val, "Snapshot") && dc_eval_beyond_release()) m->snapshot = 1;   /* M7 Z01 opt-in */
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
        else if (m->snapshot && strcmp(h, "Derive")) continue;   /* M7 Z01: snapshot decls are read by ops_m7_snapshot.c from m->source */
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
        if (rc == -1 && (strstr(err, "[M0]") || refers_to_skipped(m, err))) {
            rc = -2;
            if (!pending_why[0] && !strstr(err, "[M0]")) snprintf(pending_why, sizeof pending_why, "%s", referenced_why(m, err));
        }
        else if (rc == -1) pending_why[0] = 0;
        /* a form-naming reason (Bool Observe maps, type-form maps, Like machines and what uses them) is kept for the requests */
        if (rc == -2 && pending_why[0] && d->n > 1 && d->items[1]->kind == SX_SYM && m->nskipwhy < sizeof m->skipwhy / sizeof m->skipwhy[0]) {
            snprintf(m->skipwhy[m->nskipwhy].name, DC_MAX_NAME, "%.63s", d->items[1]->text);
            snprintf(m->skipwhy[m->nskipwhy].why, sizeof m->skipwhy[0].why, "%s", pending_why); m->nskipwhy++;
        }
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
    for (size_t i = 0; i < m->ncar; i++) { for (size_t j = 0; j < m->car[i].n; j++) sx_free(m->car[i].elems[j]); free(m->car[i].elems); free(m->car[i].sub_idx); sx_free(m->car[i].type); }
    for (size_t i = 0; i < m->nmap; i++) free(m->map[i].table);
    for (size_t i = 0; i < m->ntol; i++) free(m->tol[i].table);
    for (size_t i = 0; i < m->nabs; i++) sx_free(m->abs[i].source);
    for (size_t i = 0; i < m->nder; i++) sx_free(m->der[i].request);
    sx_free(m->source);
    memset(m, 0, sizeof *m);
}
