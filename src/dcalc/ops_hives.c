#include "ops_internal.h"
#include "ops_run.h"
#include "lp_exact.h"
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
static int hv_load(const DcModule *m, const Sx *hn, Hive *h, char *why, size_t wn);
static int hv_bfs(const Hive *h, int s, int *par);
/* M6-rest review-1 F1: (Derive C (CompleteHive H)) used as (Output C Hive) returns the completed hive.  Measured entries
 * stay fixed; an unmeasured entry joined by a measured path becomes 1; the other unmeasured entries of a member pair that
 * some measured path joins become 0 (the least value); every entry of a NoPath member pair stays Unmeasured (-1), so a
 * claim that reads it answers Unknown (CheckKernelCoherence) or Unsupported (requests that read only measured entries). */
static int hv_fillc(const DcModule *m, const Sx *req, Hive *h, char *why, size_t wn) {
    static int depth = 0; static int par[HV_MAXN][HV_MAXN];
    if (req->n != 2) HV_FAIL(-1, "expected (CompleteHive Hive)");
    if (depth > 3) HV_FAIL(-2, "CompleteHive: completions nested more than 4 deep");
    depth++; int rc = hv_load(m, req->items[1], h, why, wn); depth--;
    if (rc) return rc;
    for (int a = 0; a < h->nn; a++) hv_bfs(h, a, par[a]);
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++) if (h->H[a][b] == 0 && par[a][b] != -2)
        HV_FAIL(-2, "CompleteHive %s: the measured entry between %s[%d] and %s[%d] is 0 but a measured path identifies them; the measured correspondences are not Lipschitz and round-trip coherent",
                h->name, h->mem[h->mof[a]].name, h->vof[a], h->mem[h->mof[b]].name, h->vof[b]);
    for (int i = 0; i < h->nm; i++) for (int j = 0; j < h->nm; j++) {
        const HvMem *I = &h->mem[i], *J = &h->mem[j]; int any = 0;
        for (int l = 0; l < I->nv; l++) for (int r2 = 0; r2 < J->nv; r2++) if (par[I->base + l][J->base + r2] != -2) any = 1;
        if (!any) continue;   /* NoPath pair: stays Unmeasured, never zero-filled */
        for (int l = 0; l < I->nv; l++) for (int r2 = 0; r2 < J->nv; r2++) {
            int a = I->base + l, b = J->base + r2;
            if (h->H[a][b] < 0) h->H[a][b] = par[a][b] != -2 ? 1 : 0;
        }
    }
    return 0;
}
static int hv_derived(const DcModule *m, const Sx *hn, Hive *h, char *why, size_t wn) {
    const char *names[HV_MAXM]; int cars[HV_MAXM], nvs[HV_MAXM], nm = 0, ovf = 0;
    if (hn->n != 3 || hn->items[1]->kind != SX_SYM || !sx_is_sym(hn->items[2], "Hive")) HV_FAIL(-1, "expected (Output Derive Hive)");
    const Sx *d = hv_decl(m, "Derive", hn->items[1]->text);
    if (!d || d->n != 3) HV_FAIL(-1, "%s names no declared Derive", hn->items[1]->text);
    if (sx_head_is(d->items[2], "CompleteHive")) { int rc = hv_fillc(m, d->items[2], h, why, wn); if (!rc) h->name = d->items[1]->text; return rc; }
    if (!sx_head_is(d->items[2], "KernelOf")) HV_FAIL(-1, "Derive %s is not a KernelOf or CompleteHive; only derived kernel hives are accepted here", hn->items[1]->text);
    int rc = dc_kernel_of(m, d->items[2], names, cars, nvs, &nm, h->H, why, wn);
    if (rc) return rc;
    h->name = d->items[1]->text; h->nm = nm;
    for (int i = 0; i < nm; i++) {
        HvMem *M = &h->mem[i]; M->name = names[i]; M->car = cars[i]; M->nv = nvs[i]; M->base = h->nn; M->w = rq(1, nm);
        for (int v = 0; v < M->nv; v++) { h->mof[h->nn] = i; h->vof[h->nn] = v; h->nn++; }
    }
    for (int a = 0; a < h->nn; a++) h->w[a] = dc_rat_mul(h->mem[h->mof[a]].w, rq(1, h->mem[h->mof[a]].nv), &ovf);
    if (ovf) HV_FAIL(-2, "KernelHive %s: rational overflow", h->name);
    return 0;
}
static int hv_load(const DcModule *m, const Sx *hn, Hive *h, char *why, size_t wn) {
    memset(h, 0, sizeof *h); int ovf = 0;
    if (hn && sx_head_is(hn, "Output")) return hv_derived(m, hn, h, why, wn);   /* M6: KernelOf */
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
        HV_FAIL(-2, "KernelHive %s: the correspondence between %s and %s is Unmeasured or undeclared; this request reads only measured correspondences; complete them first with (CompleteHive %s)",
                h->name, h->mem[h->mof[a]].name, h->mem[h->mof[b]].name, h->name);
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
    /* review-2 F1 (negative test 4): an Unmeasured correspondence is never zero-filled.  Refuted needs a fully
     * measured intransitive triple; a triple that some completion of the Unmeasured entries could break gives Unknown. */
    int rc = hv_load(m, q->items[1], h, why, sizeof why);
    if (rc == -2) return dc_unsupported(m, "CheckKernelCoherence: %s", why);
    if (rc) return dc_invalid(m, "CheckKernelCoherence: %s", why);
    int ua = -1, ub = -1, uc = -1;
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++) for (int c = 0; c < h->nn; c++)
        if (ua < 0 && a != b && b != c && a != c   /* a degenerate triple shares an entry, so no completion breaks it */
            && h->H[a][b] && h->H[b][c] && h->H[a][c] != 1 && (h->H[a][b] < 0 || h->H[b][c] < 0 || h->H[a][c] < 0)
            && !(h->H[a][b] == 1 && h->H[b][c] == 1 && h->H[a][c] == 0)) { ua = a; ub = b; uc = c; }
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++) for (int c = 0; c < h->nn; c++)
        if (h->H[a][b] == 1 && h->H[b][c] == 1 && h->H[a][c] == 0) {
            Sx *ev = dc_form("Evidence", dc_form("Witness", dc_form("Triple", hv_node(m, h, a), hv_node(m, h, b), hv_node(m, h, c), NULL),
                             dc_form("Degrees", dc_int(1), dc_int(1), dc_int(0), NULL), NULL), NULL);
            int cyc[HV_MAXM]; for (int i = 0; i < h->nm; i++) cyc[i] = i;
            if (h->nm >= 3 && !hv_holo(h, cyc, h->nm, R, why, sizeof why)) sx_push(ev, dc_form("Holonomy", hv_kernel(m, h, 0, R), NULL));
            return dc_envelope(m, VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), hv_subj(h), NULL, ev, NULL);
        }
    if (ua >= 0) {
        char rs[300]; snprintf(rs, sizeof rs, "an Unmeasured correspondence is not zero-filled; triple (%s %s %s) is transitive or not depending on its completion",
                               h->mem[h->mof[ua]].name, h->mem[h->mof[ub]].name, h->mem[h->mof[uc]].name);
        return dc_envelope(m, VERDICT_HOLDS, 0, dc_claim_of(q, "Literal"), hv_subj(h), NULL,
                           dc_form("Evidence", dc_form("Open", dc_form("Triple", hv_node(m, h, ua), hv_node(m, h, ub), hv_node(m, h, uc), NULL), NULL), NULL), rs);
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
/* M6-rest: general LeastCoherentRefinement as an exact linear program (spec Sec. 10.4, Example 10.5: "optimality over
 * all graded refinements is a linear-programming fact, and it has an exact certificate").  Variables x_ab for the
 * identification pairs a < b of H; maximize sum w_a w_b x_ab subject to x_ab <= 1 (Edge rows) and, for every middle
 * node b and pair a < c with H(a,b) = H(b,c) = 1, x_ab + x_bc - x_ac <= 1 (Triple rows when H(a,c) = 0, so x_ac = 0;
 * Chord rows otherwise; Chord is ours, M6-rest registry patch).  Every other ordered-triple constraint is implied
 * by 0 <= x <= 1.  Solved by the exact Bland simplex (lp_exact.c); the primal is re-checked against every ordered
 * triple and the dual against every variable before anything is reported. */
#define HV_LP_MAXV 120
#define HV_LP_MAXR 1200
static Sx *hv_lcr_lp(DcModule *m, const Hive *h, const Sx *q) {
    int n = h->nn, ovf = 0, nv = 0, nr = 0, rc;
    static int vid[HV_MAXN][HV_MAXN]; static DcRat X[HV_MAXN][HV_MAXN];
    int va[HV_LP_MAXV], vb[HV_LP_MAXV]; static int ra[HV_LP_MAXR], rb[HV_LP_MAXR], rcn[HV_LP_MAXR];
    for (int a = 0; a < n; a++) for (int b = 0; b < n; b++) vid[a][b] = -1;
    for (int a = 0; a < n; a++) for (int b = a + 1; b < n; b++) if (h->H[a][b]) {
        if (nv >= HV_LP_MAXV) return dc_unsupported(m, "LeastCoherentRefinement %s: more than %d identification pairs; the exact linear program is capped there", h->name, HV_LP_MAXV);
        vid[a][b] = vid[b][a] = nv; va[nv] = a; vb[nv] = b; nv++;
    }
    for (int i = 0; i < nv; i++) { ra[nr] = va[i]; rb[nr] = vb[i]; rcn[nr] = -1; nr++; }
    for (int b = 0; b < n; b++) for (int a = 0; a < n; a++) for (int c = a + 1; c < n; c++)
        if (a != b && c != b && vid[a][b] >= 0 && vid[b][c] >= 0) {
            if (nr >= HV_LP_MAXR) return dc_unsupported(m, "LeastCoherentRefinement %s: more than %d constraints; the exact linear program is capped there", h->name, HV_LP_MAXR);
            ra[nr] = a; rb[nr] = b; rcn[nr] = c; nr++;
        }
    DcRat *A = calloc((size_t)nr * (size_t)nv, sizeof(DcRat)), *bb = malloc(sizeof(DcRat) * (size_t)nr), *cc = malloc(sizeof(DcRat) * (size_t)nv),
          *x = malloc(sizeof(DcRat) * (size_t)nv), *y = malloc(sizeof(DcRat) * (size_t)nr), val;
    if (!A || !bb || !cc || !x || !y) { free(A); free(bb); free(cc); free(x); free(y); return dc_unsupported(m, "LeastCoherentRefinement: out of memory"); }
    for (size_t k = 0; k < (size_t)nr * (size_t)nv; k++) A[k] = rq(0, 1);
    for (int i = 0; i < nr; i++) {
        bb[i] = rq(1, 1);
        if (rcn[i] < 0) A[(size_t)i * nv + vid[ra[i]][rb[i]]] = rq(1, 1);
        else {
            A[(size_t)i * nv + vid[ra[i]][rb[i]]] = rq(1, 1); A[(size_t)i * nv + vid[rb[i]][rcn[i]]] = rq(1, 1);
            if (vid[ra[i]][rcn[i]] >= 0) A[(size_t)i * nv + vid[ra[i]][rcn[i]]] = rq(-1, 1);
        }
    }
    for (int j = 0; j < nv; j++) cc[j] = dc_rat_mul(h->w[va[j]], h->w[vb[j]], &ovf);
    rc = dc_lp_max(nr, nv, A, bb, cc, x, y, &val, &ovf);
    Sx *out = NULL;
#define LPFAIL(...) do { out = dc_unsupported(m, __VA_ARGS__); goto done; } while (0)
    if (ovf) LPFAIL("LeastCoherentRefinement %s: rational overflow in the exact linear program", h->name);
    if (rc) LPFAIL("LeastCoherentRefinement %s: exact linear program did not finish (code %d)", h->name, rc);
    /* independent re-check: primal over every ordered triple, dual over every variable, equal values */
    for (int a = 0; a < n; a++) for (int b = 0; b < n; b++) X[a][b] = a == b ? rq(1, 1) : vid[a][b] >= 0 ? x[vid[a][b]] : rq(0, 1);
    for (int a = 0; a < n; a++) for (int b = 0; b < n; b++) {
        if (X[a][b].n < 0 || dc_rat_cmp(X[a][b], rq(h->H[a][b] || a == b, 1)) > 0) LPFAIL("LeastCoherentRefinement: internal primal outside [0, H]");
        for (int c = 0; c < n; c++) if (dc_rat_cmp(X[a][c], dc_rat_sub(dc_rat_add(X[a][b], X[b][c], &ovf), rq(1, 1), &ovf)) < 0)
            LPFAIL("LeastCoherentRefinement: internal primal violates transitivity");
    }
    DcRat P = rq(0, 1), Dv = rq(0, 1), T = rq(0, 1);
    for (int i = 0; i < nr; i++) { if (y[i].n < 0) LPFAIL("LeastCoherentRefinement: internal dual negative"); Dv = dc_rat_add(Dv, y[i], &ovf); }
    for (int j = 0; j < nv; j++) {
        DcRat cov = rq(0, 1);
        for (int i = 0; i < nr; i++) if (A[(size_t)i * nv + j].n) cov = dc_rat_add(cov, dc_rat_mul(A[(size_t)i * nv + j], y[i], &ovf), &ovf);
        if (dc_rat_cmp(cov, cc[j]) < 0) LPFAIL("LeastCoherentRefinement: internal dual infeasible");
        T = dc_rat_add(T, cc[j], &ovf); P = dc_rat_add(P, dc_rat_mul(cc[j], x[j], &ovf), &ovf);
    }
    if (ovf) LPFAIL("LeastCoherentRefinement %s: rational overflow", h->name);
    if (dc_rat_cmp(P, Dv) || dc_rat_cmp(P, val)) LPFAIL("LeastCoherentRefinement %s: primal and dual values differ; optimality not certified", h->name);
    {
        DcRat cost = dc_rat_mul(rq(2, 1), dc_rat_sub(T, P, &ovf), &ovf);
        Sx *kept = dc_form("Kept", NULL), *dual = dc_form("Dual", NULL);
        for (int a = 0; a < n; a++) for (int b = a + 1; b < n; b++) if (X[a][b].n) sx_push(kept, dc_form("Pair", hv_node(m, h, a), hv_node(m, h, b), rsx(X[a][b]), NULL));
        for (int i = 0; i < nr; i++) if (y[i].n) {
            if (rcn[i] < 0) sx_push(dual, dc_form("Edge", hv_node(m, h, ra[i]), hv_node(m, h, rb[i]), rsx(y[i]), NULL));
            else sx_push(dual, dc_form(vid[ra[i]][rcn[i]] >= 0 ? "Chord" : "Triple", hv_node(m, h, ra[i]), hv_node(m, h, rb[i]), hv_node(m, h, rcn[i]), rsx(y[i]), NULL));
        }
        if (ovf) LPFAIL("LeastCoherentRefinement %s: rational overflow", h->name);
        Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Method", dc_sym("LinearProgram"), NULL), dc_form("PrimalValue", rsx(P), NULL),
                         dc_form("DualValue", rsx(Dv), NULL), dc_form("EdgeMass", rsx(T), NULL), kept, dual, NULL), NULL);
        out = dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), hv_subj(h), dc_form("Value", rsx(cost), NULL), ev, NULL);
    }
