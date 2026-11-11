/* In-tree ROBDD package (M3, OQ5).  See bdd.h. */
#include "bdd.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int var, lo, hi; } Node;
typedef struct { int op, a, b, c, r; } CacheEnt;
struct DcBddMgr {
    int nvars, failed;
    Node *n; size_t cnt, cap, limit;
    int *uh; size_t ucap;            /* open addressing: node index or -1 */
    CacheEnt *cache; size_t ccap;    /* direct mapped, ccap power of two */
};

#define DC_BDD_LIMIT ((size_t)1 << 22)

static size_t h3(int a, int b, int c) {
    uint64_t x = (uint64_t)(unsigned)a * 0x9E3779B97F4A7C15ULL;
    x ^= (uint64_t)(unsigned)b * 0xC2B2AE3D27D4EB4FULL; x = (x << 31) | (x >> 33);
    x ^= (uint64_t)(unsigned)c * 0x165667B19E3779F9ULL; x ^= x >> 29;
    return (size_t)x;
}

static int urehash(DcBddMgr *m, size_t ncap) {
    int *nu = malloc(ncap * sizeof *nu);
    if (!nu) return 0;
    for (size_t i = 0; i < ncap; i++) nu[i] = -1;
    for (size_t k = 2; k < m->cnt; k++) {
        size_t i = h3(m->n[k].var, m->n[k].lo, m->n[k].hi) & (ncap - 1);
        while (nu[i] >= 0) i = (i + 1) & (ncap - 1);
        nu[i] = (int)k;
    }
    free(m->uh); m->uh = nu; m->ucap = ncap; return 1;
}

DcBddMgr *dc_bdd_new(int nvars) {
    if (nvars < 1 || nvars > 64) return NULL;
    DcBddMgr *m = calloc(1, sizeof *m);
    if (!m) return NULL;
    m->nvars = nvars; m->limit = DC_BDD_LIMIT; m->cap = 1024;
    m->n = malloc(m->cap * sizeof *m->n);
    m->ccap = (size_t)1 << 16; m->cache = malloc(m->ccap * sizeof *m->cache);
    if (!m->n || !m->cache) { dc_bdd_free(m); return NULL; }
    for (size_t i = 0; i < m->ccap; i++) m->cache[i].op = -1;
    m->n[0] = (Node){ nvars, 0, 0 }; m->n[1] = (Node){ nvars, 1, 1 }; m->cnt = 2;
    if (!urehash(m, 2048)) { dc_bdd_free(m); return NULL; }
    return m;
}
void dc_bdd_free(DcBddMgr *m) { if (!m) return; free(m->n); free(m->uh); free(m->cache); free(m); }
int dc_bdd_nvars(const DcBddMgr *m) { return m->nvars; }
size_t dc_bdd_nodes(const DcBddMgr *m) { return m->cnt; }
int dc_bdd_failed(const DcBddMgr *m) { return m->failed; }

static DcBdd mk(DcBddMgr *m, int v, DcBdd lo, DcBdd hi) {
    if (m->failed) return 0;
    if (lo == hi) return lo;
    size_t i = h3(v, lo, hi) & (m->ucap - 1);
    while (m->uh[i] >= 0) {
        Node *x = &m->n[m->uh[i]];
        if (x->var == v && x->lo == lo && x->hi == hi) return m->uh[i];
        i = (i + 1) & (m->ucap - 1);
    }
    if (m->cnt >= m->limit) { m->failed = 1; return 0; }
    if (m->cnt == m->cap) {
        Node *nn = realloc(m->n, 2 * m->cap * sizeof *nn);
        if (!nn) { m->failed = 1; return 0; }
        m->n = nn; m->cap *= 2;
    }
    int k = (int)m->cnt++;
    m->n[k] = (Node){ v, lo, hi };
    m->uh[i] = k;
    if (2 * m->cnt > m->ucap && !urehash(m, 2 * m->ucap)) { m->failed = 1; return 0; }
    if (m->ccap < m->ucap && m->ccap < ((size_t)1 << 22)) {
        CacheEnt *nc = realloc(m->cache, 2 * m->ccap * sizeof *nc);
        if (nc) { m->cache = nc; m->ccap *= 2; for (size_t j = 0; j < m->ccap; j++) m->cache[j].op = -1; }
    }
    return k;
}

