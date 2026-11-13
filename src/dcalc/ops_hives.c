#include "ops_internal.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* M6 (opt-in, beyond release only): kernel hives, spec section 10 (Hives library), crisp case.
 * (KernelHive H (Member M Carrier Tolerance Measure)... (Correspondence Mi Mj K Measured|Unmeasured)...
 *  (Weights (M q)...)) is read from m->source.  Nodes are (member, value) with weight w_M * mu_M(value);
 * within a member the kernel is the member tolerance (Discrete or Trivial), across members it is the
 * declared CrossKernel (transposed for the reverse direction).  Only 0/1 kernels, Uniform measures and
 * fully measured hives are evaluated; everything else answers Unsupported.
 *   CheckKernelCoherence: Checked iff the kernel is transitive, else Refuted with a violating triple and
 *     the holonomy around the declared member order.
 *   Holonomy (Cycle M1 ... Mk): relational composition of the kernels M1->M2->...->Mk->M1.
 *   ConsensusCost: sum over ordered node pairs w_a w_b (closure(H) - H)(a, b).
 *   LeastCoherentRefinement: max kept mass over graded refinements H' <= H with H'(a,c) >= H'(a,b) + H'(b,c) - 1;
 *     supported when every identification component is a clique or a chordless cycle with equal edge
 *     weights; the answer carries a primal refinement checked against every ordered triple and a dual
 *     solution of equal value (exact optimality certificate); cost = sum w_a w_b (H - H'). */
#define HV_MAXM 8
#define HV_MAXN 64
typedef struct { const char *name; int car, nv, base, trivial; DcRat w; } HvMem;
typedef struct { const char *name; int nm, nn; HvMem mem[HV_MAXM]; int mof[HV_MAXN], vof[HV_MAXN]; DcRat w[HV_MAXN]; signed char H[HV_MAXN][HV_MAXN]; } Hive;

static DcRat rq(long n, long d) { DcRat r; r.n = n; r.d = d; return r; }
static Sx *rsx(DcRat r) { return dc_form("Rat", dc_int((long)r.n), dc_int((long)r.d), NULL); }
static const Sx *hv_kid(const Sx *x, const char *h) {
    for (size_t i = 1; x && x->kind == SX_LIST && i < x->n; i++) if (sx_head_is(x->items[i], h)) return x->items[i];
    return NULL;
}
static const char *hv_arg(const Sx *x, const char *h) { const Sx *k = hv_kid(x, h); return k && k->n == 2 && k->items[1]->kind == SX_SYM ? k->items[1]->text : NULL; }
static const Sx *hv_decl(const DcModule *m, const char *head, const char *name) {
    const Sx *s = m->source;
    for (size_t i = 2; s && i < s->n; i++) { const Sx *d = s->items[i]; if (sx_head_is(d, head) && d->n > 1 && sx_is_sym(d->items[1], name)) return d; }
    return NULL;
}
static int hv_car(const DcModule *m, const char *name) { for (size_t i = 0; i < (size_t)m->ncar; i++) if (!strcmp(m->car[i].name, name)) return (int)i; return -1; }
static int hv_elem(const DcModule *m, int c, const Sx *v) { for (size_t i = 0; i < m->car[c].n; i++) if (sx_equal(m->car[c].elems[i], v)) return (int)i; return -1; }
static int hv_mem(const Hive *h, const char *nm) { for (int i = 0; i < h->nm; i++) if (!strcmp(h->mem[i].name, nm)) return i; return -1; }
static Sx *hv_node(const DcModule *m, const Hive *h, int a) { const HvMem *M = &h->mem[h->mof[a]]; return dc_form("Node", dc_sym(M->name), sx_copy(m->car[M->car].elems[h->vof[a]]), NULL); }

#define HV_FAIL(rc, ...) do { snprintf(why, wn, __VA_ARGS__); return rc; } while (0)
static int hv_load(const DcModule *m, const Sx *hn, Hive *h, char *why, size_t wn) {
    memset(h, 0, sizeof *h); int ovf = 0;
    if (hn && sx_head_is(hn, "Output")) HV_FAIL(-2, "derived hives ((Output Derive Hive), KernelOf) are not evaluated yet");
    if (!hn || hn->kind != SX_SYM) HV_FAIL(-1, "expected a KernelHive name");
    const Sx *d = hv_decl(m, "KernelHive", hn->text);
    if (!d) HV_FAIL(-1, "%s names no declared KernelHive", hn->text);
    h->name = d->items[1]->text;
    for (size_t i = 2; i < d->n; i++) {
        const Sx *x = d->items[i];
        if (!sx_head_is(x, "Member")) continue;
        if (x->n != 5 || x->items[1]->kind != SX_SYM || x->items[2]->kind != SX_SYM || x->items[3]->kind != SX_SYM || x->items[4]->kind != SX_SYM)
            HV_FAIL(-1, "KernelHive %s: expected (Member Name Carrier Tolerance Measure)", h->name);
        if (h->nm >= HV_MAXM) HV_FAIL(-2, "KernelHive %s: more than %d members", h->name, HV_MAXM);
        if (hv_mem(h, x->items[1]->text) >= 0) HV_FAIL(-1, "KernelHive %s: Member %s declared twice", h->name, x->items[1]->text);
        HvMem *M = &h->mem[h->nm]; M->name = x->items[1]->text;
        if ((M->car = hv_car(m, x->items[2]->text)) < 0) HV_FAIL(-1, "Member %s: Carrier %s is not declared", M->name, x->items[2]->text);
        const Sx *t = hv_decl(m, "Tolerance", x->items[3]->text), *ms = hv_decl(m, "Measure", x->items[4]->text);
        if (!t || t->n != 4) HV_FAIL(-1, "Member %s: Tolerance %s is not declared", M->name, x->items[3]->text);
        if (!ms || ms->n != 4) HV_FAIL(-1, "Member %s: Measure %s is not declared", M->name, x->items[4]->text);
        if (!hv_arg(t, "On") || strcmp(hv_arg(t, "On"), x->items[2]->text) || !hv_arg(ms, "On") || strcmp(hv_arg(ms, "On"), x->items[2]->text))
            HV_FAIL(-1, "Member %s: tolerance and measure must be On %s", M->name, x->items[2]->text);
        if (sx_head_is(t->items[3], "Discrete") && t->items[3]->n == 1) M->trivial = 0;
        else if (sx_head_is(t->items[3], "Trivial") && t->items[3]->n == 1) M->trivial = 1;
        else HV_FAIL(-2, "Member %s: only Discrete and Trivial member tolerances are evaluated", M->name);
        if (!(sx_head_is(ms->items[3], "Uniform") && ms->items[3]->n == 1)) HV_FAIL(-2, "Member %s: only Uniform measures are evaluated", M->name);
        M->nv = (int)m->car[M->car].n;
        if (M->nv <= 0) HV_FAIL(-1, "Member %s: empty carrier", M->name);
        if (h->nn + M->nv > HV_MAXN) HV_FAIL(-2, "KernelHive %s: more than %d nodes", h->name, HV_MAXN);
        M->base = h->nn;
        for (int v = 0; v < M->nv; v++) { h->mof[h->nn] = h->nm; h->vof[h->nn] = v; h->nn++; }
        h->nm++;
    }
    if (h->nm < 2) HV_FAIL(-1, "KernelHive %s: needs at least two Members", h->name);
    for (int i = 0; i < h->nm; i++) h->mem[i].w = rq(1, h->nm);
    const Sx *W = hv_kid(d, "Weights");
    if (W) {
        DcRat s = rq(0, 1); int seen = 0;
        for (size_t k = 1; k < W->n; k++) {
            const Sx *e = W->items[k]; DcRat q; int i;
            if (e->kind != SX_LIST || e->n != 2 || e->items[0]->kind != SX_SYM || (i = hv_mem(h, e->items[0]->text)) < 0 || dc_sx_rat(e->items[1], &q) || q.n < 0)
                HV_FAIL(-1, "KernelHive %s: Weights entry %zu is not (Member q) with q >= 0", h->name, k);
            h->mem[i].w = q; s = dc_rat_add(s, q, &ovf); seen++;
        }
        if (seen != h->nm || dc_rat_cmp(s, rq(1, 1))) HV_FAIL(-1, "KernelHive %s: Weights must give every member once and sum to 1", h->name);
    }
    for (int a = 0; a < h->nn; a++) h->w[a] = dc_rat_mul(h->mem[h->mof[a]].w, rq(1, h->mem[h->mof[a]].nv), &ovf);
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++)
        h->H[a][b] = h->mof[a] != h->mof[b] ? -1 : a == b ? 1 : h->mem[h->mof[a]].trivial;
    for (size_t k = 2; k < d->n; k++) {
        const Sx *x = d->items[k];
        if (!sx_head_is(x, "Correspondence")) continue;
        int i, j;
        if (x->n != 5 || x->items[1]->kind != SX_SYM || x->items[2]->kind != SX_SYM || x->items[3]->kind != SX_SYM
            || (i = hv_mem(h, x->items[1]->text)) < 0 || (j = hv_mem(h, x->items[2]->text)) < 0 || i == j
            || !(sx_is_sym(x->items[4], "Measured") || sx_is_sym(x->items[4], "Unmeasured")))
            HV_FAIL(-1, "KernelHive %s: expected (Correspondence Mi Mj Kernel Measured|Unmeasured) between two declared members", h->name);
        if (sx_is_sym(x->items[4], "Unmeasured")) continue;
        const HvMem *A = &h->mem[i], *B = &h->mem[j];
        if (h->H[A->base][B->base] >= 0) HV_FAIL(-1, "KernelHive %s: correspondence %s %s declared twice", h->name, A->name, B->name);
        const Sx *K = hv_decl(m, "CrossKernel", x->items[3]->text), *E = K ? hv_kid(K, "Entries") : NULL;
        if (!K || !E) HV_FAIL(-1, "KernelHive %s: CrossKernel %s is not declared", h->name, x->items[3]->text);
        if (!hv_arg(K, "Left") || hv_car(m, hv_arg(K, "Left")) != A->car || !hv_arg(K, "Right") || hv_car(m, hv_arg(K, "Right")) != B->car)
            HV_FAIL(-1, "CrossKernel %s: Left/Right must be the carriers of %s and %s", x->items[3]->text, A->name, B->name);
        for (size_t e = 1; e < E->n; e++) {
            const Sx *t = E->items[e]; int l, r; DcRat v;
            if (t->kind != SX_LIST || t->n != 3 || (l = hv_elem(m, A->car, t->items[0])) < 0 || (r = hv_elem(m, B->car, t->items[1])) < 0 || dc_sx_rat(t->items[2], &v))
                HV_FAIL(-1, "CrossKernel %s: entry %zu is not (left right degree) over its carriers", x->items[3]->text, e);
            if (!(v.n == 0 || (v.n == 1 && v.d == 1))) HV_FAIL(-2, "CrossKernel %s: graded degrees are not evaluated (crisp 0/1 kernels only)", x->items[3]->text);
            h->H[A->base + l][B->base + r] = h->H[B->base + r][A->base + l] = (signed char)v.n;
        }
        for (int l = 0; l < A->nv; l++) for (int r = 0; r < B->nv; r++)
            if (h->H[A->base + l][B->base + r] < 0) HV_FAIL(-1, "CrossKernel %s: Entries do not cover every pair", x->items[3]->text);
    }
    if (ovf) HV_FAIL(-2, "KernelHive %s: rational overflow", h->name);
    return 0;
}
static int hv_complete(const Hive *h, char *why, size_t wn) {
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++) if (h->H[a][b] < 0)
        HV_FAIL(-2, "KernelHive %s: the correspondence between %s and %s is Unmeasured or undeclared; completion (CompleteHive) is outside this milestone",
                h->name, h->mem[h->mof[a]].name, h->mem[h->mof[b]].name);
    return 0;
}
/* R[a][c] over the values of cyc[0]: composite of the kernels cyc[0] -> cyc[1] -> ... -> cyc[k-1] -> cyc[0]. */
static int hv_holo(const Hive *h, const int *cyc, int k, unsigned char R[HV_MAXN][HV_MAXN], char *why, size_t wn) {
    static unsigned char nx[HV_MAXN][HV_MAXN];
    const HvMem *S = &h->mem[cyc[0]]; int u = cyc[0];
    for (int a = 0; a < S->nv; a++) for (int b = 0; b < S->nv; b++) R[a][b] = a == b;
    for (int s = 1; s <= k; s++) {
        int v = cyc[s % k]; const HvMem *U = &h->mem[u], *V = &h->mem[v];
        if (u == v) HV_FAIL(-1, "Cycle: member %s follows itself", U->name);
        for (int a = 0; a < S->nv; a++) for (int c = 0; c < V->nv; c++) {
            int x = 0;
            for (int b = 0; b < U->nv; b++) {
                int hh = h->H[U->base + b][V->base + c];
                if (hh < 0) HV_FAIL(-2, "Holonomy: the correspondence between %s and %s is Unmeasured or undeclared", U->name, V->name);
                x |= R[a][b] && hh;
            }
            nx[a][c] = (unsigned char)x;
        }
        for (int a = 0; a < S->nv; a++) for (int c = 0; c < V->nv; c++) R[a][c] = nx[a][c];
        u = v;
    }
    return 0;
}
static Sx *hv_kernel(const DcModule *m, const Hive *h, int mi, unsigned char R[HV_MAXN][HV_MAXN]) {
    const HvMem *M = &h->mem[mi]; Sx *E = sx_list(); int id = 1;
    sx_push(E, dc_sym("Entries"));
    for (int a = 0; a < M->nv; a++) for (int c = 0; c < M->nv; c++) {
        Sx *t = sx_list(); sx_push(t, sx_copy(m->car[M->car].elems[a])); sx_push(t, sx_copy(m->car[M->car].elems[c])); sx_push(t, dc_int(R[a][c]));
        sx_push(E, t); if (R[a][c] != (a == c)) id = 0;
    }
    return dc_form("Kernel", dc_form("From", dc_sym(M->name), NULL), dc_form("On", dc_sym(m->car[M->car].name), NULL), E,
                   dc_form("Identity", dc_sym(id ? "True" : "False"), NULL), NULL);
}
static Sx *hv_subj(const Hive *h) { return dc_form("Subject", dc_form("Hive", dc_sym(h->name), NULL), NULL); }
#define HV_LOAD(op) \
    int rc = hv_load(m, q->n >= 2 ? q->items[1] : NULL, h, why, sizeof why); \
    if (!rc) rc = hv_complete(h, why, sizeof why); \
    if (rc == -2) return dc_unsupported(m, "%s: %s", op, why); \
    if (rc) return dc_invalid(m, "%s: %s", op, why);

