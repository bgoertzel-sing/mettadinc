#define _POSIX_C_SOURCE 200809L   /* mkdtemp, fork/exec for the proof backend */
/* M3: symbolic carriers (BitVector words as BDD variables), term maps as
 * per-bit BDD vectors, signature refinement, cone of influence, reachability
 * with words, and symbolic block-partition admission.  Nothing is tabulated. */
#include "ops_internal.h"
#include "ops_run.h"
#include "bdd.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>

#define SYM_MAXW 64
/* Obligation generator version (spec 15.3: recorded in every certificate it contributes to). */
#define SYM_GEN_VERSION "m3.1"
/* Resources of the current symbolic request (spec 6.2: concrete words touched; no enumeration). */
static long sym_res_words = -1; static size_t sym_res_nodes;
static long sym_res_xcheck;   /* sample words evaluated by internal cross-checks (not part of any answer) */
/* A compiled term value: either a constant (w = -1, k) or w BDD bits (bit 0 first). */
typedef struct { int w; uint64_t k; DcBdd b[SYM_MAXW]; } SymVal;

static int sterr(char *err, size_t es, const char *msg, const Sx *t) {
    char *s = t ? sx_print(t) : NULL;
    snprintf(err, es, "%s%s%.120s", msg, s ? ": " : "", s ? s : "");
    free(s); return -1;
}
static int lit_of(const Sx *t, uint64_t *v) {
    if (!t || t->kind != SX_SYM || !t->text[0]) return 0;
    char *e; unsigned long long x = strtoull(t->text, &e, 10);
    if (*e || t->text[0] == '-') return 0;
    *v = x; return 1;
}
/* Make a constant into w bits. */
static void widen(SymVal *v, int w) {
    if (v->w >= 0) return;
    uint64_t k = v->k; v->w = w;
    for (int i = 0; i < w; i++) v->b[i] = (k >> i) & 1 ? 1 : 0;
}

typedef struct { DcBddMgr *bm; const char *var; const DcBdd *xv; int W; char *err; size_t es; } SymCtx;

static int sym_term(SymCtx *c, const Sx *t, SymVal *o);

static int arg_idx(SymCtx *c, const Sx *t, int lim, int *i) {
    uint64_t v;
    if (!lit_of(t, &v) || v >= (uint64_t)lim) return sterr(c->err, c->es, "bit index out of range or not a literal", t);
    *i = (int)v; return 0;
}
static int to_bool(SymCtx *c, SymVal *v, const Sx *t) {
    if (v->w < 0) { if (v->k > 1) return sterr(c->err, c->es, "expected a bit", t); widen(v, 1); }
    if (v->w != 1) return sterr(c->err, c->es, "expected a bit (width 1)", t);
    return 0;
}

static int sym_term(SymCtx *c, const Sx *t, SymVal *o) {
    DcBddMgr *bm = c->bm;
    memset(o, 0, sizeof *o);
    if (t->kind == SX_SYM) {
        if (!strcmp(t->text, c->var)) { o->w = c->W; memcpy(o->b, c->xv, (size_t)c->W * sizeof(DcBdd)); return 0; }
        if (lit_of(t, &o->k)) { o->w = -1; return 0; }
        return sterr(c->err, c->es, "unknown symbol in Body", t);
    }
    if (t->kind != SX_LIST || t->n == 0 || t->items[0]->kind != SX_SYM) return sterr(c->err, c->es, "bad Body term", t);
    const char *h = t->items[0]->text; size_t n = t->n;
    SymVal a, b;
    if (!strcmp(h, "BitAt") && n == 3) {
        int i; if (sym_term(c, t->items[1], &a) || a.w < 0 || arg_idx(c, t->items[2], a.w, &i)) return -1;
        o->w = 1; o->b[0] = a.b[i]; return 0;
    }
    if (!strcmp(h, "Slice") && n == 4) {
        int i, j; if (sym_term(c, t->items[1], &a) || a.w < 0 || arg_idx(c, t->items[2], a.w, &i) || arg_idx(c, t->items[3], a.w, &j)) return -1;
        if (j < i) return sterr(c->err, c->es, "Slice: empty range", t);
        o->w = j - i + 1; for (int k = i; k <= j; k++) o->b[k - i] = a.b[k]; return 0;
    }
    if (!strcmp(h, "SwapBits") && n == 4) {
        int i, j; if (sym_term(c, t->items[1], &a) || a.w < 0 || arg_idx(c, t->items[2], a.w, &i) || arg_idx(c, t->items[3], a.w, &j)) return -1;
        *o = a; o->b[i] = a.b[j]; o->b[j] = a.b[i]; return 0;
    }
    if (!strcmp(h, "RotateRange") && n == 4) {   /* up by one: bit k <- bit k-1, bit lo <- bit hi */
        int i, j; if (sym_term(c, t->items[1], &a) || a.w < 0 || arg_idx(c, t->items[2], a.w, &i) || arg_idx(c, t->items[3], a.w, &j)) return -1;
        if (j < i) return sterr(c->err, c->es, "RotateRange: empty range", t);
        *o = a; for (int k = i + 1; k <= j; k++) o->b[k] = a.b[k - 1]; o->b[i] = a.b[j]; return 0;
    }
    if (!strcmp(h, "SetBit") && n == 4) {
        int i; if (sym_term(c, t->items[1], &a) || a.w < 0 || arg_idx(c, t->items[2], a.w, &i)) return -1;
        if (sym_term(c, t->items[3], &b) || to_bool(c, &b, t->items[3])) return -1;
        *o = a; o->b[i] = b.b[0]; return 0;
    }
    if (!strcmp(h, "Parity") && n == 2) {
        if (sym_term(c, t->items[1], &a) || a.w < 0) return sterr(c->err, c->es, "Parity: expected a vector", t);
        DcBdd p = 0; for (int k = 0; k < a.w; k++) p = dc_bdd_xor(bm, p, a.b[k]);
        o->w = 1; o->b[0] = p; return 0;
    }
    if (!strcmp(h, "IsZero") && n == 2) {
        if (sym_term(c, t->items[1], &a)) return -1;
        if (a.w < 0) { o->w = -1; o->k = a.k == 0; return 0; }
        DcBdd z = 1; for (int k = 0; k < a.w; k++) z = dc_bdd_and(bm, z, dc_bdd_not(bm, a.b[k]));
        o->w = 1; o->b[0] = z; return 0;
    }
    if (!strcmp(h, "Not") && n == 2) {
        if (sym_term(c, t->items[1], &a) || to_bool(c, &a, t->items[1])) return -1;
        o->w = 1; o->b[0] = dc_bdd_not(bm, a.b[0]); return 0;
    }
    if ((!strcmp(h, "And") || !strcmp(h, "Or") || !strcmp(h, "Xor")) && n == 3) {
        if (sym_term(c, t->items[1], &a) || sym_term(c, t->items[2], &b)) return -1;
        if (a.w < 0 && b.w < 0) return sterr(c->err, c->es, "constant-only term", t);
        widen(&a, b.w); widen(&b, a.w);
        if (a.w != b.w) return sterr(c->err, c->es, "width mismatch", t);
        o->w = a.w;
        for (int k = 0; k < a.w; k++)
            o->b[k] = h[0] == 'A' ? dc_bdd_and(bm, a.b[k], b.b[k]) : h[0] == 'O' ? dc_bdd_or(bm, a.b[k], b.b[k]) : dc_bdd_xor(bm, a.b[k], b.b[k]);
        return 0;
    }
    if (!strcmp(h, "Eq") && n == 3) {
        if (sym_term(c, t->items[1], &a) || sym_term(c, t->items[2], &b)) return -1;
        if (a.w < 0 && b.w < 0) { o->w = -1; o->k = a.k == b.k; return 0; }
        int w = a.w >= 0 ? a.w : b.w;
        SymVal *cv = a.w < 0 ? &a : b.w < 0 ? &b : NULL;
        if (cv && w < 64 && (cv->k >> w)) { o->w = 1; o->b[0] = 0; return 0; }   /* constant does not fit */
        widen(&a, w); widen(&b, w);
        if (a.w != b.w) return sterr(c->err, c->es, "Eq: width mismatch", t);
        DcBdd e = 1;
        for (int k = 0; k < w; k++) e = dc_bdd_and(bm, e, dc_bdd_not(bm, dc_bdd_xor(bm, a.b[k], b.b[k])));
        o->w = 1; o->b[0] = e; return 0;
    }
    return sterr(c->err, c->es, "Body operator outside the BitVectors fragment", t);
}

/* Independent concrete evaluator (no BDDs): replays witnesses on plain words.
 * Returns 0 and sets *v (value) and *w (width, -1 for an untyped literal), or -1. */
static uint64_t cmask(int w) { return w >= 64 ? ~(uint64_t)0 : (((uint64_t)1 << w) - 1); }
static int sym_ceval(const Sx *t, const char *var, uint64_t x, int W, uint64_t *v, int *w) {
    uint64_t a, b; int wa, wb; uint64_t i, j;
    if (t->kind == SX_SYM) {
        if (!strcmp(t->text, var)) { *v = x & cmask(W); *w = W; return 0; }
        if (lit_of(t, v)) { *w = -1; return 0; }
        return -1;
    }
    if (t->kind != SX_LIST || !t->n || t->items[0]->kind != SX_SYM) return -1;
    const char *h = t->items[0]->text; size_t n = t->n;
#define EV(k, vv, ww) if (sym_ceval(t->items[k], var, x, W, &vv, &ww)) return -1
    if (!strcmp(h, "BitAt") && n == 3) { EV(1, a, wa); if (wa < 0 || !lit_of(t->items[2], &i) || i >= (uint64_t)wa) return -1; *v = (a >> i) & 1; *w = 1; return 0; }
    if (!strcmp(h, "Slice") && n == 4) { EV(1, a, wa); if (wa < 0 || !lit_of(t->items[2], &i) || !lit_of(t->items[3], &j) || j < i || j >= (uint64_t)wa) return -1;
        *w = (int)(j - i + 1); *v = (a >> i) & cmask(*w); return 0; }
    if (!strcmp(h, "SwapBits") && n == 4) { EV(1, a, wa); if (wa < 0 || !lit_of(t->items[2], &i) || !lit_of(t->items[3], &j) || i >= (uint64_t)wa || j >= (uint64_t)wa) return -1;
        uint64_t bi = (a >> i) & 1, bj = (a >> j) & 1; a &= ~(((uint64_t)1 << i) | ((uint64_t)1 << j)); *v = a | (bj << i) | (bi << j); *w = wa; return 0; }
    if (!strcmp(h, "RotateRange") && n == 4) { EV(1, a, wa); if (wa < 0 || !lit_of(t->items[2], &i) || !lit_of(t->items[3], &j) || j < i || j >= (uint64_t)wa) return -1;
        int len = (int)(j - i + 1); uint64_t m = cmask(len), f = (a >> i) & m;
        uint64_t r = len == 1 ? f : (((f << 1) | (f >> (len - 1))) & m);
        *v = (a & ~(m << i)) | (r << i); *w = wa; return 0; }
    if (!strcmp(h, "SetBit") && n == 4) { EV(1, a, wa); EV(3, b, wb); if (wa < 0 || !lit_of(t->items[2], &i) || i >= (uint64_t)wa || b > 1) return -1;
        *v = (a & ~((uint64_t)1 << i)) | (b << i); *w = wa; return 0; }
    if (!strcmp(h, "Parity") && n == 2) { EV(1, a, wa); if (wa < 0) return -1; *v = (uint64_t)__builtin_parityll(a); *w = 1; return 0; }
    if (!strcmp(h, "IsZero") && n == 2) { EV(1, a, wa); *v = a == 0; *w = wa < 0 ? -1 : 1; return 0; }
    if (!strcmp(h, "Not") && n == 2) { EV(1, a, wa); if (a > 1) return -1; *v = !a; *w = 1; return 0; }
    if ((!strcmp(h, "And") || !strcmp(h, "Or") || !strcmp(h, "Xor")) && n == 3) {
        EV(1, a, wa); EV(2, b, wb); if (wa < 0 && wb < 0) return -1;
        int ww = wa >= 0 ? wa : wb; if (wa >= 0 && wb >= 0 && wa != wb) return -1;
        *v = (h[0] == 'A' ? (a & b) : h[0] == 'O' ? (a | b) : (a ^ b)) & cmask(ww); *w = ww; return 0; }
    if (!strcmp(h, "Eq") && n == 3) { EV(1, a, wa); EV(2, b, wb); if (wa >= 0 && wb >= 0 && wa != wb) return -1; *v = a == b; *w = (wa < 0 && wb < 0) ? -1 : 1; return 0; }
#undef EV
    return -1;
}

/* ---- part 6a: independent Tseitin bit-blaster (proof path; never reads the BDDs) ----
 * Variables 1..W are the word bits x0..x_{W-1}; W+1 is the constant true (unit clause).
 * Gates are numbered in creation order, so every gate depends only on lower variables;
 * gate definitions are kept so an assignment can be computed for self-checks. */