static int cget(DcBddMgr *m, int op, int a, int b, int c, int *r) {
    CacheEnt *e = &m->cache[h3(a ^ (op << 28), b, c) & (m->ccap - 1)];
    if (e->op == op && e->a == a && e->b == b && e->c == c) { *r = e->r; return 1; }
    return 0;
}
static void cput(DcBddMgr *m, int op, int a, int b, int c, int r) {
    if (m->failed) return;
    m->cache[h3(a ^ (op << 28), b, c) & (m->ccap - 1)] = (CacheEnt){ op, a, b, c, r };
}

DcBdd dc_bdd_var(DcBddMgr *m, int v) { return (v < 0 || v >= m->nvars) ? (m->failed = 1, 0) : mk(m, v, 0, 1); }

DcBdd dc_bdd_ite(DcBddMgr *m, DcBdd f, DcBdd g, DcBdd h) {
    if (m->failed) return 0;
    if (f == 1) return g;
    if (f == 0) return h;
    if (g == h) return g;
    if (g == 1 && h == 0) return f;
    int r;
    if (cget(m, 0, f, g, h, &r)) return r;
    int v = m->n[f].var;
    if (m->n[g].var < v) v = m->n[g].var;
    if (m->n[h].var < v) v = m->n[h].var;
#define CO(x, b) (m->n[x].var == v ? ((b) ? m->n[x].hi : m->n[x].lo) : (x))
    int f0 = CO(f, 0), f1 = CO(f, 1), g0 = CO(g, 0), g1 = CO(g, 1), h0 = CO(h, 0), h1 = CO(h, 1);
#undef CO
    DcBdd lo = dc_bdd_ite(m, f0, g0, h0);
    DcBdd hi = dc_bdd_ite(m, f1, g1, h1);
    r = mk(m, v, lo, hi);
    cput(m, 0, f, g, h, r);
    return r;
}
DcBdd dc_bdd_not(DcBddMgr *m, DcBdd f) { return dc_bdd_ite(m, f, 0, 1); }
DcBdd dc_bdd_and(DcBddMgr *m, DcBdd f, DcBdd g) { return dc_bdd_ite(m, f, g, 0); }
DcBdd dc_bdd_or(DcBddMgr *m, DcBdd f, DcBdd g) { return dc_bdd_ite(m, f, 1, g); }
DcBdd dc_bdd_xor(DcBddMgr *m, DcBdd f, DcBdd g) { return dc_bdd_ite(m, f, dc_bdd_not(m, g), g); }

DcBdd dc_bdd_restrict(DcBddMgr *m, DcBdd f, int v, int val) {
    if (m->failed) return 0;
    if (m->n[f].var > v) return f;
    if (m->n[f].var == v) return val ? m->n[f].hi : m->n[f].lo;
    int r;
    if (cget(m, 1, f, v, val, &r)) return r;
    int fv = m->n[f].var, flo = m->n[f].lo, fhi = m->n[f].hi;
    DcBdd lo = dc_bdd_restrict(m, flo, v, val);
    DcBdd hi = dc_bdd_restrict(m, fhi, v, val);
    r = mk(m, fv, lo, hi);
    cput(m, 1, f, v, val, r);
    return r;
}
DcBdd dc_bdd_exists(DcBddMgr *m, DcBdd f, int v) {
    return dc_bdd_or(m, dc_bdd_restrict(m, f, v, 0), dc_bdd_restrict(m, f, v, 1));
}