static Hive g_h;
static Sx *hv_coh(DcRun *r, const Sx *q) {
    DcModule *m = r->m; Hive *h = &g_h; char why[300]; static unsigned char R[HV_MAXN][HV_MAXN];
    if (q->n != 2) return dc_invalid(m, "CheckKernelCoherence: expected (CheckKernelCoherence Hive)");
    HV_LOAD("CheckKernelCoherence")
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++) for (int c = 0; c < h->nn; c++)
        if (h->H[a][b] && h->H[b][c] && !h->H[a][c]) {
            Sx *ev = dc_form("Evidence", dc_form("Witness", dc_form("Triple", hv_node(m, h, a), hv_node(m, h, b), hv_node(m, h, c), NULL),
                             dc_form("Degrees", dc_int(1), dc_int(1), dc_int(0), NULL), NULL), NULL);
            int cyc[HV_MAXM]; for (int i = 0; i < h->nm; i++) cyc[i] = i;
            if (h->nm >= 3 && !hv_holo(h, cyc, h->nm, R, why, sizeof why)) sx_push(ev, dc_form("Holonomy", hv_kernel(m, h, 0, R), NULL));
            return dc_envelope(m, VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), hv_subj(h), NULL, ev, NULL);
        }
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), hv_subj(h), NULL,
                       dc_form("Evidence", dc_form("Transitive", dc_form("Triples", dc_int((long)h->nn * h->nn * h->nn), NULL), NULL), NULL), NULL);
}
static Sx *hv_hol(DcRun *r, const Sx *q) {
    DcModule *m = r->m; Hive *h = &g_h; char why[300]; static unsigned char R[HV_MAXN][HV_MAXN]; int cyc[HV_MAXM * 4], k = 0;
    if (q->n != 3 || !sx_head_is(q->items[2], "Cycle") || q->items[2]->n < 3) return dc_invalid(m, "Holonomy: expected (Holonomy Hive (Cycle M1 M2 ...))");
    int rc = hv_load(m, q->items[1], h, why, sizeof why);
    if (rc == -2) return dc_unsupported(m, "Holonomy: %s", why);
    if (rc) return dc_invalid(m, "Holonomy: %s", why);
    const Sx *C = q->items[2];
    for (size_t i = 1; i < C->n; i++) {
        if (k >= HV_MAXM * 4 || C->items[i]->kind != SX_SYM || (cyc[k] = hv_mem(h, C->items[i]->text)) < 0) return dc_invalid(m, "Holonomy: Cycle entry %zu is not a member of %s", i, h->name);
        k++;
    }
    rc = hv_holo(h, cyc, k, R, why, sizeof why);
    if (rc == -2) return dc_unsupported(m, "%s", why);
    if (rc) return dc_invalid(m, "Holonomy: %s", why);
    Sx *path = dc_form("Path", NULL);
    for (int i = 0; i <= k; i++) sx_push(path, dc_sym(h->mem[cyc[i % k]].name));
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), hv_subj(h), dc_form("Value", hv_kernel(m, h, cyc[0], R), NULL),
                       dc_form("Evidence", dc_form("Composition", path, NULL), NULL), NULL);
}
static Sx *hv_cost(DcRun *r, const Sx *q) {
    DcModule *m = r->m; Hive *h = &g_h; char why[300]; static unsigned char Hb[HV_MAXN][HV_MAXN]; int ovf = 0;
    if (q->n != 2) return dc_invalid(m, "ConsensusCost: expected (ConsensusCost Hive)");
    HV_LOAD("ConsensusCost")
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++) Hb[a][b] = (unsigned char)(h->H[a][b] > 0);
    for (int k = 0; k < h->nn; k++) for (int a = 0; a < h->nn; a++) if (Hb[a][k]) for (int b = 0; b < h->nn; b++) if (Hb[k][b]) Hb[a][b] = 1;
    DcRat cost = rq(0, 1); int classes = 0;
    for (int a = 0; a < h->nn; a++) {
        int first = 1;
        for (int b = 0; b < a; b++) if (Hb[a][b] && Hb[b][a]) first = 0;
        classes += first;
        for (int b = 0; b < h->nn; b++) if (Hb[a][b] && !h->H[a][b]) cost = dc_rat_add(cost, dc_rat_mul(h->w[a], h->w[b], &ovf), &ovf);
    }
    if (ovf) return dc_unsupported(m, "ConsensusCost: rational overflow");
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), hv_subj(h), dc_form("Value", rsx(cost), NULL),
                       dc_form("Evidence", dc_form("Closure", dc_form("Classes", dc_int(classes), NULL), NULL), NULL), NULL);
}
static Sx *hv_lcr(DcRun *r, const Sx *q) {
    DcModule *m = r->m; Hive *h = &g_h; char why[300]; int ovf = 0, n;
    static int comp[HV_MAXN], deg[HV_MAXN], ord[HV_MAXN]; static DcRat X[HV_MAXN][HV_MAXN];
    typedef struct { int a, b, c; DcRat y; } Dual;   /* c < 0: capacity x_ab <= 1; else x_ab + x_bc <= 1 (H(a,c) = 0) */
    static Dual D[HV_MAXN * HV_MAXN]; int nd = 0;
    if (q->n != 2) return dc_invalid(m, "LeastCoherentRefinement: expected (LeastCoherentRefinement Hive)");
    HV_LOAD("LeastCoherentRefinement")
    n = h->nn;
    for (int a = 0; a < n; a++) { comp[a] = -1; deg[a] = 0; for (int b = 0; b < n; b++) { X[a][b] = rq(a == b, 1); if (a != b && h->H[a][b]) deg[a]++; } }
    for (int s = 0, nc = 0; s < n; s++) if (comp[s] < 0) {
        int st[HV_MAXN], sp = 0, cs = 0; comp[s] = nc; st[sp++] = s;
        while (sp) { int a = st[--sp]; ord[cs++] = a; for (int b = 0; b < n; b++) if (b != a && h->H[a][b] && comp[b] < 0) { comp[b] = nc; st[sp++] = b; } }
        nc++;
        if (cs < 2) continue;
        int clique = 1;
        for (int i = 0; i < cs; i++) for (int j = 0; j < cs; j++) if (i != j && !h->H[ord[i]][ord[j]]) clique = 0;
        if (clique) {
            for (int i = 0; i < cs; i++) for (int j = i + 1; j < cs; j++) {
                int a = ord[i], b = ord[j]; X[a][b] = X[b][a] = rq(1, 1);
                D[nd].a = a; D[nd].b = b; D[nd].c = -1; D[nd].y = dc_rat_mul(h->w[a], h->w[b], &ovf); nd++;
            }
            continue;
        }
        int cyc = cs >= 4;
        for (int i = 0; i < cs; i++) if (deg[ord[i]] != 2) cyc = 0;
        if (!cyc) return dc_unsupported(m, "LeastCoherentRefinement %s: an identification component is neither a clique nor a chordless cycle; the general linear program is outside this milestone", h->name);
        int path[HV_MAXN], prev = -1, cur = ord[0];
        for (int i = 0; i < cs; i++) {   /* walk the cycle */
            path[i] = cur; int nxt = -1;
            for (int b = 0; b < n && nxt < 0; b++) if (b != cur && b != prev && h->H[cur][b]) nxt = b;
            if (nxt < 0) nxt = prev;
            prev = cur; cur = nxt;
        }
        if (cur != path[0]) return dc_unsupported(m, "LeastCoherentRefinement %s: component walk did not close", h->name);
        DcRat we = dc_rat_mul(h->w[path[0]], h->w[path[1]], &ovf);
        for (int i = 0; i < cs; i++) if (dc_rat_cmp(dc_rat_mul(h->w[path[i]], h->w[path[(i + 1) % cs]], &ovf), we))
            return dc_unsupported(m, "LeastCoherentRefinement %s: cycle edges of unequal weight are outside this milestone", h->name);
        for (int i = 0; i < cs; i++) {
            int a = path[i], b = path[(i + 1) % cs], c = path[(i + 2) % cs];
            X[a][b] = X[b][a] = cs % 2 ? rq(1, 2) : rq(i % 2 == 0, 1);
            D[nd].a = a; D[nd].b = b; D[nd].c = c; D[nd].y = dc_rat_mul(we, rq(1, 2), &ovf); nd++;
        }
    }
    /* primal feasibility over every ordered triple, refinement of H */
    for (int a = 0; a < n; a++) for (int b = 0; b < n; b++) {
        if (dc_rat_cmp(X[a][b], rq(h->H[a][b], 1)) > 0) return dc_unsupported(m, "LeastCoherentRefinement: internal primal exceeds H");
        for (int c = 0; c < n; c++) if (dc_rat_cmp(X[a][c], dc_rat_sub(dc_rat_add(X[a][b], X[b][c], &ovf), rq(1, 1), &ovf)) < 0)
            return dc_unsupported(m, "LeastCoherentRefinement: internal primal violates transitivity");
    }
    /* dual feasibility: every identification edge covered by at least its weight; values */
    DcRat P = rq(0, 1), Dv = rq(0, 1), T = rq(0, 1);
    for (int i = 0; i < nd; i++) Dv = dc_rat_add(Dv, D[i].y, &ovf);
    for (int a = 0; a < n; a++) for (int b = a + 1; b < n; b++) if (h->H[a][b]) {
        DcRat we = dc_rat_mul(h->w[a], h->w[b], &ovf), cov = rq(0, 1);
        T = dc_rat_add(T, we, &ovf); P = dc_rat_add(P, dc_rat_mul(we, X[a][b], &ovf), &ovf);
        for (int i = 0; i < nd; i++) {
            int on = (D[i].a == a && D[i].b == b) || (D[i].a == b && D[i].b == a);
            if (D[i].c >= 0) on = on || (D[i].b == a && D[i].c == b) || (D[i].b == b && D[i].c == a);
            if (on) cov = dc_rat_add(cov, D[i].y, &ovf);
        }
        if (dc_rat_cmp(cov, we) < 0) return dc_unsupported(m, "LeastCoherentRefinement: internal dual infeasible");
    }
    for (int i = 0; i < nd; i++) if (D[i].c >= 0 && h->H[D[i].a][D[i].c]) return dc_unsupported(m, "LeastCoherentRefinement: internal dual uses a chord");
    if (ovf) return dc_unsupported(m, "LeastCoherentRefinement: rational overflow");
    if (dc_rat_cmp(P, Dv)) return dc_unsupported(m, "LeastCoherentRefinement %s: primal and dual values differ; optimality not certified", h->name);
    DcRat cost = dc_rat_mul(rq(2, 1), dc_rat_sub(T, P, &ovf), &ovf);
    Sx *kept = dc_form("Kept", NULL), *dual = dc_form("Dual", NULL);
    for (int a = 0; a < n; a++) for (int b = a + 1; b < n; b++) if (X[a][b].n) sx_push(kept, dc_form("Pair", hv_node(m, h, a), hv_node(m, h, b), rsx(X[a][b]), NULL));
    for (int i = 0; i < nd; i++)
        sx_push(dual, D[i].c < 0 ? dc_form("Edge", hv_node(m, h, D[i].a), hv_node(m, h, D[i].b), rsx(D[i].y), NULL)
                                 : dc_form("Triple", hv_node(m, h, D[i].a), hv_node(m, h, D[i].b), hv_node(m, h, D[i].c), rsx(D[i].y), NULL));
    Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("PrimalValue", rsx(P), NULL), dc_form("DualValue", rsx(Dv), NULL),
                     dc_form("EdgeMass", rsx(T), NULL), kept, dual, NULL), NULL);
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), hv_subj(h), dc_form("Value", rsx(cost), NULL), ev, NULL);
}
Sx *dc_req_hives(DcRun *r, const Sx *q, const char *h) {
    if (!strcmp(h, "CheckKernelCoherence")) return hv_coh(r, q);
    if (!strcmp(h, "Holonomy")) return hv_hol(r, q);
    if (!strcmp(h, "ConsensusCost")) return hv_cost(r, q);
    if (!strcmp(h, "LeastCoherentRefinement")) return hv_lcr(r, q);
    return dc_unsupported(r->m, "%s is outside the M6 Hives subset", h);
}