typedef struct { int nv, tru, bad; int *cl; size_t n, cap, ncl; int *gd; size_t gcap; } Cnf;
static void cnf_lit(Cnf *c, int l) {
    if (c->n == c->cap) { size_t nc = c->cap ? 2 * c->cap : 4096; int *t = realloc(c->cl, nc * sizeof *t); if (!t) { c->bad = 1; return; } c->cl = t; c->cap = nc; }
    c->cl[c->n++] = l;
}
static void cnf_add(Cnf *c, int a, int b, int d) { cnf_lit(c, a); if (b) cnf_lit(c, b); if (d) cnf_lit(c, d); cnf_lit(c, 0); c->ncl++; }
static void cnf_free(Cnf *c) { free(c->cl); free(c->gd); memset(c, 0, sizeof *c); }
static int cnf_init(Cnf *c, int W) { memset(c, 0, sizeof *c); c->nv = W + 1; c->tru = W + 1; cnf_add(c, c->tru, 0, 0); return c->bad ? -1 : 0; }
static int cnf_gate(Cnf *c, int op, int a, int b) {
    int g = ++c->nv;
    if ((size_t)(3 * g + 3) > c->gcap) { size_t nc = c->gcap ? 2 * c->gcap : 3 * 4096; while (nc < (size_t)(3 * g + 3)) nc *= 2;
        int *t = realloc(c->gd, nc * sizeof *t); if (!t) { c->bad = 1; return g; } c->gd = t; c->gcap = nc; }
    c->gd[3 * g] = op; c->gd[3 * g + 1] = a; c->gd[3 * g + 2] = b; return g;
}
static int cnf_and(Cnf *c, int a, int b) {
    int T = c->tru;
    if (a == -T || b == -T || a == -b) return -T;
    if (a == T || a == b) return b;
    if (b == T) return a;
    int g = cnf_gate(c, 1, a, b); cnf_add(c, -g, a, 0); cnf_add(c, -g, b, 0); cnf_add(c, g, -a, -b); return g;
}
static int cnf_or(Cnf *c, int a, int b) { return -cnf_and(c, -a, -b); }
static int cnf_xor(Cnf *c, int a, int b) {
    int T = c->tru;
    if (a == T) return -b;
    if (a == -T) return b;
    if (b == T) return -a;
    if (b == -T) return a;
    if (a == b) return -T;
    if (a == -b) return T;
    int g = cnf_gate(c, 2, a, b);
    cnf_add(c, -g, a, b); cnf_add(c, -g, -a, -b); cnf_add(c, g, -a, b); cnf_add(c, g, a, -b); return g;
}
/* val[1..nv]: the assignment forced by word (self-check only). */
static void cnf_assign(const Cnf *c, uint64_t word, unsigned char *val) {
    int W = c->tru - 1;
    for (int v = 1; v <= W; v++) val[v] = (word >> (v - 1)) & 1;
    val[c->tru] = 1;
#define LV(l) ((l) > 0 ? val[(l)] : !val[-(l)])
    for (int g = c->tru + 1; g <= c->nv; g++) {
        int a = c->gd[3 * g + 1], b = c->gd[3 * g + 2];
        val[g] = c->gd[3 * g] == 1 ? (LV(a) && LV(b)) : (LV(a) != LV(b));
    }
#undef LV
}
static int cnf_sat_by(const Cnf *c, const unsigned char *val) {   /* every clause satisfied */
    int sat = 0;
    for (size_t i = 0; i < c->n; i++) {
        int l = c->cl[i];
        if (!l) { if (!sat) return 0; sat = 0; continue; }
        if (l > 0 ? val[l] : !val[-l]) sat = 1;
    }
    return 1;
}

typedef struct { int w; uint64_t k; int b[SYM_MAXW]; } CVal;
typedef struct { Cnf *c; const char *var; const int *xv; int W; } CCtx;
static void cwiden(CCtx *x, CVal *v, int w) {
    if (v->w >= 0) return;
    uint64_t k = v->k; v->w = w;
    for (int i = 0; i < w; i++) v->b[i] = ((k >> i) & 1) ? x->c->tru : -x->c->tru;
}
static int cbool(CCtx *x, CVal *v) {
    if (v->w < 0) { if (v->k > 1) return -1; cwiden(x, v, 1); }
    return v->w == 1 ? 0 : -1;
}
static int cnf_term(CCtx *x, const Sx *t, CVal *o) {
    Cnf *c = x->c; uint64_t i, j; CVal a, b;
    if (t->kind == SX_SYM) {
        if (!strcmp(t->text, x->var)) { o->w = x->W; memcpy(o->b, x->xv, (size_t)x->W * sizeof(int)); return 0; }
        if (lit_of(t, &o->k)) { o->w = -1; return 0; }
        return -1;
    }
    if (t->kind != SX_LIST || !t->n || t->items[0]->kind != SX_SYM) return -1;
    const char *h = t->items[0]->text; size_t n = t->n;
#define CT(k, v) if (cnf_term(x, t->items[k], &v)) return -1
#define IX(k, v, lim) (lit_of(t->items[k], &v) && v < (uint64_t)(lim))
    if (!strcmp(h, "BitAt") && n == 3) { CT(1, a); if (a.w < 0 || !IX(2, i, a.w)) return -1; o->w = 1; o->b[0] = a.b[i]; return 0; }
    if (!strcmp(h, "Slice") && n == 4) { CT(1, a); if (a.w < 0 || !IX(2, i, a.w) || !IX(3, j, a.w) || j < i) return -1;
        o->w = (int)(j - i + 1); for (uint64_t k = i; k <= j; k++) o->b[k - i] = a.b[k]; return 0; }
    if (!strcmp(h, "SwapBits") && n == 4) { CT(1, a); if (a.w < 0 || !IX(2, i, a.w) || !IX(3, j, a.w)) return -1;
        *o = a; o->b[i] = a.b[j]; o->b[j] = a.b[i]; return 0; }
    if (!strcmp(h, "RotateRange") && n == 4) { CT(1, a); if (a.w < 0 || !IX(2, i, a.w) || !IX(3, j, a.w) || j < i) return -1;
        *o = a; for (uint64_t k = i + 1; k <= j; k++) o->b[k] = a.b[k - 1]; o->b[i] = a.b[j]; return 0; }
    if (!strcmp(h, "SetBit") && n == 4) { CT(1, a); CT(3, b); if (a.w < 0 || !IX(2, i, a.w) || cbool(x, &b)) return -1;
        *o = a; o->b[i] = b.b[0]; return 0; }
    if (!strcmp(h, "Parity") && n == 2) { CT(1, a); if (a.w < 0) return -1;
        int p = -c->tru; for (int k = 0; k < a.w; k++) p = cnf_xor(c, p, a.b[k]); o->w = 1; o->b[0] = p; return 0; }
    if (!strcmp(h, "IsZero") && n == 2) { CT(1, a); if (a.w < 0) { o->w = -1; o->k = a.k == 0; return 0; }
        int z = c->tru; for (int k = 0; k < a.w; k++) z = cnf_and(c, z, -a.b[k]); o->w = 1; o->b[0] = z; return 0; }
    if (!strcmp(h, "Not") && n == 2) { CT(1, a); if (cbool(x, &a)) return -1; o->w = 1; o->b[0] = -a.b[0]; return 0; }
    if ((!strcmp(h, "And") || !strcmp(h, "Or") || !strcmp(h, "Xor")) && n == 3) {
        CT(1, a); CT(2, b); if (a.w < 0 && b.w < 0) return -1;
        cwiden(x, &a, b.w); cwiden(x, &b, a.w); if (a.w != b.w) return -1;
        o->w = a.w;
        for (int k = 0; k < a.w; k++) o->b[k] = h[0] == 'A' ? cnf_and(c, a.b[k], b.b[k]) : h[0] == 'O' ? cnf_or(c, a.b[k], b.b[k]) : cnf_xor(c, a.b[k], b.b[k]);
        return 0;
    }
    if (!strcmp(h, "Eq") && n == 3) {
        CT(1, a); CT(2, b);
        if (a.w < 0 && b.w < 0) { o->w = -1; o->k = a.k == b.k; return 0; }
        int w = a.w >= 0 ? a.w : b.w; CVal *cv = a.w < 0 ? &a : b.w < 0 ? &b : NULL;
        o->w = 1;
        if (cv && w < 64 && (cv->k >> w)) { o->b[0] = -c->tru; return 0; }
        cwiden(x, &a, w); cwiden(x, &b, w); if (a.w != b.w) return -1;
        int e = c->tru; for (int k = 0; k < w; k++) e = cnf_and(c, e, -cnf_xor(c, a.b[k], b.b[k]));
        o->b[0] = e; return 0;
    }
#undef CT
#undef IX
    return -1;
}

/* ---- module reader: the symbolic declarations are read from m->source ---- */
#define SYM_NM 64
typedef struct { char name[SYM_NM]; int width; const Sx *reach; } SCar;   /* bit vector; reach != NULL: (Reach Machine (From k)) subset */
typedef struct { char name[SYM_NM]; int from, to; const Sx *var, *body; } SMap;
typedef struct { char name[SYM_NM]; int map; } SPort;
typedef struct { char name[SYM_NM]; int states; SPort obs[8]; int nobs; SPort act[8]; int nact; } SMach;
typedef struct { char name[SYM_NM]; const Sx *form; } SDecl;
typedef struct {
    SCar car[16]; int ncar; SMap map[32]; int nmap; SMach mach[8]; int nmach;
    SDecl decl[32]; int ndecl;           /* Representation, BlockPartition, Reach, ... by name */
} SymMod;

static int sfind_car(const SymMod *s, const char *n) { for (int i = 0; i < s->ncar; i++) if (!strcmp(s->car[i].name, n)) return i; return -1; }
static int sfind_map(const SymMod *s, const char *n) { for (int i = 0; i < s->nmap; i++) if (!strcmp(s->map[i].name, n)) return i; return -1; }
static int sfind_mach(const SymMod *s, const char *n) { for (int i = 0; i < s->nmach; i++) if (!strcmp(s->mach[i].name, n)) return i; return -1; }
static const Sx *sfind_decl(const SymMod *s, const char *n) { for (int i = 0; i < s->ndecl; i++) if (!strcmp(s->decl[i].name, n)) return s->decl[i].form; return NULL; }
static const Sx *sfield(const Sx *d, const char *h) { for (size_t i = 2; i < d->n; i++) if (sx_head_is(d->items[i], h)) return d->items[i]; return NULL; }
static int sname(const Sx *f, size_t k, const char **out) {
    if (!f || f->n <= k || f->items[k]->kind != SX_SYM) return -1;
    *out = f->items[k]->text; return 0;
}