done:
#undef LPFAIL
    free(A); free(bb); free(cc); free(x); free(y);
    return out;
}
static Sx *hv_lcr(DcRun *r, const Sx *q) {
    DcModule *m = r->m; Hive *h = &g_h; char why[300]; int ovf = 0, n;
    static int comp[HV_MAXN], deg[HV_MAXN], ord[HV_MAXN]; static DcRat X[HV_MAXN][HV_MAXN];
    typedef struct { int a, b, c; DcRat y; } Dual;   /* c < 0: capacity x_ab <= 1; else x_ab + x_bc <= 1 (H(a,c) = 0) */
    static Dual D[HV_MAXN * HV_MAXN]; int nd = 0;
    if (q->n < 2) return dc_invalid(m, "LeastCoherentRefinement: expected (LeastCoherentRefinement Hive [(Search Exhaustive|LinearProgram)] [(Budget b)])");
    /* M6-rest: registry args (spec registry requests.LeastCoherentRefinement): Search Exhaustive|LinearProgram, default
     * LinearProgram; Budget is a work limit.  Unsupported options answer Unsupported, never a silent fallback. */
    { int hs = 0, hb = 0;
      for (size_t i = 2; i < q->n; i++) {
          const Sx *f = q->items[i];
          if (sx_head_is(f, "Search") && f->n == 2 && f->items[1]->kind == SX_SYM && !hs) {
              hs = 1;
              if (!strcmp(f->items[1]->text, "LinearProgram")) continue;
              if (!strcmp(f->items[1]->text, "Exhaustive")) return dc_unsupported(m, "LeastCoherentRefinement: (Search Exhaustive) is not implemented; graded refinements form a continuum, so this release answers through the exact linear program (Search LinearProgram) only");
              return dc_invalid(m, "LeastCoherentRefinement: Search must be Exhaustive or LinearProgram");
          }
          if (sx_head_is(f, "Budget") && !hb) { hb = 1; return dc_unsupported(m, "LeastCoherentRefinement: (Budget ..) is not implemented; answers are exact or Unsupported"); }
          return dc_invalid(m, "LeastCoherentRefinement: argument %zu is not (Search s) or (Budget b)", i - 1);
      } }
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
        if (!cyc) return hv_lcr_lp(m, h, q);   /* M6-rest: general case */
        int path[HV_MAXN], prev = -1, cur = ord[0];
        for (int i = 0; i < cs; i++) {   /* walk the cycle */
            path[i] = cur; int nxt = -1;
            for (int b = 0; b < n && nxt < 0; b++) if (b != cur && b != prev && h->H[cur][b]) nxt = b;
            if (nxt < 0) nxt = prev;
            prev = cur; cur = nxt;
        }
        if (cur != path[0]) return hv_lcr_lp(m, h, q);   /* M6-rest: general case */
        DcRat we = dc_rat_mul(h->w[path[0]], h->w[path[1]], &ovf);
        for (int i = 0; i < cs; i++) if (dc_rat_cmp(dc_rat_mul(h->w[path[i]], h->w[path[(i + 1) % cs]], &ovf), we))
            return hv_lcr_lp(m, h, q);   /* M6-rest: general case */
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
/* M6-rest: CompleteHive (spec Sec. 10.4 l.2896-2906; semantics = hive decision 2, our reading, crisp 0/1 kernels).
 * A correspondence that was never measured (Unmeasured or undeclared) is completed, never zero-filled silently:
 * every unmeasured entry gets the least value transitivity forces, i.e. 1 exactly when a path of measured
 * identifications joins the two nodes (composition along paths), with measured entries held fixed.  If that closure
 * would change a measured 0 entry, the measured correspondences are not Lipschitz / round-trip coherent and the
 * answer is Unsupported naming the entry and the path.  Value is the alignment cost: sum of w_a w_b over ordered
 * node pairs that the completion fills with 1.  Certificate rows (ours, m6rest patch): (Fill a b (Path n1 .. nk))
 * for each filled identification a < b; (NoPath Mi Mj) for unmeasured member pairs no measured path joins: their
 * entries stay Unmeasured (never 0) in the completed hive, see hv_fillc.  Other unmeasured entries of a joined member
 * pair are 0, the least value.  Optimality Checked: each filled 1 is forced by its Path.
 * The completed hive itself is (Output C Hive) for (Derive C (CompleteHive H)) (HiveResult Hive field). */
static int hv_bfs(const Hive *h, int s, int *par) {
    int q[HV_MAXN], qh = 0, qt = 0;
    for (int i = 0; i < h->nn; i++) par[i] = -2;
    par[s] = -1; q[qt++] = s;
    while (qh < qt) { int a = q[qh++]; for (int b = 0; b < h->nn; b++) if (b != a && h->H[a][b] == 1 && par[b] == -2) { par[b] = a; q[qt++] = b; } }
    return 0;
}
static Sx *hv_path(DcModule *m, const Hive *h, const int *par, int b) {
    int st[HV_MAXN], k = 0; for (int x = b; x >= 0; x = par[x]) st[k++] = x;
    Sx *p = dc_form("Path", NULL); while (k) sx_push(p, hv_node(m, h, st[--k])); return p;
}
static Sx *hv_completehive(DcRun *r, const Sx *q) {
    DcModule *m = r->m; Hive *h = &g_h; char why[300]; int ovf = 0; static int par[HV_MAXN][HV_MAXN];
    if (q->n != 2) return dc_invalid(m, "CompleteHive: expected (CompleteHive Hive)");
    int rc = hv_load(m, q->items[1], h, why, sizeof why);
    if (rc == -2) return dc_unsupported(m, "CompleteHive: %s", why);
    if (rc) return dc_invalid(m, "CompleteHive: %s", why);
    for (int a = 0; a < h->nn; a++) hv_bfs(h, a, par[a]);
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++) if (h->H[a][b] == 0 && par[a][b] != -2) {
        char pb[200]; int st[HV_MAXN], k = 0, o = 0; for (int x = b; x >= 0; x = par[a][x]) st[k++] = x;
        while (k && o < (int)sizeof pb - 24) { int x = st[--k]; o += snprintf(pb + o, sizeof pb - o, "%s%s[%d]", o ? " " : "", h->mem[h->mof[x]].name, h->vof[x]); }
        return dc_unsupported(m, "CompleteHive %s: the measured entry between %s[%d] and %s[%d] is 0 but the measured path %s identifies them; the measured correspondences are not Lipschitz and round-trip coherent, so no coherent completion keeps them (spec l.2902)",
                              h->name, h->mem[h->mof[a]].name, h->vof[a], h->mem[h->mof[b]].name, h->vof[b], pb);
    }
    DcRat cost = rq(0, 1); int nfill = 0, nunm = 0;
    Sx *fill = dc_form("Filled", NULL), *nop = dc_form("NoPaths", NULL);
    for (int a = 0; a < h->nn; a++) for (int b = 0; b < h->nn; b++) if (h->H[a][b] < 0) {
        nunm++;
        if (par[a][b] != -2) { cost = dc_rat_add(cost, dc_rat_mul(h->w[a], h->w[b], &ovf), &ovf); if (a < b) { sx_push(fill, dc_form("Fill", hv_node(m, h, a), hv_node(m, h, b), hv_path(m, h, par[a], b), NULL)); nfill++; } }
    }
    for (int i = 0; i < h->nm; i++) for (int j = i + 1; j < h->nm; j++) {
        int A = h->mem[i].base, B = h->mem[j].base; if (h->H[A][B] >= 0) continue;
        int any = 0; for (int l = 0; l < h->mem[i].nv; l++) for (int r2 = 0; r2 < h->mem[j].nv; r2++) if (par[A + l][B + r2] != -2) any = 1;
        if (!any) sx_push(nop, dc_form("NoPath", dc_sym(h->mem[i].name), dc_sym(h->mem[j].name), NULL));
    }
    if (ovf) return dc_unsupported(m, "CompleteHive: rational overflow");
    Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Method", dc_sym("PathComposition"), NULL), dc_form("Optimality", dc_sym("Checked"), NULL),
                     dc_form("UnmeasuredEntries", dc_int(nunm), NULL), fill, nop, NULL), NULL);
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), hv_subj(h), dc_form("Value", rsx(cost), NULL), ev, NULL);
}
/* M6-rest: (Associator Hive Mi Mj Mk) (request shape ours, m6rest patch; definition spec Def 10.1 l.2827:
 * [i, j, k] = c_ik - c_ij o c_jk, crisp kernels, o the Boolean relational composite as in Holonomy).
 * Value lists every entry (a c direct composite difference) over V_i x V_k; (Zero True) iff the direct
 * correspondence equals the path-induced one.  Unmeasured entries answer Unsupported (complete them first). */