static DcBdd comp_rec(DcBddMgr *m, DcBdd f, const DcBdd *sub, int *memo) {
    if (f < 2 || m->failed) return f;
    if (memo[f] >= 0) return memo[f];
    int fv = m->n[f].var, flo = m->n[f].lo, fhi = m->n[f].hi;
    DcBdd lo = comp_rec(m, flo, sub, memo);
    DcBdd hi = comp_rec(m, fhi, sub, memo);
    DcBdd r = dc_bdd_ite(m, sub[fv], hi, lo);
    memo[f] = r;
    return r;
}
DcBdd dc_bdd_compose(DcBddMgr *m, DcBdd f, const DcBdd *sub) {
    size_t n0 = m->cnt;            /* every node of f has index < n0 */
    int *memo = malloc(n0 * sizeof *memo);
    if (!memo) { m->failed = 1; return 0; }
    for (size_t i = 0; i < n0; i++) memo[i] = -1;
    DcBdd r = comp_rec(m, f, sub, memo);
    free(memo);
    return m->failed ? 0 : r;
}

static void supp_rec(const DcBddMgr *m, DcBdd f, unsigned char *seen, unsigned char *out) {
    if (f < 2 || seen[f]) return;
    seen[f] = 1; out[m->n[f].var] = 1;
    supp_rec(m, m->n[f].lo, seen, out); supp_rec(m, m->n[f].hi, seen, out);
}
void dc_bdd_support(const DcBddMgr *m, DcBdd f, unsigned char *out) {
    memset(out, 0, (size_t)m->nvars);
    unsigned char *seen = calloc(m->cnt, 1);
    if (!seen) return;
    supp_rec(m, f, seen, out);
    free(seen);
}

/* least word: free and skipped variables take 0 */
static int minw_rec(const DcBddMgr *m, DcBdd f, uint64_t *val, unsigned char *st) {
    if (f == 0) return 0;
    if (f == 1) { *val = 0; return 1; }
    if (st[f]) { *val = ((uint64_t *)(st + m->cnt))[f]; return st[f] == 1; }
    uint64_t a = 0, b = 0;
    int sa = minw_rec(m, m->n[f].lo, &a, st), sb = minw_rec(m, m->n[f].hi, &b, st);
    if (sb) b += (uint64_t)1 << m->n[f].var;
    int ok = sa || sb;
    uint64_t r = !sa ? b : !sb ? a : (a < b ? a : b);
    st[f] = ok ? 1 : 2; ((uint64_t *)(st + m->cnt))[f] = r;
    *val = r; return ok;
}
int dc_bdd_min_word(const DcBddMgr *m, DcBdd f, uint64_t *word) {
    /* st: cnt status bytes followed (aligned) by cnt uint64 values */
    size_t pad = (m->cnt + 7) & ~(size_t)7;
    unsigned char *buf = calloc(pad + m->cnt * sizeof(uint64_t), 1);
    if (!buf) return 0;
    /* values live at buf + pad; minw_rec indexes st + cnt, so shift base */
    unsigned char *st = buf + pad - m->cnt;
    memset(st, 0, m->cnt);
    int ok = minw_rec(m, f, word, st);
    free(buf);
    return ok;
}

int dc_bdd_eval(const DcBddMgr *m, DcBdd f, uint64_t word) {
    while (f >= 2) f = ((word >> m->n[f].var) & 1) ? m->n[f].hi : m->n[f].lo;
    return f;
}

static double sc_rec(const DcBddMgr *m, DcBdd f, double *memo) {
    if (f < 2) return (double)f;
    if (memo[f] >= 0) return memo[f];
    int v = m->n[f].var, lo = m->n[f].lo, hi = m->n[f].hi;
    double r = ldexp(sc_rec(m, lo, memo), m->n[lo].var - v - 1) + ldexp(sc_rec(m, hi, memo), m->n[hi].var - v - 1);
    memo[f] = r; return r;
}
double dc_bdd_satcount(const DcBddMgr *m, DcBdd f) {
    double *memo = malloc(m->cnt * sizeof *memo);
    if (!memo) return -1;
    for (size_t i = 0; i < m->cnt; i++) memo[i] = -1;
    double r = ldexp(sc_rec(m, f, memo), m->n[f].var);
    free(memo);
    return r;
}