static int sym_read(const Sx *src, SymMod *s, char *err, size_t es) {
    memset(s, 0, sizeof *s);
    for (size_t i = 2; i < src->n; i++) {
        const Sx *d = src->items[i]; const char *nm, *t;
        if (d->kind != SX_LIST || d->n < 2 || d->items[0]->kind != SX_SYM) continue;
        const char *h = d->items[0]->text;
        if (!strcmp(h, "Profile") || !strcmp(h, "Use") || !strcmp(h, "Derive")) continue;
        if (sname(d, 1, &nm) || strlen(nm) >= SYM_NM) return sterr(err, es, "declaration without a name", d);
        if (!strcmp(h, "Carrier")) {
            if (s->ncar == 16) return sterr(err, es, "too many carriers", d);
            const Sx *of = sfield(d, "Of"); SCar *c = &s->car[s->ncar];
            snprintf(c->name, SYM_NM, "%s", nm);
            if (of && of->n == 2 && sx_head_is(of->items[1], "BitVector") && of->items[1]->n == 2) {
                uint64_t w; if (!lit_of(of->items[1]->items[1], &w) || w < 1 || w > SYM_MAXW) return sterr(err, es, "BitVector width outside 1..64", d);
                const Sx *rc = sfield(d, "Reach");
                if (rc) {
                    if (rc->n != 3 || rc->items[1]->kind != SX_SYM || !sx_head_is(rc->items[2], "From") || rc->items[2]->n != 2)
                        return sterr(err, es, "expected (Reach Machine (From word))", d);
                    c->reach = rc;
                } else if (!sfield(d, "All")) return sterr(err, es, "symbolic carrier must be (All) or (Reach ..)", d);
                c->width = (int)w;
            } else {
                const Sx *en = sfield(d, "Enum");      /* (Enum 0 1 ..): Nat literals 0..2^k-1 */
                if (!en || en->n < 2) return sterr(err, es, "carrier is neither (BitVector w) nor (Enum ..)", d);
                uint64_t v, mx = 0;
                for (size_t k = 1; k < en->n; k++) { if (!lit_of(en->items[k], &v) || v != k - 1) return sterr(err, es, "Enum must be 0..n-1", d); mx = v; }
                int w = 1; while (w < 63 && (mx >> w)) w++;
                if (((uint64_t)1 << w) != mx + 1) return sterr(err, es, "Enum size must be a power of two on a symbolic module", d);
                c->width = w;
            }
            s->ncar++;
        } else if (!strcmp(h, "Map")) {
            if (s->nmap == 32) return sterr(err, es, "too many maps", d);
            SMap *mp = &s->map[s->nmap]; snprintf(mp->name, SYM_NM, "%s", nm);
            const Sx *fr = sfield(d, "From"), *to = sfield(d, "To"), *b = sfield(d, "Body");
            if (sname(fr, 1, &t) || (mp->from = sfind_car(s, t)) < 0) return sterr(err, es, "Map: From names no carrier", d);
            if (sname(to, 1, &t) || (mp->to = sfind_car(s, t)) < 0) return sterr(err, es, "Map: To names no carrier", d);
            if (!b || b->n != 3 || b->items[1]->kind != SX_LIST || b->items[1]->n != 1 || b->items[1]->items[0]->kind != SX_SYM)
                return sterr(err, es, "Map: expected (Body ($x) term)", d);
            mp->var = b->items[1]->items[0]; mp->body = b->items[2]; s->nmap++;
        } else if (!strcmp(h, "Machine")) {
            if (s->nmach == 8) return sterr(err, es, "too many machines", d);
            SMach *M = &s->mach[s->nmach]; snprintf(M->name, SYM_NM, "%s", nm);
            const Sx *st = sfield(d, "States");
            if (sname(st, 1, &t) || (M->states = sfind_car(s, t)) < 0) return sterr(err, es, "Machine: States names no carrier", d);
            for (size_t k = 2; k < d->n; k++) {
                const Sx *f = d->items[k]; int isobs = sx_head_is(f, "Observe"), isact = sx_head_is(f, "Action");
                if (!isobs && !isact) { if (sx_head_is(f, "States")) continue; return sterr(err, es, "Machine field outside the M3 symbolic fragment", f); }
                const char *pn, *mn; int mi;
                if (f->n != 3 || sname(f, 1, &pn) || sname(f, 2, &mn) || (mi = sfind_map(s, mn)) < 0 || strlen(pn) >= SYM_NM)
                    return sterr(err, es, "Machine: expected (Observe|Action port map)", f);
                if (s->car[s->map[mi].from].width != s->car[M->states].width || (isact && s->car[s->map[mi].to].width != s->car[M->states].width)) return sterr(err, es, "Machine: port map has the wrong carriers", f);
                SPort *P = isobs ? &M->obs[M->nobs] : &M->act[M->nact];
                if ((isobs ? M->nobs : M->nact) == 8) return sterr(err, es, "too many ports", f);
                snprintf(P->name, SYM_NM, "%s", pn); P->map = mi;
                if (isobs) M->nobs++; else M->nact++;
            }
            s->nmach++;
        } else {
            if (s->ndecl == 32) return sterr(err, es, "too many declarations", d);
            snprintf(s->decl[s->ndecl].name, SYM_NM, "%s", nm); s->decl[s->ndecl].form = d; s->ndecl++;
        }
    }
    return 0;
}

/* Compile map mi applied to the state variables xv (width = from-carrier width). */
static int sym_apply(DcBddMgr *bm, const SymMod *s, int mi, const DcBdd *xv, SymVal *o, char *err, size_t es) {
    const SMap *mp = &s->map[mi];
    SymCtx c = { bm, mp->var->text, xv, s->car[mp->from].width, err, es };
    if (sym_term(&c, mp->body, o)) return -1;
    widen(o, s->car[mp->to].width);
    if (o->w != s->car[mp->to].width) { snprintf(err, es, "Map %s: Body width %d does not match carrier %s", mp->name, o->w, s->car[mp->to].name); return -1; }
    return 0;
}

/* ---- part 3: reachability with words, block-partition obligations (BDD candidate) ---- */
#define SYM_REACH_MAX 65536
#define SYM_MAXB 32
typedef struct { uint64_t w; int parent, act; } RNode;
typedef struct { DcBddMgr *bm; int W; DcBdd xv[SYM_MAXW]; } SymEnv;
typedef struct { const char *obl; uint64_t wit; char what[160]; } SymFail;

static int senv_init(SymEnv *e, int W) {
    memset(e, 0, sizeof *e);
    if (!(e->bm = dc_bdd_new(W))) return -1;
    e->W = W; for (int i = 0; i < W; i++) e->xv[i] = dc_bdd_var(e->bm, i);
    return 0;
}
static DcBdd word_bdd(SymEnv *e, uint64_t w) {
    DcBdd r = 1;
    for (int i = e->W - 1; i >= 0; i--) r = dc_bdd_and(e->bm, r, ((w >> i) & 1) ? e->xv[i] : dc_bdd_not(e->bm, e->xv[i]));
    return r;
}
static uint64_t sv_eval(SymEnv *e, const SymVal *v, uint64_t w) {
    uint64_t r = 0;
    for (int k = 0; k < v->w; k++) if (dc_bdd_eval(e->bm, v->b[k], w)) r |= (uint64_t)1 << k;
    return r;
}
static int mach_acts(SymEnv *e, const SymMod *S, const SMach *M, SymVal *av, char *err, size_t es) {
    for (int a = 0; a < M->nact; a++) if (sym_apply(e->bm, S, M->act[a].map, e->xv, &av[a], err, es)) return -1;
    return 0;
}
/* Forward closure of {start} under the actions, by breadth-first search on concrete
 * words; every word keeps its parent and action, so each has a reachability witness. */
static int sym_reach(SymEnv *e, const SymVal *av, int nact, uint64_t start, RNode **out, int *nout, char *err, size_t es) {
    if (e->W < 64 && (start >> e->W)) { snprintf(err, es, "initial word outside the width"); return -1; }
    size_t hc = 2 * SYM_REACH_MAX; int *ht = malloc(hc * sizeof *ht); RNode *nd = malloc(SYM_REACH_MAX * sizeof *nd);
    if (!ht || !nd) { free(ht); free(nd); snprintf(err, es, "out of memory"); return -2; }
    for (size_t i = 0; i < hc; i++) ht[i] = -1;
#define RFIND(word, slot) do { slot = (size_t)(((word) * 0x9E3779B97F4A7C15ULL) >> 40) & (hc - 1); \
        while (ht[slot] >= 0 && nd[ht[slot]].w != (word)) slot = (slot + 1) & (hc - 1); } while (0)
    size_t sl; RFIND(start, sl); nd[0] = (RNode){ start, -1, -1 }; ht[sl] = 0; int n = 1;
    for (int q = 0; q < n; q++)
        for (int a = 0; a < nact; a++) {
            uint64_t w = sv_eval(e, &av[a], nd[q].w);
            RFIND(w, sl);
            if (ht[sl] >= 0) continue;
            if (n == SYM_REACH_MAX) { free(ht); free(nd); snprintf(err, es, "reachable set exceeds %d words", SYM_REACH_MAX); return -2; }
            nd[n] = (RNode){ w, q, a }; ht[sl] = n++;
        }
#undef RFIND
    free(ht); *out = nd; *nout = n; return 0;
}

/* 1: all obligations hold (BDD candidate); 0: refuted (*f); -1: invalid input (err); -2: BDD limit. */
static int sym_check_partition(SymEnv *e, const SymMod *S, const SMach *M, const SymVal *av, const Sx *bp, DcBdd C,
                               SymFail *f, char *err, size_t es) {
    DcBddMgr *bm = e->bm;
    const char *bn[SYM_MAXB]; DcBdd B[SYM_MAXB]; uint64_t rep[SYM_MAXB]; int nb = 0, succ[SYM_MAXB][8];
    for (int i = 0; i < SYM_MAXB; i++) for (int a = 0; a < 8; a++) succ[i][a] = -1;
    for (size_t k = 2; k < bp->n; k++) {
        const Sx *b = bp->items[k];
        if (!sx_head_is(b, "Block")) continue;
        const Sx *bd = b->n == 4 ? b->items[2] : NULL;
        if (nb == SYM_MAXB || !bd || b->items[1]->kind != SX_SYM || !sx_head_is(bd, "Body") || bd->n != 3 || bd->items[1]->kind != SX_LIST
            || bd->items[1]->n != 1 || bd->items[1]->items[0]->kind != SX_SYM || !lit_of(b->items[3], &rep[nb]))
            return sterr(err, es, "expected (Block Name (Body ($x) predicate) representative)", b);
        if (e->W < 64 && (rep[nb] >> e->W)) return sterr(err, es, "representative outside the word width", b);
        SymCtx c = { bm, bd->items[1]->items[0]->text, e->xv, e->W, err, es };
        SymVal v; if (sym_term(&c, bd->items[2], &v) || to_bool(&c, &v, bd->items[2])) return -1;
        bn[nb] = b->items[1]->text; B[nb++] = v.b[0];
    }
    if (!nb) return sterr(err, es, "BlockPartition has no blocks", bp);
    for (size_t k = 2; k < bp->n; k++) {
        const Sx *s = bp->items[k]; int a = -1, i = -1, j = -1;
        if (!sx_head_is(s, "Successor")) continue;
        if (s->n != 4 || s->items[1]->kind != SX_SYM || s->items[2]->kind != SX_SYM || s->items[3]->kind != SX_SYM)
            return sterr(err, es, "expected (Successor action from to)", s);
        for (int t = 0; t < M->nact; t++) if (!strcmp(M->act[t].name, s->items[1]->text)) a = t;
        for (int t = 0; t < nb; t++) { if (!strcmp(bn[t], s->items[2]->text)) i = t; if (!strcmp(bn[t], s->items[3]->text)) j = t; }
        if (a < 0 || i < 0 || j < 0) return sterr(err, es, "Successor names no action or block", s);
        succ[i][a] = j;
    }
    for (int i = 0; i < nb; i++) for (int a = 0; a < M->nact; a++)
        if (succ[i][a] < 0) { snprintf(err, es, "no Successor for block %s under action %s", bn[i], M->act[a].name); return -1; }
    uint64_t w; DcBdd D;
#define FAILW(o, wd, ...) do { if (dc_bdd_failed(bm)) return -2; f->obl = o; f->wit = (wd); snprintf(f->what, sizeof f->what, __VA_ARGS__); return 0; } while (0)
    DcBdd U = 0; for (int i = 0; i < nb; i++) U = dc_bdd_or(bm, U, B[i]);
    D = dc_bdd_and(bm, C, dc_bdd_not(bm, U));
    if (dc_bdd_min_word(bm, D, &w)) FAILW("Coverage", w, "word %llu is in no block", (unsigned long long)w);
    for (int i = 0; i < nb; i++) for (int j = i + 1; j < nb; j++) {
        D = dc_bdd_and(bm, C, dc_bdd_and(bm, B[i], B[j]));
        if (dc_bdd_min_word(bm, D, &w)) FAILW("Disjointness", w, "word %llu is in blocks %s and %s", (unsigned long long)w, bn[i], bn[j]);
    }
    if (dc_bdd_failed(bm)) return -2;
    for (int i = 0; i < nb; i++)
        if (!dc_bdd_eval(bm, C, rep[i]) || !dc_bdd_eval(bm, B[i], rep[i]))
            FAILW("Membership", rep[i], "representative %llu of block %s is outside %s", (unsigned long long)rep[i], bn[i], dc_bdd_eval(bm, C, rep[i]) ? "the block" : "the scope");
    for (int p = 0; p < M->nobs; p++) {
        SymVal ob; if (sym_apply(bm, S, M->obs[p].map, e->xv, &ob, err, es)) return -1;
        for (int i = 0; i < nb; i++) {
            uint64_t t = sv_eval(e, &ob, rep[i]);
            for (int k = 0; k < ob.w; k++) {
                DcBdd diff = ((t >> k) & 1) ? dc_bdd_not(bm, ob.b[k]) : ob.b[k];
                D = dc_bdd_and(bm, C, dc_bdd_and(bm, B[i], diff));
                if (dc_bdd_min_word(bm, D, &w)) FAILW("Constancy", w, "observation %s at word %llu differs from representative of block %s", M->obs[p].name, (unsigned long long)w, bn[i]);
            }
        }
    }
    for (int i = 0; i < nb; i++) for (int a = 0; a < M->nact; a++) {
        DcBdd post = dc_bdd_compose(bm, B[succ[i][a]], av[a].b);
        D = dc_bdd_and(bm, C, dc_bdd_and(bm, B[i], dc_bdd_not(bm, post)));
        if (dc_bdd_min_word(bm, D, &w)) FAILW("Stability", w, "action %s takes word %llu of block %s outside block %s", M->act[a].name, (unsigned long long)w, bn[i], bn[succ[i][a]]);
    }
#undef FAILW
    return dc_bdd_failed(bm) ? -2 : 1;
}

/* Concrete replay of a refutation, independent of the BDD path: the blocks,
 * observations, actions and successors are re-read and evaluated on plain words. */