static Sx *hv_assoc(DcRun *r, const Sx *q) {
    DcModule *m = r->m; Hive *h = &g_h; char why[300]; int mi[3];
    if (q->n != 5) return dc_invalid(m, "Associator: expected (Associator Hive Mi Mj Mk)");
    int rc = hv_load(m, q->items[1], h, why, sizeof why);
    if (rc == -2) return dc_unsupported(m, "Associator: %s", why);
    if (rc) return dc_invalid(m, "Associator: %s", why);
    for (int t = 0; t < 3; t++)
        if (q->items[t + 2]->kind != SX_SYM || (mi[t] = hv_mem(h, q->items[t + 2]->text)) < 0) return dc_invalid(m, "Associator: argument %d is not a member of %s", t + 2, h->name);
    if (mi[0] == mi[1] || mi[1] == mi[2] || mi[0] == mi[2]) return dc_invalid(m, "Associator: the three members must be distinct");
    const HvMem *I = &h->mem[mi[0]], *J = &h->mem[mi[1]], *K = &h->mem[mi[2]];
    for (int a = 0; a < I->nv + J->nv; a++) for (int c = 0; c < J->nv + K->nv; c++) {
        int x = a < I->nv ? I->base + a : J->base + a - I->nv, y = c < J->nv ? (a < I->nv ? J->base + c : -1) : K->base + c - J->nv;
        if (y >= 0 && h->H[x][y] < 0) return dc_unsupported(m, "Associator %s: an entry between %s and %s is Unmeasured or undeclared; complete it first with (CompleteHive %s)", h->name, h->mem[h->mof[x]].name, h->mem[h->mof[y]].name, h->name);
    }
    for (int a = 0; a < I->nv; a++) for (int c = 0; c < K->nv; c++) if (h->H[I->base + a][K->base + c] < 0)
        return dc_unsupported(m, "Associator %s: an entry between %s and %s is Unmeasured or undeclared; complete it first with (CompleteHive %s)", h->name, I->name, K->name, h->name);
    Sx *E = dc_form("Entries", NULL); int zero = 1, npos = 0, nneg = 0;
    for (int a = 0; a < I->nv; a++) for (int c = 0; c < K->nv; c++) {
        int d = h->H[I->base + a][K->base + c], comp = 0;
        for (int b = 0; b < J->nv; b++) comp |= h->H[I->base + a][J->base + b] && h->H[J->base + b][K->base + c];
        if (d != comp) { zero = 0; if (d > comp) npos++; else nneg++; }
        sx_push(E, dc_form("Entry", sx_copy(m->car[I->car].elems[a]), sx_copy(m->car[K->car].elems[c]), dc_int(d), dc_int(comp), dc_int(d - comp), NULL));
    }
    Sx *val = dc_form("Associator", dc_form("Members", dc_sym(I->name), dc_sym(J->name), dc_sym(K->name), NULL), E,
                      dc_form("Zero", dc_sym(zero ? "True" : "False"), NULL), dc_form("Positive", dc_int(npos), NULL), dc_form("Negative", dc_int(nneg), NULL), NULL);
    return dc_envelope(m, VERDICT_HOLDS, 1, dc_claim_of(q, "Literal"), hv_subj(h), dc_form("Value", val, NULL),
                       dc_form("Evidence", dc_form("Composition", dc_form("Path", dc_sym(I->name), dc_sym(J->name), dc_sym(K->name), NULL), NULL), NULL), NULL);
}
Sx *dc_req_hives(DcRun *r, const Sx *q, const char *h) {
    if (!strcmp(h, "CheckKernelCoherence")) return hv_coh(r, q);
    if (!strcmp(h, "Holonomy")) return hv_hol(r, q);
    if (!strcmp(h, "ConsensusCost")) return hv_cost(r, q);
    if (!strcmp(h, "LeastCoherentRefinement")) return hv_lcr(r, q);
    if (!strcmp(h, "CompleteHive")) return hv_completehive(r, q);   /* M6-rest */
    if (!strcmp(h, "Associator")) return hv_assoc(r, q);   /* M6-rest */
    return dc_unsupported(r->m, "%s is outside the M6 Hives subset", h);
}