static int cmap(const SymMod *S, int mi, uint64_t x, uint64_t *out) {
    const SMap *mp = &S->map[mi]; uint64_t v; int w, tw = S->car[mp->to].width;
    if (sym_ceval(mp->body, mp->var->text, x, S->car[mp->from].width, &v, &w)) return -1;
    if ((w >= 0 && w != tw) || (v & ~cmask(tw))) return -1;
    *out = v; return 0;
}
static int cblock(const Sx *b, uint64_t x, int W) {
    const Sx *bd = b->items[2]; uint64_t v; int w;
    if (sym_ceval(bd->items[2], bd->items[1]->items[0]->text, x, W, &v, &w) || v > 1) return -1;
    return (int)v;
}
static int sym_replay(const SymMod *S, const SMach *M, const Sx *bp, const RNode *nd, int nn, const SymFail *f) {
    int W = S->car[M->states].width, nb = 0, hits = 0, hi = -1; uint64_t x = f->wit, rp[SYM_MAXB];
    const Sx *bl[SYM_MAXB]; int mem[SYM_MAXB];
    int insc = W >= 64 || !(x >> W);
    if (nd) { insc = 0; for (int k = 0; k < nn; k++) if (nd[k].w == x) insc = 1; }
    for (size_t k = 2; k < bp->n && nb < SYM_MAXB; k++) {
        const Sx *b = bp->items[k];
        if (!sx_head_is(b, "Block")) continue;
        if (!lit_of(b->items[3], &rp[nb])) return 0;
        bl[nb] = b; if ((mem[nb] = cblock(b, x, W)) < 0) return 0;
        if (mem[nb]) { hits++; hi = nb; }
        nb++;
    }
    if (!strcmp(f->obl, "Coverage")) return insc && hits == 0;
    if (!strcmp(f->obl, "Disjointness")) return insc && hits >= 2;
    if (!strcmp(f->obl, "Membership")) { for (int k = 0; k < nb; k++) if (rp[k] == x && (!insc || !mem[k])) return 1; return 0; }
    if (!insc || hits != 1) return 0;
    if (!strcmp(f->obl, "Constancy")) {
        for (int p = 0; p < M->nobs; p++) { uint64_t o1, o2;
            if (cmap(S, M->obs[p].map, x, &o1) || cmap(S, M->obs[p].map, rp[hi], &o2)) return 0;
            if (o1 != o2) return 1; }
        return 0;
    }
    if (!strcmp(f->obl, "Stability")) {
        for (int a = 0; a < M->nact; a++) {
            uint64_t y; if (cmap(S, M->act[a].map, x, &y)) return 0;
            for (size_t k = 2; k < bp->n; k++) {
                const Sx *sc = bp->items[k];
                if (!sx_head_is(sc, "Successor") || sc->n != 4 || strcmp(sc->items[1]->text, M->act[a].name) || strcmp(sc->items[2]->text, bl[hi]->items[1]->text)) continue;
                for (int j = 0; j < nb; j++) if (!strcmp(bl[j]->items[1]->text, sc->items[3]->text)) { int r = cblock(bl[j], y, W); if (r == 0) return 1; }
            }
        }
        return 0;
    }
    return 0;
}

/* ---- part 6b: checked proofs (CNF -> CaDiCaL LRAT -> cake_lpr), bound to the CNF sha256 ---- */
static const char *penv(const char *k) { const char *v = getenv(k); return v && *v ? v : NULL; }
static int file_sha(const char *path, char *dg) {
    FILE *f = fopen(path, "rb"); if (!f) return -1;
    fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
    char *b = malloc(n > 0 ? (size_t)n : 1); if (!b) { fclose(f); return -1; }
    size_t got = fread(b, 1, (size_t)n, f); fclose(f);
    if (got != (size_t)n) { free(b); return -1; }
    dc_sha256_hex(b, got, dg); free(b); return 0;
}
static int sym_run(char *const argv[], const char *out) {
    pid_t p = fork();
    if (p < 0) return -1;
    if (p == 0) {
        int fd = open(out ? out : "/dev/null", O_WRONLY | O_CREAT | O_TRUNC, 0600);
        if (fd >= 0) { dup2(fd, 1); dup2(fd, 2); close(fd); }
        execv(argv[0], argv); _exit(127);
    }
    int st; if (waitpid(p, &st, 0) < 0) return -1;
    return WIFEXITED(st) ? WEXITSTATUS(st) : -1;
}
/* Asserts goal (the negated obligation) and asks for a checked refutation.
 * 1: UNSAT, proof replayed by cake_lpr on the hashed CNF; 0: solver says SAT;
 * -1: no backend or a pipeline failure (why).  dg receives the CNF sha256. */
static int sym_prove(Cnf *c, int goal, char *dg, char *why, size_t ws) {
    const char *cad = penv("DCALC_CADICAL"), *cake = penv("DCALC_CAKE_LPR"), *dir = penv("DCALC_PROOF_DIR");
    dg[0] = 0;
    if (!cad || !cake) { snprintf(why, ws, "no proof backend configured (DCALC_CADICAL, DCALC_CAKE_LPR)"); return -1; }
    cnf_add(c, goal, 0, 0);
    if (c->bad) { snprintf(why, ws, "out of memory building the CNF"); return -1; }
    char d[512], cf[600], lf[600], of[600];
    snprintf(d, sizeof d, "%s/dcalc-proof-XXXXXX", dir ? dir : "/tmp");
    if (!mkdtemp(d)) { snprintf(why, ws, "cannot create a proof directory"); return -1; }
    snprintf(cf, sizeof cf, "%s/ob.cnf", d); snprintf(lf, sizeof lf, "%s/ob.lrat", d); snprintf(of, sizeof of, "%s/check.out", d);
    int rc = -1; FILE *f = fopen(cf, "w");
    if (!f) { snprintf(why, ws, "cannot write the CNF"); goto done; }
    fprintf(f, "p cnf %d %zu\n", c->nv, c->ncl);
    for (size_t i = 0; i < c->n; i++) { if (c->cl[i]) fprintf(f, "%d ", c->cl[i]); else fputs("0\n", f); }
    if (fclose(f) || file_sha(cf, dg)) { snprintf(why, ws, "cannot write the CNF"); goto done; }
    {
        char *av[] = { (char *)cad, "-q", "--no-binary", "--lrat", cf, lf, NULL };
        int r = sym_run(av, NULL);
        if (r == 10) { rc = 0; snprintf(why, ws, "solver found the obligation satisfiable"); goto done; }
        if (r != 20) { snprintf(why, ws, "solver exit %d", r); goto done; }
    }
    {
        char *av[] = { (char *)cake, cf, lf, NULL };
        int r = sym_run(av, of); char buf[4096] = {0}, dg2[65];
        FILE *o = fopen(of, "rb"); if (o) { size_t k = fread(buf, 1, sizeof buf - 1, o); buf[k] = 0; fclose(o); }
        if (r != 0 || !strstr(buf, "s VERIFIED UNSAT")) { snprintf(why, ws, "cake_lpr did not verify the proof (exit %d)", r); goto done; }
        if (file_sha(cf, dg2) || strcmp(dg, dg2)) { snprintf(why, ws, "CNF changed during checking"); goto done; }
        rc = 1;
    }
done:
    if (!penv("DCALC_PROOF_KEEP")) { unlink(cf); unlink(lf); unlink(of); rmdir(d); }
    return rc;
}

static int cnf_map(Cnf *c, const SymMod *S, int mi, const int *vec, CVal *o) {
    const SMap *mp = &S->map[mi]; CCtx x = { c, mp->var->text, vec, S->car[mp->from].width };
    if (cnf_term(&x, mp->body, o)) return -1;
    cwiden(&x, o, S->car[mp->to].width);
    return o->w == S->car[mp->to].width ? 0 : -1;
}
static int cnf_block(Cnf *c, const Sx *b, const int *vec, int W, int *lit) {
    const Sx *bd = b->items[2]; CCtx x = { c, bd->items[1]->items[0]->text, vec, W }; CVal v;
    if (cnf_term(&x, bd->items[2], &v) || cbool(&x, &v)) return -1;
    *lit = v.b[0]; return 0;
}
/* goal = C(x) and (some universal obligation fails at x).  Membership is concrete. */
static int sym_cnf_partition(Cnf *c, const SymMod *S, const SMach *M, const Sx *bp, const RNode *nd, int nn,
                             int sel, int *nobl, const char **oname, int *goal) {   /* sel < 0: all obligations */
    int W = S->car[M->states].width, xv[SYM_MAXW], nb = 0, Bl[SYM_MAXB]; const Sx *bl[SYM_MAXB]; uint64_t rp[SYM_MAXB];
    for (int i = 0; i < W; i++) xv[i] = i + 1;
    if (cnf_init(c, W)) return -1;
    int T = c->tru, C = T, viol = -T, U = -T;
    int oi = 0; const char *on = "All";
#define OBL(name, t) do { int t_ = (t); if (sel < 0 || sel == oi) { viol = cnf_or(c, viol, t_); if (sel >= 0) on = (name); } oi++; } while (0)
    if (nd) { C = -T; for (int k = 0; k < nn; k++) { int e = T; for (int i = 0; i < W; i++) e = cnf_and(c, e, ((nd[k].w >> i) & 1) ? xv[i] : -xv[i]); C = cnf_or(c, C, e); } }
    for (size_t k = 2; k < bp->n; k++) {
        const Sx *b = bp->items[k];
        if (!sx_head_is(b, "Block")) continue;
        if (nb == SYM_MAXB || !lit_of(b->items[3], &rp[nb]) || cnf_block(c, b, xv, W, &Bl[nb])) return -1;
        bl[nb++] = b;
    }
    for (int i = 0; i < nb; i++) U = cnf_or(c, U, Bl[i]);
    OBL("Coverage", -U);
    for (int i = 0; i < nb; i++) for (int j = i + 1; j < nb; j++) OBL("Disjointness", cnf_and(c, Bl[i], Bl[j]));
    for (int p = 0; p < M->nobs; p++) {
        CVal ob; if (cnf_map(c, S, M->obs[p].map, xv, &ob)) return -1;
        for (int i = 0; i < nb; i++) {
            uint64_t t; if (cmap(S, M->obs[p].map, rp[i], &t)) return -1;
            int diff = -T; for (int k = 0; k < ob.w; k++) diff = cnf_or(c, diff, ((t >> k) & 1) ? -ob.b[k] : ob.b[k]);
            OBL("Constancy", cnf_and(c, Bl[i], diff));
        }
    }
    for (int a = 0; a < M->nact; a++) {
        CVal y; if (cnf_map(c, S, M->act[a].map, xv, &y)) return -1;
        for (size_t k = 2; k < bp->n; k++) {
            const Sx *sc = bp->items[k]; int i = -1, j = -1, by;
            if (!sx_head_is(sc, "Successor") || sc->n != 4 || strcmp(sc->items[1]->text, M->act[a].name)) continue;
            for (int t = 0; t < nb; t++) { if (!strcmp(bl[t]->items[1]->text, sc->items[2]->text)) i = t; if (!strcmp(bl[t]->items[1]->text, sc->items[3]->text)) j = t; }
            if (i < 0 || j < 0 || cnf_block(c, bl[j], y.b, W, &by)) return -1;
            OBL("Stability", cnf_and(c, Bl[i], -by));
        }
    }
#undef OBL
    *nobl = oi; *oname = on;
    *goal = cnf_and(c, C, viol);
    return c->bad ? -1 : 0;
}

/* A decision-diagram answer alone is a candidate (spec 6.2): until its obligations
 * are replayed by a checked proof it is Conditional on the trusted backend. */
static void sym_set_conditional(Sx *res, const char *digest) {
    Sx *st = sx_find(res, "Status", 1);
    if (st && st->n == 2) { sx_free(st->items[1]); st->items[1] = dc_sym("Conditional"); }
    Sx *as = sx_find(res, "Assumptions", 1);
    if (as) sx_push(as, dc_form("TrustedBackend", dc_sym("dcalc-bdd"), dc_sym("m3"), dc_sym("BDD"), sx_str(digest), NULL));
    Sx *au = sx_find(res, "Assurance", 1);
    Sx *g = au ? sx_find(au, "Ground", 1) : NULL, *rp = au ? sx_find(au, "Replayed", 1) : NULL;
    if (g && g->n == 2) { sx_free(g->items[1]); g->items[1] = dc_sym("Exact"); }
    if (rp && rp->n == 2) { sx_free(rp->items[1]); rp->items[1] = dc_sym("False"); }
}
static Sx *sym_reach_words(const RNode *nd, int nn, const SMach *R) {
    Sx *l = dc_form("Words", NULL);
    for (int k = 0; k < nn; k++) {
        int path[64], np = 0;
        for (int x = k; nd[x].parent >= 0 && np < 64; x = nd[x].parent) path[np++] = nd[x].act;
        Sx *pa = dc_form("Path", NULL);
        for (int t = np - 1; t >= 0; t--) sx_push(pa, dc_sym(R->act[path[t]].name));
        char wb[32]; snprintf(wb, sizeof wb, "%llu", (unsigned long long)nd[k].w);
        sx_push(l, dc_form("Word", dc_sym(wb), pa, NULL));
    }
    return l;
}

static Sx *sym_req_partition(DcModule *m, const SymMod *S, const Sx *q) {
    char err[256]; const char *pn, *mn, *cn; const Sx *of = q->n == 3 ? q->items[2] : NULL;
    if (sname(q, 1, &pn) || !of || !sx_head_is(of, "Of") || sname(of, 1, &mn))
        return dc_invalid(m, "CheckBlockPartition: expected (CheckBlockPartition Partition (Of Machine))");
    const Sx *bp = sfind_decl(S, pn); int mi = sfind_mach(S, mn), ci;
    if (!bp || !sx_head_is(bp, "BlockPartition")) return dc_invalid(m, "CheckBlockPartition: %s names no BlockPartition", pn);
    if (mi < 0) return dc_invalid(m, "CheckBlockPartition: %s names no machine", mn);
    const SMach *M = &S->mach[mi];
    if (sname(sfield(bp, "On"), 1, &cn) || (ci = sfind_car(S, cn)) < 0) return dc_invalid(m, "BlockPartition %s: (On carrier) missing", pn);
    if (S->car[ci].width != S->car[M->states].width) return dc_invalid(m, "BlockPartition %s: carrier width differs from machine states", pn);
    SymEnv E; if (senv_init(&E, S->car[ci].width)) return dc_unsupported(m, "CheckBlockPartition: out of memory");
    SymVal av[8]; DcBdd C = 1; int nn = 0, rc; SymFail f; RNode *nd = NULL; const SMach *R = NULL;
    if (mach_acts(&E, S, M, av, err, sizeof err)) { dc_bdd_free(E.bm); return dc_invalid(m, "CheckBlockPartition: %s", err); }
    if (S->car[ci].reach) {
        const Sx *rf = S->car[ci].reach; int ri = sfind_mach(S, rf->items[1]->text); uint64_t st; SymVal rav[8];
        if (ri < 0 || !lit_of(rf->items[2]->items[1], &st)) { dc_bdd_free(E.bm); return dc_invalid(m, "carrier %s: bad (Reach Machine (From word))", cn); }
        R = &S->mach[ri];
        if (mach_acts(&E, S, R, rav, err, sizeof err) || (rc = sym_reach(&E, rav, R->nact, st, &nd, &nn, err, sizeof err))) {
            dc_bdd_free(E.bm); return dc_unsupported(m, "CheckBlockPartition: reach scope %s: %s", cn, err);
        }
        C = 0; for (int k = 0; k < nn; k++) C = dc_bdd_or(E.bm, C, word_bdd(&E, nd[k].w));
    }
    rc = sym_check_partition(&E, S, M, av, bp, C, &f, err, sizeof err);
    size_t nodes = dc_bdd_nodes(E.bm); dc_bdd_free(E.bm);
    sym_res_words = nn + (rc == 0); sym_res_nodes = nodes;
    for (size_t k = 2; k < bp->n; k++) if (sx_head_is(bp->items[k], "Block")) sym_res_words++;
    if (rc < 0) { free(nd); return rc == -1 ? dc_invalid(m, "CheckBlockPartition: %s", err) : dc_unsupported(m, "CheckBlockPartition: BDD node limit reached"); }
    /* obligation digest: partition text, machine, scope words */
    char *bt = sx_print(bp); size_t cap = strlen(bt) + 128 + (size_t)nn * 24, len; char *buf = malloc(cap), dg[65];
    len = (size_t)snprintf(buf, cap, "%s|%s|%s", bt, mn, nd ? "reach" : "all");
    for (int k = 0; k < nn; k++) len += (size_t)snprintf(buf + len, cap - len, ",%llu", (unsigned long long)nd[k].w);
    dc_sha256_hex(buf, len, dg); free(buf); free(bt);
    DcScope sc = { "M3-SymbolicBitVector", -1, "", NULL };
    Sx *claim = dc_form("Claim", sx_copy(q), NULL);
    Sx *subj = dc_form("Subject", dc_form("BlockPartition", dc_sym(pn), NULL), dc_form("Machine", dc_sym(mn), NULL), NULL);
    char nb[32]; snprintf(nb, sizeof nb, "%zu", nodes);
    Sx *res;
    if (rc == 0) {
        char wb[32]; snprintf(wb, sizeof wb, "%llu", (unsigned long long)f.wit);
        Sx *val = dc_form("Value", dc_form("Refuted", dc_form("Obligation", dc_sym(f.obl), NULL), dc_form("Witness", dc_sym(wb), NULL), NULL), NULL);
        Sx *ev = dc_form("Evidence", dc_form("Witness", dc_form("Word", dc_sym(wb), NULL), dc_form("Obligation", dc_sym(f.obl), NULL), dc_form("Detail", sx_str(f.what), NULL), NULL), NULL);
        int rep_ok = sym_replay(S, M, bp, nd, nn, &f);   /* concrete evaluator, no BDDs */
        res = dc_envelope_scoped(m, VERDICT_FAILS, rep_ok, claim, subj, val, ev, rep_ok ? NULL : "witness did not replay on the concrete evaluator", &sc);
    } else {
        Sx *val = dc_form("Value", dc_form("Partition", dc_sym(pn), NULL), NULL);
        if (nd) sx_push(val, dc_form("ReachScope", dc_sym(cn), sym_reach_words(nd, nn, R), NULL));
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("SymbolicPartition"), NULL),
                         dc_form("ObligationDigest", sx_str(dg), NULL), dc_form("BddNodes", dc_sym(nb), NULL), NULL), NULL);
        {   /* symbolic-partition certificate fields (Table 1): block predicates + representatives, successor map, invariant, reach words */
            Sx *cert = ev->items[1], *blocks = dc_form("Blocks", NULL), *succ = dc_form("SuccessorMap", NULL);
            for (size_t k = 2; k < bp->n; k++) {
                if (sx_head_is(bp->items[k], "Block")) sx_push(blocks, sx_copy(bp->items[k]));
                else if (sx_head_is(bp->items[k], "Successor")) sx_push(succ, sx_copy(bp->items[k]));
            }
            sx_push(cert, blocks); sx_push(cert, succ);
            if (nd) {
                Sx *inv = dc_form("Invariant", dc_form("Words", NULL), NULL);
                for (int k = 0; k < nn; k++) { char wb[32]; snprintf(wb, sizeof wb, "%llu", (unsigned long long)nd[k].w); sx_push(inv->items[1], dc_sym(wb)); }
                sx_push(cert, inv); sx_push(cert, dc_form("ReachWords", sym_reach_words(nd, nn, R), NULL));
            }
        }
        /* one checked proof per obligation (cert format: symbolic partition) */
        Cnf cn; int goal, pr = 1, nob = 1; char pdg[65] = "", why[160] = "proof not attempted"; Sx *proofs = dc_form("Proofs", NULL);
        for (int ob = 0; ob < nob && pr == 1; ob++) {
            const char *on = "?"; int r1;
            memset(&cn, 0, sizeof cn);
            if (sym_cnf_partition(&cn, S, M, bp, nd, nn, ob, &nob, &on, &goal) != 0) { pr = -1; snprintf(why, sizeof why, "CNF generation failed"); }
            else if ((r1 = sym_prove(&cn, goal, pdg, why, sizeof why)) != 1) pr = r1;
            else sx_push(proofs, dc_form("Proof", dc_form("Obligation", dc_sym(on), dc_int(ob), NULL), dc_form("CnfSha256", sx_str(pdg), NULL), NULL));
            cnf_free(&cn);
        }
        if (pr != 1) { sx_free(proofs); proofs = NULL; }
        if (pr == 0) { sx_free(val); sx_free(ev); sx_free(claim); sx_free(subj); free(nd);
            return dc_unsupported(m, "CheckBlockPartition: decision diagrams and SAT solver disagree (%s)", why); }
        if (pr == 1) {
            sx_push(ev->items[1], dc_form("Proof", dc_form("Solver", dc_sym("cadical-3.0.1"), NULL), dc_form("Format", dc_sym("LRAT"), NULL),
                                          dc_form("Checker", dc_sym("cake_lpr-033aad5"), NULL), proofs, dc_form("Generator", dc_sym("dcalc-symgen"), dc_sym(SYM_GEN_VERSION), NULL), NULL));
            res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, claim, subj, val, ev, NULL, &sc);
        } else {
            char rs[256]; snprintf(rs, sizeof rs, "decision-diagram answer; obligations not yet replayed by a checked proof (%s)", why);
            res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, claim, subj, val, ev, rs, &sc);
            sym_set_conditional(res, dg);
        }
    }
    free(nd);
    return res;
}

/* ---- part 4: MinimizeForQueries on a symbolic machine ----
 * Classes are the fibers of a list of tests (word, port, bit), each a BDD.  Tests start
 * from the observation bits; for every kept test t and action a the test t.a (apply a,
 * then t) is tried; a test is kept only when it splits a class.  When no t.a splits,
 * every t.a is constant on the classes, so the partition is stable (and coarsest:
 * every split is forced by a test).  The kept tests form the splitting tree. */
#define SYM_MAXCL 256
#define SYM_MAXT 64
#define SYM_MAXWD 8
typedef struct { int nw, word[SYM_MAXWD], port, bit; DcBdd f; } STest;

static int sym_split(DcBddMgr *bm, DcBdd *cl, int *ncl, DcBdd f) {   /* 1 split, 0 none, -1 overflow */
    int n0 = *ncl, did = 0;
    for (int i = 0; i < n0; i++) {
        DcBdd a = dc_bdd_and(bm, cl[i], f), b = dc_bdd_and(bm, cl[i], dc_bdd_not(bm, f));
        if (a && b) { if (*ncl == SYM_MAXCL) return -1; cl[i] = a; cl[(*ncl)++] = b; did = 1; }
    }
    return did;
}

static int sym_refine(DcBddMgr *bm, const SymMod *S, const SMach *M, const SymVal *av, SymVal *ob, const DcBdd *xv,
                      STest *T, int *ntp, DcBdd *cl, int *nclp, char *err, size_t es) {   /* 0 ok, -1 overflow, -2 invalid */
    int nt = 0, ncl = 1, rc = 0; cl[0] = 1;
    for (int p = 0; p < M->nobs && !rc; p++) {
        if (sym_apply(bm, S, M->obs[p].map, xv, &ob[p], err, es)) return -2;
        for (int k = 0; k < ob[p].w && !rc; k++) {
            int sp = sym_split(bm, cl, &ncl, ob[p].b[k]);
            if (sp < 0 || (sp && nt == SYM_MAXT)) rc = -1;
            else if (sp) T[nt++] = (STest){ 0, {0}, p, k, ob[p].b[k] };
        }
    }
    for (int i = 0; i < nt && !rc; i++)
        for (int a = 0; a < M->nact && !rc; a++) {
            DcBdd f = dc_bdd_compose(bm, T[i].f, av[a].b);
            int sp = sym_split(bm, cl, &ncl, f);
            if (sp < 0 || (sp && (nt == SYM_MAXT || T[i].nw == SYM_MAXWD))) { rc = -1; break; }
            if (!sp) continue;
            STest t = T[i]; t.f = f; t.word[0] = a; memcpy(t.word + 1, T[i].word, (size_t)T[i].nw * sizeof(int)); t.nw = T[i].nw + 1;
            T[nt++] = t;
        }
    *ntp = nt; *nclp = ncl; return rc;
}

/* Proof obligation for a symbolic refinement, on two copies x, y of the word:
 * same value on every kept test  =>  same observation bits and same value of t.a for
 * every test t and action a.  UNSAT means the test fibers form a congruence that refines
 * the observations (stability); distinct test vectors on the representatives (checked
 * concretely) show every class split is forced by a test (coarseness). */
static int cnf_test(Cnf *c, const SymMod *S, const SMach *M, int pre, const STest *t, const int *vec, int *lit) {
    int W = S->car[M->states].width, cur[SYM_MAXW]; CVal y;
    memcpy(cur, vec, (size_t)W * sizeof(int));
    if (pre >= 0) { if (cnf_map(c, S, M->act[pre].map, cur, &y)) return -1; memcpy(cur, y.b, (size_t)W * sizeof(int)); }
    for (int k = 0; k < t->nw; k++) { if (cnf_map(c, S, M->act[t->word[k]].map, cur, &y)) return -1; memcpy(cur, y.b, (size_t)W * sizeof(int)); }
    if (cnf_map(c, S, M->obs[t->port].map, cur, &y) || t->bit >= y.w) return -1;
    *lit = y.b[t->bit]; return 0;
}
static int sym_cnf_minimize(Cnf *c, const SymMod *S, const SMach *M, const STest *T, int nt, int *goal) {
    int W = S->car[M->states].width, xv[SYM_MAXW], yv[SYM_MAXW], lx, ly;
    if (cnf_init(c, 2 * W)) return -1;
    for (int i = 0; i < W; i++) { xv[i] = i + 1; yv[i] = W + i + 1; }
    int Tr = c->tru, same = Tr, viol = -Tr;
    for (int i = 0; i < nt; i++) {
        if (cnf_test(c, S, M, -1, &T[i], xv, &lx) || cnf_test(c, S, M, -1, &T[i], yv, &ly)) return -1;
        same = cnf_and(c, same, -cnf_xor(c, lx, ly));
    }
    for (int p = 0; p < M->nobs; p++) {
        CVal ox, oy; if (cnf_map(c, S, M->obs[p].map, xv, &ox) || cnf_map(c, S, M->obs[p].map, yv, &oy)) return -1;
        for (int k = 0; k < ox.w; k++) viol = cnf_or(c, viol, cnf_xor(c, ox.b[k], oy.b[k]));
    }
    for (int i = 0; i < nt; i++) for (int a = 0; a < M->nact; a++) {
        if (cnf_test(c, S, M, a, &T[i], xv, &lx) || cnf_test(c, S, M, a, &T[i], yv, &ly)) return -1;
        viol = cnf_or(c, viol, cnf_xor(c, lx, ly));
    }
    *goal = cnf_and(c, same, viol);
    return c->bad ? -1 : 0;
}
/* concrete: the representatives have pairwise distinct test vectors */
static int sym_reps_distinct(const SymMod *S, const SMach *M, const STest *T, int nt, const uint64_t *rep, int ncl) {
    static uint64_t vec[SYM_MAXCL];
    for (int i = 0; i < ncl; i++) {
        vec[i] = 0;
        for (int t = 0; t < nt; t++) {
            uint64_t x = rep[i], o;
            for (int k = 0; k < T[t].nw; k++) if (cmap(S, M->act[T[t].word[k]].map, x, &x)) return 0;
            if (cmap(S, M->obs[T[t].port].map, x, &o)) return 0;
            if ((o >> T[t].bit) & 1) vec[i] |= (uint64_t)1 << t;
        }
        for (int j = 0; j < i; j++) if (vec[j] == vec[i]) return 0;
    }
    return 1;
}

/* Splitting tree (Def 4.11) over the kept tests: each internal node is the first test that
 * splits its classes (values computed concretely on the representatives); leaves are the
 * classes with their concrete representatives. */
static int sym_test_vec(const SymMod *S, const SMach *M, const STest *T, int nt, const uint64_t *rep, int ncl, uint64_t *vec) {
    for (int i = 0; i < ncl; i++) {
        vec[i] = 0;
        for (int t = 0; t < nt; t++) {
            uint64_t x = rep[i], o;
            for (int k = 0; k < T[t].nw; k++) if (cmap(S, M->act[T[t].word[k]].map, x, &x)) return -1;
            if (cmap(S, M->obs[T[t].port].map, x, &o)) return -1;
            if ((o >> T[t].bit) & 1) vec[i] |= (uint64_t)1 << t;
        }
    }
    return 0;
}
static Sx *sym_tree(const SMach *M, const STest *T, int nt, const uint64_t *vec, const uint64_t *rep, const int *ids, int n, int *nodes, int *maxw) {
    char b[32];
    if (n == 1) { snprintf(b, sizeof b, "%llu", (unsigned long long)rep[ids[0]]); return dc_form("Leaf", dc_form("Rep", dc_sym(b), NULL), NULL); }
    for (int t = 0; t < nt; t++) {
        int z[SYM_MAXCL], o[SYM_MAXCL], nz = 0, no = 0;
        for (int k = 0; k < n; k++) { if ((vec[ids[k]] >> t) & 1) o[no++] = ids[k]; else z[nz++] = ids[k]; }
        if (!nz || !no) continue;
        Sx *l = sym_tree(M, T, nt, vec, rep, z, nz, nodes, maxw), *r = l ? sym_tree(M, T, nt, vec, rep, o, no, nodes, maxw) : NULL;
        if (!l || !r) { sx_free(l); return NULL; }
        Sx *w = dc_form("Word", NULL); for (int k = 0; k < T[t].nw; k++) sx_push(w, dc_sym(M->act[T[t].word[k]].name));
        if (T[t].nw > *maxw) *maxw = T[t].nw;
        snprintf(b, sizeof b, "%d", T[t].bit); (*nodes)++;
        return dc_form("Split", w, dc_form("Observe", dc_sym(M->obs[T[t].port].name), dc_sym(b), NULL),
                       dc_form("Zero", l, NULL), dc_form("One", r, NULL), NULL);
    }
    return NULL;   /* classes not separated by the tests */
}

/* ---- linear backend over F2 (spec 6.2: ParityQuotient) ----
 * A syntactic compiler turns Body terms into F2 matrices (row j = mask of the input bits
 * whose XOR is output bit j); any non-linear operator or constant offset rejects the map.
 * The observable space is the closure of the observation rows under r -> r.A_a; its
 * dimension k gives 2^k classes and W-k unobservable dimensions.  Stability is the matrix
 * identity B_j.A_a = sum_l K_a[j][l] B_l, replayed by multiplication. */
typedef struct { int w; uint64_t k; uint64_t row[SYM_MAXW]; unsigned char c[SYM_MAXW]; } LVal;
static void lwiden(LVal *v, int w) {
    if (v->w >= 0) return;
    uint64_t k = v->k; v->w = w;
    for (int i = 0; i < w; i++) { v->row[i] = 0; v->c[i] = (k >> i) & 1; }
}
static int lbool(LVal *v) { if (v->w < 0) { if (v->k > 1) return -1; lwiden(v, 1); } return v->w == 1 ? 0 : -1; }
static int lin_term(const Sx *t, const char *var, int W, LVal *o) {
    LVal a, b; uint64_t i, j;
    memset(o, 0, sizeof *o);
    if (t->kind == SX_SYM) {
        if (!strcmp(t->text, var)) { o->w = W; for (int q = 0; q < W; q++) o->row[q] = (uint64_t)1 << q; return 0; }
        if (lit_of(t, &o->k)) { o->w = -1; return 0; }
        return -1;
    }
    if (t->kind != SX_LIST || !t->n || t->items[0]->kind != SX_SYM) return -1;
    const char *h = t->items[0]->text; size_t n = t->n;
#define LT(k, v) if (lin_term(t->items[k], var, W, &v)) return -1
#define LX(k, v, lim) (lit_of(t->items[k], &v) && v < (uint64_t)(lim))
    if (!strcmp(h, "BitAt") && n == 3) { LT(1, a); if (a.w < 0 || !LX(2, i, a.w)) return -1; o->w = 1; o->row[0] = a.row[i]; o->c[0] = a.c[i]; return 0; }
    if (!strcmp(h, "Slice") && n == 4) { LT(1, a); if (a.w < 0 || !LX(2, i, a.w) || !LX(3, j, a.w) || j < i) return -1;
        o->w = (int)(j - i + 1); for (uint64_t q = i; q <= j; q++) { o->row[q - i] = a.row[q]; o->c[q - i] = a.c[q]; } return 0; }
    if (!strcmp(h, "SwapBits") && n == 4) { LT(1, a); if (a.w < 0 || !LX(2, i, a.w) || !LX(3, j, a.w)) return -1;
        *o = a; o->row[i] = a.row[j]; o->row[j] = a.row[i]; o->c[i] = a.c[j]; o->c[j] = a.c[i]; return 0; }
    if (!strcmp(h, "RotateRange") && n == 4) { LT(1, a); if (a.w < 0 || !LX(2, i, a.w) || !LX(3, j, a.w) || j < i) return -1;
        *o = a; for (uint64_t q = i + 1; q <= j; q++) { o->row[q] = a.row[q - 1]; o->c[q] = a.c[q - 1]; } o->row[i] = a.row[j]; o->c[i] = a.c[j]; return 0; }
    if (!strcmp(h, "SetBit") && n == 4) { LT(1, a); LT(3, b); if (a.w < 0 || !LX(2, i, a.w) || lbool(&b)) return -1;
        *o = a; o->row[i] = b.row[0]; o->c[i] = b.c[0]; return 0; }
    if (!strcmp(h, "Parity") && n == 2) { LT(1, a); if (a.w < 0) return -1;
        o->w = 1; for (int q = 0; q < a.w; q++) { o->row[0] ^= a.row[q]; o->c[0] ^= a.c[q]; } return 0; }
    if (!strcmp(h, "Not") && n == 2) { LT(1, a); if (lbool(&a)) return -1; *o = a; o->c[0] ^= 1; return 0; }
    if (!strcmp(h, "Xor") && n == 3) { LT(1, a); LT(2, b); if (a.w < 0 && b.w < 0) return -1;
        lwiden(&a, b.w); lwiden(&b, a.w); if (a.w != b.w) return -1;
        o->w = a.w; for (int q = 0; q < a.w; q++) { o->row[q] = a.row[q] ^ b.row[q]; o->c[q] = a.c[q] ^ b.c[q]; } return 0; }
#undef LT
#undef LX
    return -1;   /* And, Or, Eq, IsZero, ...: not linear */
}
static int lin_map(const SymMod *S, int mi, LVal *o) {
    const SMap *mp = &S->map[mi];
    if (lin_term(mp->body, mp->var->text, S->car[mp->from].width, o)) return -1;
    lwiden(o, S->car[mp->to].width);
    if (o->w != S->car[mp->to].width) return -1;
    for (int q = 0; q < o->w; q++) if (o->c[q]) return -1;   /* affine offset: outside the linear backend */
    /* cross-check against the concrete evaluator */
    uint64_t x = 0x9E3779B97F4A7C15ULL ^ (uint64_t)mi;
    for (int t = 0; t < 128; t++) {
        uint64_t w = (t < 64 ? ((uint64_t)1 << (t % S->car[mp->from].width)) : (x ^= x << 13, x ^= x >> 7, x ^= x << 17)) & cmask(S->car[mp->from].width), y, z = 0;
        sym_res_xcheck++;
        if (cmap(S, mi, w, &y)) return -1;
        for (int q = 0; q < o->w; q++) if (__builtin_parityll(o->row[q] & w)) z |= (uint64_t)1 << q;
        if (y != z) return -1;
    }
    return 0;
}
static uint64_t lin_comp(uint64_t r, const LVal *f) { uint64_t x = 0; for (int j = 0; j < f->w; j++) if ((r >> j) & 1) x ^= f->row[j]; return x; }
typedef struct { uint64_t B[64], er[64], ec[64]; int piv[64], k; } LBasis;
static uint64_t lin_reduce(const LBasis *L, uint64_t v, uint64_t *comb) {
    *comb = 0;
    while (v) { int p = 63 - __builtin_clzll(v), e = L->piv[p]; if (e < 0) break; v ^= L->er[e]; *comb ^= L->ec[e]; }
    return v;
}
static void lin_add(LBasis *L, uint64_t v) {
    uint64_t c, r = lin_reduce(L, v, &c);
    if (!r || L->k == 64) return;
    int e = L->k; L->B[e] = v; L->er[e] = r; L->ec[e] = c ^ ((uint64_t)1 << e); L->piv[63 - __builtin_clzll(r)] = e; L->k++;
}
/* NULL when the machine is not linear; *ok = identities replayed and 2^k == ncl. */
static Sx *sym_linear(const SymMod *S, const SMach *M, int ncl, int *ok) {
    static LVal act[8], obs[8]; static LBasis L; int W = S->car[M->states].width; char hb[32];
    *ok = 0;
    for (int a = 0; a < M->nact; a++) if (lin_map(S, M->act[a].map, &act[a])) return NULL;
    for (int p = 0; p < M->nobs; p++) if (lin_map(S, M->obs[p].map, &obs[p])) return NULL;
    memset(&L, 0, sizeof L); for (int i = 0; i < 64; i++) L.piv[i] = -1;
    for (int p = 0; p < M->nobs; p++) for (int q = 0; q < obs[p].w; q++) lin_add(&L, obs[p].row[q]);
    for (int i = 0; i < L.k; i++) for (int a = 0; a < M->nact; a++) lin_add(&L, lin_comp(L.B[i], &act[a]));
    int rep = 1; Sx *basis = dc_form("Basis", NULL), *trans = dc_form("Transitions", NULL);
    for (int i = 0; i < L.k; i++) { snprintf(hb, sizeof hb, "%llx", (unsigned long long)L.B[i]); sx_push(basis, dc_form("Row", sx_str(hb), NULL)); }
    for (int a = 0; a < M->nact; a++) {
        Sx *K = dc_form("K", NULL);
        for (int j = 0; j < L.k; j++) {
            uint64_t v = lin_comp(L.B[j], &act[a]), c, x = 0;
            if (lin_reduce(&L, v, &c)) rep = 0;
            for (int l = 0; l < L.k; l++) if ((c >> l) & 1) x ^= L.B[l];   /* replay by multiplication */
            if (x != v) rep = 0;
            snprintf(hb, sizeof hb, "%llx", (unsigned long long)c); sx_push(K, sx_str(hb));
        }
        sx_push(trans, dc_form("Action", dc_sym(M->act[a].name), K, NULL));
    }
    if (L.k > 30 || ((long)1 << L.k) != ncl) rep = 0;
    *ok = rep;
    return dc_form("Linear", dc_form("Field", dc_sym("F2"), NULL), dc_form("ObservableDimension", dc_int(L.k), NULL),
                   dc_form("UnobservableDimension", dc_int(W - L.k), NULL), basis, trans,
                   dc_form("Replayed", dc_sym(rep ? "True" : "False"), NULL), NULL);
}

/* ---- syntactic cone-of-influence pass ----
 * Each Body term is read as per-output-bit masks of the input bits it mentions (no
 * evaluation).  The cone is the least set containing the bits read by the observations
 * and closed under: bit j kept and action a  =>  every bit that a's output bit j reads. */
typedef struct { int w; uint64_t m[SYM_MAXW]; } MVal;
static int sup_term(const Sx *t, const char *var, int W, MVal *o) {
    MVal a, b; uint64_t i, j, k;
    memset(o, 0, sizeof *o);
    if (t->kind == SX_SYM) {
        if (!strcmp(t->text, var)) { o->w = W; for (int q = 0; q < W; q++) o->m[q] = (uint64_t)1 << q; return 0; }
        if (lit_of(t, &k)) { o->w = -1; return 0; }
        return -1;
    }
    if (t->kind != SX_LIST || !t->n || t->items[0]->kind != SX_SYM) return -1;
    const char *h = t->items[0]->text; size_t n = t->n;
#define ST(q, v) if (sup_term(t->items[q], var, W, &v)) return -1
#define SX_(q, v, lim) (lit_of(t->items[q], &v) && v < (uint64_t)(lim))
    if (!strcmp(h, "BitAt") && n == 3) { ST(1, a); if (a.w < 0 || !SX_(2, i, a.w)) return -1; o->w = 1; o->m[0] = a.m[i]; return 0; }
    if (!strcmp(h, "Slice") && n == 4) { ST(1, a); if (a.w < 0 || !SX_(2, i, a.w) || !SX_(3, j, a.w) || j < i) return -1;
        o->w = (int)(j - i + 1); for (uint64_t q = i; q <= j; q++) o->m[q - i] = a.m[q]; return 0; }
    if (!strcmp(h, "SwapBits") && n == 4) { ST(1, a); if (a.w < 0 || !SX_(2, i, a.w) || !SX_(3, j, a.w)) return -1;
        *o = a; o->m[i] = a.m[j]; o->m[j] = a.m[i]; return 0; }
    if (!strcmp(h, "RotateRange") && n == 4) { ST(1, a); if (a.w < 0 || !SX_(2, i, a.w) || !SX_(3, j, a.w) || j < i) return -1;
        *o = a; for (uint64_t q = i + 1; q <= j; q++) o->m[q] = a.m[q - 1]; o->m[i] = a.m[j]; return 0; }
    if (!strcmp(h, "SetBit") && n == 4) { ST(1, a); ST(3, b); if (a.w < 0 || !SX_(2, i, a.w)) return -1;
        *o = a; o->m[i] = b.w < 0 ? 0 : b.m[0]; return 0; }
    if ((!strcmp(h, "Parity") || !strcmp(h, "IsZero") || !strcmp(h, "Not")) && n == 2) { ST(1, a);
        o->w = 1; for (int q = 0; q < a.w; q++) o->m[0] |= a.m[q]; return 0; }
    if ((!strcmp(h, "And") || !strcmp(h, "Or") || !strcmp(h, "Xor")) && n == 3) { ST(1, a); ST(2, b);
        int w = a.w >= 0 ? a.w : b.w; if (w < 0) { o->w = -1; return 0; }
        o->w = w; for (int q = 0; q < w; q++) o->m[q] = (a.w >= 0 ? a.m[q] : 0) | (b.w >= 0 ? b.m[q] : 0); return 0; }
    if (!strcmp(h, "Eq") && n == 3) { ST(1, a); ST(2, b);
        o->w = 1; for (int q = 0; q < a.w; q++) o->m[0] |= a.m[q]; for (int q = 0; q < b.w; q++) o->m[0] |= b.m[q]; return 0; }
#undef ST
#undef SX_
    return -1;
}
static int sup_map(const SymMod *S, int mi, MVal *o) {
    const SMap *mp = &S->map[mi];
    if (sup_term(mp->body, mp->var->text, S->car[mp->from].width, o)) return -1;
    if (o->w < 0) { o->w = S->car[mp->to].width; for (int q = 0; q < o->w; q++) o->m[q] = 0; }
    return o->w == S->car[mp->to].width ? 0 : -1;
}
static Sx *sym_cone(const SymMod *S, const SMach *M) {
    static MVal act[8]; MVal ob; uint64_t cone = 0, prev; int W = S->car[M->states].width;
    for (int p = 0; p < M->nobs; p++) { if (sup_map(S, M->obs[p].map, &ob)) return NULL; for (int q = 0; q < ob.w; q++) cone |= ob.m[q]; }
    for (int a = 0; a < M->nact; a++) if (sup_map(S, M->act[a].map, &act[a])) return NULL;
    do { prev = cone;
        for (int a = 0; a < M->nact; a++) for (int j = 0; j < W; j++) if ((cone >> j) & 1) cone |= act[a].m[j];
    } while (cone != prev);
    Sx *bits = dc_form("Dropped", NULL); int kept = 0;
    for (int j = 0; j < W; j++) { if ((cone >> j) & 1) kept++; else sx_push(bits, dc_int(j)); }
    return dc_form("Cone", dc_form("Pass", dc_sym("Syntactic"), NULL), dc_form("Kept", dc_int(kept), NULL), dc_form("Width", dc_int(W), NULL), bits, NULL);
}

static Sx *sym_req_minimize(DcRun *r, const SymMod *S, const Sx *q, int slot) {
    DcModule *m = r->m; const char *h = "MinimizeForQueries", *mn; char err[256];
    if (sname(q, 1, &mn)) return dc_invalid(m, "%s: field machine missing or not a name", h);
    if (q->n > 2) return dc_unsupported(m, "%s: Under/Budget fields are outside the M3 symbolic engine", h);
    int mi = sfind_mach(S, mn);
    if (mi < 0) return dc_invalid(m, "%s: %s names no machine", h, mn);
    const SMach *M = &S->mach[mi];
    if (S->car[M->states].reach) return dc_unsupported(m, "%s: a machine on a reach carrier is outside this step of M3", h);
    SymEnv E; if (senv_init(&E, S->car[M->states].width)) return dc_unsupported(m, "%s: out of memory", h);
    DcBddMgr *bm = E.bm; SymVal av[8], ob[8];
    static STest T[SYM_MAXT]; DcBdd cl[SYM_MAXCL]; int nt = 0, ncl = 1, rc = 0; cl[0] = 1;
    if (mach_acts(&E, S, M, av, err, sizeof err)) { dc_bdd_free(bm); return dc_invalid(m, "%s: %s", h, err); }
    rc = sym_refine(bm, S, M, av, ob, E.xv, T, &nt, cl, &ncl, err, sizeof err);
    if (rc == -2) { dc_bdd_free(bm); return dc_invalid(m, "%s: %s", h, err); }
    if (rc || dc_bdd_failed(bm)) { dc_bdd_free(bm); return dc_unsupported(m, "%s: more than %d classes, %d tests or BDD limit", h, SYM_MAXCL, SYM_MAXT); }
    /* independent self-check: observation bits constant and every action maps a class into one class */
    int ok = 1; uint64_t rep[SYM_MAXCL]; double sz[SYM_MAXCL];
    for (int i = 0; i < ncl; i++) { dc_bdd_min_word(bm, cl[i], &rep[i]); sz[i] = dc_bdd_satcount(bm, cl[i]); }
    for (int i = 0; i < ncl && ok; i++) {
        for (int p = 0; p < M->nobs && ok; p++) for (int k = 0; k < ob[p].w; k++) {
            DcBdd t = dc_bdd_eval(bm, ob[p].b[k], rep[i]) ? dc_bdd_not(bm, ob[p].b[k]) : ob[p].b[k];
            if (dc_bdd_and(bm, cl[i], t)) { ok = 0; break; }
        }
        for (int a = 0; a < M->nact && ok; a++) {
            uint64_t y = sv_eval(&E, &av[a], rep[i]); int d = -1;
            for (int j = 0; j < ncl; j++) if (dc_bdd_eval(bm, cl[j], y)) d = j;
            if (d < 0 || dc_bdd_and(bm, cl[i], dc_bdd_not(bm, dc_bdd_compose(bm, cl[d], av[a].b)))) ok = 0;
        }
    }
    double tot = 0; for (int i = 0; i < ncl; i++) tot += sz[i];
    if (tot != dc_bdd_satcount(bm, 1)) ok = 0;
    size_t nodes = dc_bdd_nodes(bm); dc_bdd_free(bm);
    sym_res_words = ncl; sym_res_nodes = nodes;
    /* blocks in order of their least word */
    int ord[SYM_MAXCL]; for (int i = 0; i < ncl; i++) ord[i] = i;
    for (int i = 1; i < ncl; i++) for (int j = i; j > 0 && rep[ord[j]] < rep[ord[j - 1]]; j--) { int t = ord[j]; ord[j] = ord[j - 1]; ord[j - 1] = t; }
    Sx *part = dc_form("Partition", NULL); char nb[48], dgin[8192]; size_t dl = (size_t)snprintf(dgin, sizeof dgin, "%s|%s|MinimizeForQueries|", m->digest, mn);
    for (int k = 0; k < ncl; k++) {
        int i = ord[k]; char rb[32]; snprintf(rb, sizeof rb, "%llu", (unsigned long long)rep[i]); snprintf(nb, sizeof nb, "%.0f", sz[i]);
        sx_push(part, dc_form("Block", dc_form("Rep", dc_sym(rb), NULL), dc_form("Size", dc_sym(nb), NULL), NULL));
    }
    Sx *tests = dc_form("Tests", NULL);
    for (int i = 0; i < nt; i++) {
        Sx *w = dc_form("Word", NULL); for (int k = 0; k < T[i].nw; k++) sx_push(w, dc_sym(M->act[T[i].word[k]].name));
        snprintf(nb, sizeof nb, "%d", T[i].bit);
        sx_push(tests, dc_form("Test", w, dc_form("Observe", dc_sym(M->obs[T[i].port].name), dc_sym(nb), NULL), NULL));
        char *ts = sx_print(tests->items[tests->n - 1]); dl += (size_t)snprintf(dgin + dl, dl < sizeof dgin ? sizeof dgin - dl : 0, "%s;", ts); free(ts);
        if (dl >= sizeof dgin) dl = sizeof dgin - 1;
    }
    char dg[65]; dc_sha256_hex(dgin, dl, dg);
    snprintf(nb, sizeof nb, "%d", ncl);
    Sx *val = dc_form("Value", dc_form("Refinement", dc_form("Representation", dc_sym(slot >= 0 ? m->der[slot].name : "?"), NULL), part,
                                       dc_form("Classes", dc_sym(nb), NULL), NULL), NULL);
    snprintf(nb, sizeof nb, "%zu", nodes);
    Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("SplittingTree"), NULL), tests,
                     dc_form("ObligationDigest", sx_str(dg), NULL), dc_form("BddNodes", dc_sym(nb), NULL), NULL), NULL);
    DcScope sc = { "M3-SymbolicBitVector", -1, "", NULL };
    Sx *subj = dc_form("Subject", dc_form("Machine", dc_sym(mn), NULL), NULL);
    {   /* splitting tree with concrete representatives */
        static uint64_t vec[SYM_MAXCL]; int nodes_t = 0, maxw = 0; Sx *tree = NULL;
        if (nt <= 63 && !sym_test_vec(S, M, T, nt, rep, ncl, vec)) tree = sym_tree(M, T, nt, vec, rep, ord, ncl, &nodes_t, &maxw);
        if (!tree) ok = 0;
        else {
            Sx *reps = dc_form("Representatives", NULL);
            for (int k = 0; k < ncl; k++) { char rb[32]; snprintf(rb, sizeof rb, "%llu", (unsigned long long)rep[ord[k]]); sx_push(reps, dc_sym(rb)); }
            sx_push(ev->items[1], dc_form("Tree", dc_form("Nodes", dc_int(nodes_t), NULL), dc_form("MaxWord", dc_int(maxw), NULL), tree, NULL));
            sx_push(ev->items[1], reps);
            Sx *cone = sym_cone(S, M); if (cone) sx_push(ev->items[1], cone);
            int lok; Sx *lin = sym_linear(S, M, ncl, &lok);
            if (lin) { sx_push(ev->items[1], lin); if (!lok) ok = 0; }
        }
    }
    if (ok && (nt > 63 || !sym_reps_distinct(S, M, T, nt, rep, ncl))) ok = 0;
    if (!ok) return dc_envelope_scoped(m, VERDICT_HOLDS, 0, dc_claim_of(q, "Literal"), subj, val, ev, "self-check of the refinement failed", &sc);
    Cnf cn; int goal, pr = -1; char pdg[65] = "", why[160] = "proof not attempted";
    memset(&cn, 0, sizeof cn);
    if (sym_cnf_minimize(&cn, S, M, T, nt, &goal) == 0) pr = sym_prove(&cn, goal, pdg, why, sizeof why);
    else snprintf(why, sizeof why, "CNF generation failed");
    cnf_free(&cn);
    if (pr == 0) { sx_free(val); sx_free(ev); sx_free(subj);
        return dc_unsupported(m, "%s: decision diagrams and SAT solver disagree (%s)", h, why); }
    Sx *res;
    if (pr == 1) {
        sx_push(ev->items[1], dc_form("Proof", dc_form("Solver", dc_sym("cadical-3.0.1"), NULL), dc_form("Format", dc_sym("LRAT"), NULL),
                                      dc_form("Checker", dc_sym("cake_lpr-033aad5"), NULL), dc_form("CnfSha256", sx_str(pdg), NULL), dc_form("Generator", dc_sym("dcalc-symgen"), dc_sym(SYM_GEN_VERSION), NULL), NULL));
        res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), subj, val, ev, NULL, &sc);
    } else {
        char rs[256]; snprintf(rs, sizeof rs, "decision-diagram answer; obligations not yet replayed by a checked proof (%s)", why);
        res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), subj, val, ev, rs, &sc);
        sym_set_conditional(res, dg);
    }
    return res;
}

/* CheckNow obligation on two copies: same code and some observation bit differs (UNSAT = holds). */
static int sym_cnf_now(Cnf *c, const SymMod *S, const SMach *M, int ei, int *goal) {
    int W = S->car[M->states].width, xv[SYM_MAXW], yv[SYM_MAXW];
    if (cnf_init(c, 2 * W)) return -1;
    for (int i = 0; i < W; i++) { xv[i] = i + 1; yv[i] = W + i + 1; }
    int Tr = c->tru, same = Tr, viol = -Tr; CVal ex, ey;
    if (cnf_map(c, S, ei, xv, &ex) || cnf_map(c, S, ei, yv, &ey)) return -1;
    for (int k = 0; k < ex.w; k++) same = cnf_and(c, same, -cnf_xor(c, ex.b[k], ey.b[k]));
    for (int p = 0; p < M->nobs; p++) {
        CVal ox, oy; if (cnf_map(c, S, M->obs[p].map, xv, &ox) || cnf_map(c, S, M->obs[p].map, yv, &oy)) return -1;
        for (int k = 0; k < ox.w; k++) viol = cnf_or(c, viol, cnf_xor(c, ox.b[k], oy.b[k]));
    }
    *goal = cnf_and(c, same, viol);
    return c->bad ? -1 : 0;
}

/* ---- part 5: CheckNow / CheckBehavioral of a Representation on a symbolic machine ----
 * The encoding is enumerated by its fibers (encode width <= 12).  CheckNow: every
 * observation is constant on each fiber.  CheckBehavioral: each fiber lies inside one
 * class of the behavioral partition (sym_refine); a failure gives a pair of words with
 * the same code and a separating word, replayed on the concrete evaluator. */
static int crun(const SymMod *S, const SMach *M, uint64_t x, const int *word, int nw, int port, uint64_t *o) {
    for (int k = 0; k < nw; k++) if (cmap(S, M->act[word[k]].map, x, &x)) return -1;
    return cmap(S, M->obs[port].map, x, o);
}
static int sym_replay_pair(const SymMod *S, const SMach *M, int ei, uint64_t x, uint64_t y, const int *word, int nw, int port) {
    uint64_t ex, ey, ox, oy;
    if (x == y || cmap(S, ei, x, &ex) || cmap(S, ei, y, &ey) || ex != ey) return 0;
    if (crun(S, M, x, word, nw, port, &ox) || crun(S, M, y, word, nw, port, &oy)) return 0;
    return ox != oy;
}
static Sx *sym_req_repr(DcRun *r, const SymMod *S, const Sx *q, const char *h) {
    DcModule *m = r->m; const char *rn, *mn, *en; char err[256]; int mi, ei, beh = !strcmp(h, "CheckBehavioral");
    if (sname(q, 1, &rn)) return dc_invalid(m, "%s: field representation missing or not a name", h);
    if (q->n > 2) return dc_unsupported(m, "%s: extra fields are outside the M3 symbolic engine", h);
    const Sx *rd = sfind_decl(S, rn);
    if (!rd || !sx_head_is(rd, "Representation")) return dc_invalid(m, "%s: %s names no Representation", h, rn);
    if (sname(sfield(rd, "Of"), 1, &mn) || (mi = sfind_mach(S, mn)) < 0) return dc_invalid(m, "Representation %s: (Of Machine) names no machine", rn);
    if (sname(sfield(rd, "Encode"), 1, &en) || (ei = sfind_map(S, en)) < 0) return dc_invalid(m, "Representation %s: (Encode map) names no map", rn);
    for (size_t k = 2; k < rd->n; k++)
        if (!sx_head_is(rd->items[k], "Of") && !sx_head_is(rd->items[k], "Encode"))
            return dc_unsupported(m, "Representation %s: fields other than Of/Encode are outside the M3 symbolic engine", rn);
    const SMach *M = &S->mach[mi];
    if (S->car[M->states].reach) return dc_unsupported(m, "%s: a machine on a reach carrier is outside this step of M3", h);
    if (S->car[S->map[ei].from].width != S->car[M->states].width) return dc_invalid(m, "Representation %s: encode map is not on the machine states", rn);
    int ew = S->car[S->map[ei].to].width;
    if (ew > 12) return dc_unsupported(m, "%s: an encoding wider than 12 bits is outside this step of M3", h);
    SymEnv E; if (senv_init(&E, S->car[M->states].width)) return dc_unsupported(m, "%s: out of memory", h);
    DcBddMgr *bm = E.bm; SymVal enc, av[8], ob[8]; static STest T[SYM_MAXT]; DcBdd cl[SYM_MAXCL]; int nt = 0, ncl = 1, rc = 0;
    if (sym_apply(bm, S, ei, E.xv, &enc, err, sizeof err) || mach_acts(&E, S, M, av, err, sizeof err)) { dc_bdd_free(bm); return dc_invalid(m, "%s: %s", h, err); }
    if (beh) rc = sym_refine(bm, S, M, av, ob, E.xv, T, &nt, cl, &ncl, err, sizeof err);
    else for (int p = 0; p < M->nobs && !rc; p++) if (sym_apply(bm, S, M->obs[p].map, E.xv, &ob[p], err, sizeof err)) rc = -2;
    if (rc == -2) { dc_bdd_free(bm); return dc_invalid(m, "%s: %s", h, err); }
    if (rc || dc_bdd_failed(bm)) { dc_bdd_free(bm); return dc_unsupported(m, "%s: class, test or BDD limit reached", h); }
    int found = 0, port = 0, word[SYM_MAXWD], nw = 0, nfib = 0; uint64_t x = 0, y = 0;
    for (uint64_t c = 0; c < ((uint64_t)1 << ew) && !found; c++) {
        DcBdd F = 1; uint64_t rep, w;
        for (int k = 0; k < ew; k++) F = dc_bdd_and(bm, F, ((c >> k) & 1) ? enc.b[k] : dc_bdd_not(bm, enc.b[k]));
        if (!dc_bdd_min_word(bm, F, &rep)) continue;
        nfib++;
        if (!beh) {
            for (int p = 0; p < M->nobs && !found; p++) for (int k = 0; k < ob[p].w; k++) {
                DcBdd d = dc_bdd_eval(bm, ob[p].b[k], rep) ? dc_bdd_not(bm, ob[p].b[k]) : ob[p].b[k];
                if (dc_bdd_min_word(bm, dc_bdd_and(bm, F, d), &w)) { found = 1; x = rep; y = w; port = p; nw = 0; break; }
            }
        } else {
            int i = -1; for (int j = 0; j < ncl; j++) if (dc_bdd_eval(bm, cl[j], rep)) i = j;
            if (i < 0) { found = -1; break; }
            if (dc_bdd_min_word(bm, dc_bdd_and(bm, F, dc_bdd_not(bm, cl[i])), &w)) {
                found = -1;
                for (int t = 0; t < nt; t++) if (dc_bdd_eval(bm, T[t].f, rep) != dc_bdd_eval(bm, T[t].f, w)) {
                    found = 1; x = rep; y = w; port = T[t].port; nw = T[t].nw; memcpy(word, T[t].word, (size_t)nw * sizeof(int)); break;
                }
            }
        }
    }
    int failed = dc_bdd_failed(bm); size_t nodes = dc_bdd_nodes(bm); dc_bdd_free(bm);
    sym_res_words = nfib + (found > 0 ? 2 : 0); sym_res_nodes = nodes;
    if (failed) return dc_unsupported(m, "%s: BDD node limit reached", h);
    if (found < 0) return dc_unsupported(m, "%s: internal check failed (tests do not separate the witness pair)", h);
    DcScope sc = { "M3-SymbolicBitVector", -1, "", NULL };
    Sx *claim = dc_form("Claim", sx_copy(q), NULL);
    Sx *subj = dc_form("Subject", dc_form("Representation", dc_sym(rn), NULL), dc_form("Machine", dc_sym(mn), NULL), NULL);
    char xb[32], yb[32], nb[32];
    if (found) {
        snprintf(xb, sizeof xb, "%llu", (unsigned long long)x); snprintf(yb, sizeof yb, "%llu", (unsigned long long)y);
        Sx *wd = dc_form("Word", NULL); for (int k = 0; k < nw; k++) sx_push(wd, dc_sym(M->act[word[k]].name));
        Sx *wit = dc_form("Witness", dc_form("Pair", dc_sym(xb), dc_sym(yb), NULL), wd, dc_form("Observe", dc_sym(M->obs[port].name), NULL), NULL);
        Sx *val = dc_form("Value", dc_form("Refuted", sx_copy(wit), NULL), NULL);
        int ok = sym_replay_pair(S, M, ei, x, y, word, nw, port);
        return dc_envelope_scoped(m, VERDICT_FAILS, ok, claim, subj, val, dc_form("Evidence", wit, NULL),
                                  ok ? NULL : "witness did not replay on the concrete evaluator", &sc);
    }
    char buf[512], dg[65]; int bl = snprintf(buf, sizeof buf, "%s|%s|%s|%s|%s", m->digest, h, rn, mn, en);
    dc_sha256_hex(buf, (size_t)bl, dg); snprintf(nb, sizeof nb, "%zu", nodes);
    Sx *val = dc_form("Value", dc_form("Holds", dc_form("Fibers", dc_int(nfib), NULL), NULL), NULL);
    Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym(beh ? "SymbolicBehavioralCandidate" : "SymbolicFiberCandidate"), NULL),
                     dc_form("ObligationDigest", sx_str(dg), NULL), dc_form("BddNodes", dc_sym(nb), NULL), NULL), NULL);
    Cnf cn; int goal, pr = -1; char pdg[65] = "", why[160] = "proof not attempted";
    memset(&cn, 0, sizeof cn);
    if (!beh) { if (sym_cnf_now(&cn, S, M, ei, &goal) == 0) pr = sym_prove(&cn, goal, pdg, why, sizeof why); else snprintf(why, sizeof why, "CNF generation failed"); }
    else snprintf(why, sizeof why, "behavioral proof obligations not generated in this step");
    cnf_free(&cn);
    if (pr == 0) { sx_free(val); sx_free(ev); sx_free(claim); sx_free(subj);
        return dc_unsupported(m, "%s: decision diagrams and SAT solver disagree (%s)", h, why); }
    Sx *res;
    if (pr == 1) {
        sx_push(ev->items[1], dc_form("Proof", dc_form("Solver", dc_sym("cadical-3.0.1"), NULL), dc_form("Format", dc_sym("LRAT"), NULL),
                                      dc_form("Checker", dc_sym("cake_lpr-033aad5"), NULL), dc_form("CnfSha256", sx_str(pdg), NULL), dc_form("Generator", dc_sym("dcalc-symgen"), dc_sym(SYM_GEN_VERSION), NULL), NULL));
        res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, claim, subj, val, ev, NULL, &sc);
    } else {
        char rs[256]; snprintf(rs, sizeof rs, "decision-diagram answer; obligations not yet replayed by a checked proof (%s)", why);
        res = dc_envelope_scoped(m, VERDICT_HOLDS, 1, claim, subj, val, ev, rs, &sc);
        sym_set_conditional(res, dg);
    }
    return res;
}

static Sx *sym_policy(Sx *res) {
    Sx *au = res ? sx_find(res, "Assurance", 1) : NULL, *p = au ? sx_find(au, "Policy", 1) : NULL;
    if (p && p->n == 2) { sx_free(p->items[1]); p->items[1] = dc_sym("M3-SymbolicReplay"); }
    if (res && sym_res_words >= 0) {
        char nb[32]; snprintf(nb, sizeof nb, "%zu", sym_res_nodes);
        sx_push(res, dc_form("Resources", dc_form("ConcreteWords", dc_int(sym_res_words), NULL), dc_form("BddNodes", dc_sym(nb), NULL),
                             dc_form("CrossCheckWords", dc_int(sym_res_xcheck), NULL), dc_form("EnumeratedCarrier", dc_sym("False"), NULL), NULL));
    }
    return res;
}

Sx *dc_req_sym(DcRun *r, const Sx *q, const char *head, int slot) {
    char err[256]; SymMod S;
    sym_res_words = -1; sym_res_nodes = 0; sym_res_xcheck = 0;
    if (sym_read(r->m->source, &S, err, sizeof err)) return dc_invalid(r->m, "symbolic module: %s", err);
    if (!strcmp(head, "CheckBlockPartition")) return sym_policy(sym_req_partition(r->m, &S, q));
    if (!strcmp(head, "MinimizeForQueries")) return sym_policy(sym_req_minimize(r, &S, q, slot));
    if (!strcmp(head, "CheckNow") || !strcmp(head, "CheckBehavioral")) return sym_policy(sym_req_repr(r, &S, q, head));
    return dc_unsupported(r->m, "request %s: symbolic engine not built yet (M3 in progress; module read: %d carriers, %d maps, %d machines)", head, S.ncar, S.nmap, S.nmach);
}
