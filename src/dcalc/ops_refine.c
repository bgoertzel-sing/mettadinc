/* M2 crisp layer: Refine (coarsest stable refinement, spec Thm 4.14) with its
 * weakness ledger (sum of mu(B)^2 under a declared law, spec l1439-1445), and
 * SamePartition.  P0 = ker q ∩ K_O: two states start together when their codes
 * are at distance 0 and their observations are at distance 0. */
#include "graded.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* One round: nx[i] = the first j <= i with cls[j] == cls[i] and, for every
 * action, cls[Ta j] == cls[Ta i].  Labels are block minima, so they stay canonical. */
typedef struct { const int *t[4]; size_t n; } DcMerges;   /* merge tables, index a*n+b */
static int refine_round(const DcView *v, const DcMerges *mg, const int *cls, int *nx) {
    size_t n = v->n; int changed = 0;
    for (size_t i = 0; i < n; i++) {
        nx[i] = (int)i;
        for (size_t j = 0; j < i; j++) {
            if (cls[j] != cls[i]) continue;
            int ok = 1;
            for (size_t a = 0; a < v->nact && ok; a++) if (cls[v->act[a][j]] != cls[v->act[a][i]]) ok = 0;
            /* merge congruence, one argument at a time (enough for an equivalence) */
            for (size_t p = 0; mg && p < mg->n && ok; p++) for (size_t y = 0; y < n && ok; y++)
                if (cls[mg->t[p][j * n + y]] != cls[mg->t[p][i * n + y]] || cls[mg->t[p][y * n + j]] != cls[mg->t[p][y * n + i]]) ok = 0;
            if (ok) { nx[i] = (int)j; break; }
        }
        if (nx[i] != cls[i]) changed = 1;
    }
    return changed;
}
/* Initial partition P0 from zero sets of the seed and the code distance. */
static void initial_blocks(size_t n, const DcRat *d0, const DcRat *dq, int *cls) {
    for (size_t i = 0; i < n; i++) {
        cls[i] = (int)i;
        for (size_t j = 0; j < i; j++)
            if (dc_rat_is_zero(d0[j * n + i]) && dc_rat_is_zero(dq[j * n + i])) { cls[i] = cls[j]; break; }
    }
}
/* Coarsest stable refinement of cls in place; returns the number of strict rounds. */
static int refine_stable_m(const DcView *v, const DcMerges *mg, int *cls) {
    size_t n = v->n; int *nx = malloc((n ? n : 1) * sizeof *nx), rounds = 0;
    while (refine_round(v, mg, cls, nx)) { memcpy(cls, nx, n * sizeof *cls); rounds++; }
    free(nx); return rounds;
}
int dc_refine_stable(const DcView *v, int *cls) { return refine_stable_m(v, NULL, cls); }
/* Weakness under the uniform law: sum over blocks of (|B|/n)^2. */
static DcRat weakness_uniform(size_t n, const int *cls, int *ovf) {
    DcRat w = {0, 1};
    for (size_t b = 0; b < n; b++) {
        if (cls[b] != (int)b) continue;
        int64_t k = 0; for (size_t i = 0; i < n; i++) if (cls[i] == (int)b) k++;
        w = dc_rat_add(w, dc_rat(k * k, (int64_t)(n * n), ovf), ovf);
    }
    return w;
}
Sx *dc_blocks_sx(const DcCarrier *S, size_t n, const int *cls, const char *head) {
    Sx *p = dc_form(head, NULL);
    for (size_t b = 0; b < n; b++) {
        if (cls[b] != (int)b) continue;
        Sx *B = dc_form("Block", NULL);
        for (size_t i = 0; i < n; i++) if (cls[i] == (int)b) sx_push(B, sx_copy(S->elems[i]));
        sx_push(p, B);
    }
    return p;
}
static Sx *rs(DcRat r) { char b[48]; dc_rat_str(r, b, sizeof b); return dc_sym(b); }

/* ---- Splitting tree (spec Def 4.11, Prop 4.12) ----
 * Root X.  An internal node carries a test (word w, query j); its children are the
 * classes of o_j o T_w on the node (zero distance under the query's tolerance; the
 * query Encoding is the code q under its tolerance).  Letters are the actions and, on a
 * machine with Merge ports, the one-argument contexts x -> m(x,y) (MergeLeft m y) and
 * x -> m(y,x) (MergeRight m y).  A leaf whose successors under letter a meet two leaves
 * is split by (a.w, j), where (w, j) is the test of the lowest node above those leaves.
 * At the end the leaves are stable, and every two leaves are separated by a test, so the
 * leaves are the coarsest stable partition refining the initial tests. */
typedef struct { int parent, depth, q, wl, nch; int *w, *ch; } TNode;
typedef struct { const DcView *v; const DcMerges *mg; size_t n, nlet; int nq, enc; int *lab; TNode *t; int nt, cap; int *leaf; } STree;

static int st_apply(const STree *T, int l, int x) {
    size_t na = T->v->nact, n = T->n;
    if ((size_t)l < na) return T->v->act[l][x];
    size_t r = (size_t)l - na, p = r / (2 * n), side = (r / n) % 2, y = r % n;
    return side == 0 ? T->mg->t[p][(size_t)x * n + y] : T->mg->t[p][y * n + (size_t)x];
}
static int st_eval(const STree *T, int q, const int *w, int wl, int x) {
    for (int i = 0; i < wl; i++) x = st_apply(T, w[i], x);
    return T->lab[(size_t)q * T->n + (size_t)x];
}
static int st_node(STree *T, int parent) {
    if (T->nt == T->cap) {
        int c = T->cap ? 2 * T->cap : 16; TNode *t = realloc(T->t, (size_t)c * sizeof *t);
        if (!t) return -1;
        T->t = t; T->cap = c;
    }
    TNode *N = &T->t[T->nt]; memset(N, 0, sizeof *N);
    N->parent = parent; N->depth = parent < 0 ? 0 : T->t[parent].depth + 1; N->q = -1;
    return T->nt++;
}
/* Splits leaf L by the test (q, w); owns w.  Returns the number of children,
 * 0 when the test does not split L, -1 on allocation failure. */
static int st_split(STree *T, int L, int q, int *w, int wl) {
    size_t n = T->n; int nv = 0;
    int *sv = malloc((n ? n : 1) * sizeof *sv), *vals = malloc((n ? n : 1) * sizeof *vals);
    if (!sv || !vals) { free(sv); free(vals); free(w); return -1; }
    for (size_t x = 0; x < n; x++) {
        if (T->leaf[x] != L) continue;
        int e = st_eval(T, q, w, wl, (int)x), k = 0;
        while (k < nv && vals[k] != e) k++;
        if (k == nv) vals[nv++] = e;
        sv[x] = k;
    }
    if (nv < 2) { free(sv); free(vals); free(w); return 0; }
    int *ch = malloc((size_t)nv * sizeof *ch);
    if (!ch) { free(sv); free(vals); free(w); return -1; }
    for (int k = 0; k < nv; k++) if ((ch[k] = st_node(T, L)) < 0) { free(sv); free(vals); free(w); free(ch); return -1; }
    TNode *N = &T->t[L]; N->q = q; N->w = w; N->wl = wl; N->ch = ch; N->nch = nv;
    for (size_t x = 0; x < n; x++) if (T->leaf[x] == L) T->leaf[x] = ch[sv[x]];
    free(sv); free(vals); return nv;
}
static int st_lca(const STree *T, int a, int b) {
    while (T->t[a].depth > T->t[b].depth) a = T->t[a].parent;
    while (T->t[b].depth > T->t[a].depth) b = T->t[b].parent;
    while (a != b) { a = T->t[a].parent; b = T->t[b].parent; }
    return a;
}
static Sx *st_letter_sx(const DcModule *m, const STree *T, int mi, const DcCarrier *S, int l) {
    size_t na = T->v->nact, n = T->n;
    if ((size_t)l < na) return dc_form("Do", dc_sym(T->v->act_label[l]), NULL);
    size_t r = (size_t)l - na, p = r / (2 * n), side = (r / n) % 2, y = r % n;
    return dc_form(side == 0 ? "MergeLeft" : "MergeRight", dc_sym(m->mach[mi].merge[p].label), sx_copy(S->elems[y]), NULL);
}
static Sx *st_sx(const DcModule *m, const STree *T, int mi, const DcCarrier *S, int i) {
    const TNode *N = &T->t[i];
    if (!N->nch) {
        Sx *B = dc_form("Block", NULL);
        for (size_t x = 0; x < T->n; x++) if (T->leaf[x] == i) sx_push(B, sx_copy(S->elems[x]));
        return dc_form("Leaf", B, NULL);
    }
    Sx *w = dc_form("Word", NULL);
    for (int k = 0; k < N->wl; k++) sx_push(w, st_letter_sx(m, T, mi, S, N->w[k]));
    const char *qn = T->enc && N->q == 0 ? "Encoding" : T->v->obs_label[N->q - T->enc];
    Sx *r = dc_form("Node", dc_form("Test", w, dc_form("Query", dc_sym(qn), NULL), NULL), NULL);
    for (int c = 0; c < N->nch; c++) sx_push(r, st_sx(m, T, mi, S, N->ch[c]));
    return r;
}
/* Builds the tree; dq == NULL: queries only (MinimizeForQueries).  cls gets block minima.
 * Returns (Tree root), or NULL on failure. */
static Sx *split_tree(const DcModule *m, const DcView *v, const DcMerges *mg, int mi, const DcRat *dq, int *cls) {
    STree T; memset(&T, 0, sizeof T); size_t n = v->n;
    T.v = v; T.mg = mg; T.n = n; T.enc = dq != NULL; T.nq = (int)v->nobs + T.enc;
    T.nlet = v->nact + (mg ? 2 * mg->n * n : 0);
    T.lab = malloc((size_t)(T.nq ? T.nq : 1) * (n ? n : 1) * sizeof *T.lab); T.leaf = calloc(n ? n : 1, sizeof *T.leaf);
    int ovf = 0, bad = !T.lab || !T.leaf || st_node(&T, -1) < 0;
    for (int q = 0; q < T.nq && !bad; q++) for (size_t x = 0; x < n; x++) {
        int l = (int)x;
        for (size_t y = 0; y < x; y++) {
            int z;
            if (T.enc && q == 0) z = dc_rat_is_zero(dq[y * n + x]);
            else {
                size_t k = (size_t)(q - T.enc); int a = v->obs[k][y], b = v->obs[k][x];
                z = v->obs_tol[k] >= 0 ? dc_rat_is_zero(dc_tol_dist(m, v->obs_tol[k], a, b, &ovf)) : a == b;
            }
            if (z) { l = T.lab[(size_t)q * n + y]; break; }
        }
        T.lab[(size_t)q * n + x] = l;
    }
    for (int q = 0; q < T.nq && !bad; q++) {
        int nt = T.nt;
        for (int L = 0; L < nt && !bad; L++) if (!T.t[L].nch && st_split(&T, L, q, NULL, 0) < 0) bad = 1;
    }
    for (int changed = 1; changed && !bad; ) {
        changed = 0;
        for (int L = 0; L < T.nt && !bad; L++) {
            if (T.t[L].nch) continue;
            for (size_t l = 0; l < T.nlet && !bad; l++) {
                int first = -1, anc = -1, split = 0;
                for (size_t x = 0; x < n; x++) if (T.leaf[x] == L) {
                    int s2 = T.leaf[st_apply(&T, (int)l, (int)x)];
                    if (first < 0) first = anc = s2;
                    else if (s2 != first) { split = 1; anc = st_lca(&T, anc, s2); }
                }
                if (!split) continue;
                int wl = T.t[anc].wl + 1, q = T.t[anc].q, *w = malloc((size_t)wl * sizeof *w);
                if (!w) { bad = 1; break; }
                w[0] = (int)l; if (wl > 1) memcpy(w + 1, T.t[anc].w, (size_t)(wl - 1) * sizeof *w);
                if (st_split(&T, L, q, w, wl) < 2) bad = 1;
                changed = 1; break;   /* L is now internal */
            }
        }
    }
    Sx *res = NULL;
    if (!bad && !ovf) {
        for (size_t x = 0; x < n; x++) { cls[x] = (int)x; for (size_t y = 0; y < x; y++) if (T.leaf[y] == T.leaf[x]) { cls[x] = (int)y; break; } }
        res = dc_form("Tree", st_sx(m, &T, mi, &m->car[v->states], 0), NULL);
    }
    for (int i = 0; i < T.nt; i++) { free(T.t[i].w); free(T.t[i].ch); }
    free(T.t); free(T.lab); free(T.leaf); return res;
}

/* (Refine Rep (Preserve Encoding) (Until Stable) [(Under Law)]) */
Sx *dc_req_refine(DcRun *run, const Sx *q, int slot) {
    DcModule *m = run->m;
    if (q->n < 2 || q->items[1]->kind != SX_SYM) return dc_invalid(m, "Refine: field Representation missing or not a name");
    const char *nm = q->items[1]->text; int ri = dc_find_repr(m, nm);
    if (ri < 0) return dc_declared_unsupported(m, nm) ? dc_unsupported(m, "Refine: Representation %s is outside the M2 fragment", nm)
                                                      : dc_invalid(m, "Refine: field Representation names no declared representation (%s)", nm);
    int pres = 0, until = 0, law = -1;
    for (size_t i = 2; i < q->n; i++) {
        const Sx *f = q->items[i];
        if (sx_head_is(f, "Preserve") && f->n == 2 && sx_is_sym(f->items[1], "Encoding") && !pres) { pres = 1; continue; }
        if (sx_head_is(f, "Until") && f->n == 2 && sx_is_sym(f->items[1], "Stable") && !until) { until = 1; continue; }
        if (sx_head_is(f, "Under") && f->n == 2 && f->items[1]->kind == SX_SYM && law < 0) {
            law = dc_find_meas(m, f->items[1]->text);
            if (law < 0) return dc_declared_unsupported(m, f->items[1]->text) ? dc_unsupported(m, "Refine: law %s is outside the M2 fragment", f->items[1]->text)
                                                                             : dc_invalid(m, "Refine: field Under names no declared law (%s)", f->items[1]->text);
            continue;
        }
        return dc_invalid(m, "Refine: field %zu is not (Preserve Encoding), (Until Stable) or (Under Law)", i - 1);
    }
    if (!pres || !until) return dc_invalid(m, "Refine: (Preserve Encoding) and (Until Stable) are required");
    const DcRepr *R = &m->rep[ri];
    if (law >= 0 && m->meas[law].on != m->mach[R->machine].states) return dc_invalid(m, "Refine: law %s is not on the state carrier", m->meas[law].name);
    DcView v; dc_view_of_machine(m, R->machine, &v); size_t n = v.n, N = n ? n * n : 1;
    if (n > 256) { dc_view_free(&v); return dc_unsupported(m, "Refine: more than 256 states is outside the M2 table engine"); }
    DcRat *d0 = calloc(N, sizeof *d0), *dq = calloc(N, sizeof *dq);
    int *p0 = malloc((n ? n : 1) * sizeof *p0), *cls = malloc((n ? n : 1) * sizeof *cls), ovf = 0;
    if (dc_g_seed(m, &v, d0) || dc_g_codes(m, ri, dq)) ovf = 1;
    initial_blocks(n, d0, dq, p0); memcpy(cls, p0, n * sizeof *cls);
    DcMerges mg; memset(&mg, 0, sizeof mg);
    for (size_t p = 0; p < m->mach[R->machine].nmerge; p++) mg.t[mg.n++] = m->map[m->mach[R->machine].merge[p].map].table;
    int rounds = refine_stable_m(&v, &mg, cls);
    const DcCarrier *S = &m->car[v.states];
    Sx *val = dc_form("Refinement", dc_form("Representation", dc_sym(slot >= 0 ? m->der[slot].name : "?"), NULL),
                      dc_blocks_sx(S, n, cls, "Partition"), NULL);
    if (law >= 0)
        sx_push(val, dc_form("Ledger", dc_form("Under", dc_sym(m->meas[law].name), NULL),
                             dc_form("Before", rs(weakness_uniform(n, p0, &ovf)), NULL),
                             dc_form("After", rs(weakness_uniform(n, cls, &ovf)), NULL), NULL));
    /* certificate: a splitting tree, built independently of the round refinement and cross-checked */
    int *tc = malloc((n ? n : 1) * sizeof *tc); Sx *tree = tc ? split_tree(m, &v, &mg, R->machine, dq, tc) : NULL; (void)rounds;
    int tree_ok = tree != NULL;
    for (size_t i = 0; i < n && tree_ok; i++) if (tc[i] != cls[i]) tree_ok = 0;
    free(tc);
    Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("SplittingTree"), NULL), tree ? tree : dc_form("Tree", NULL), NULL), NULL);
    /* self-check before reporting: the result is stable and refines P0 */
    int *chk = malloc((n ? n : 1) * sizeof *chk), rep = !refine_round(&v, &mg, cls, chk);
    for (size_t i = 0; i < n && rep; i++) if (p0[cls[i]] != p0[i]) rep = 0;
    if (!tree_ok) rep = 0;
    free(chk); free(d0); free(dq); free(p0); free(cls); dc_view_free(&v);
    if (ovf) { sx_free(val); sx_free(ev); return dc_unsupported(m, "Refine: a rational left the 64-bit exact range"); }
    DcScope sc = {"M2-GradedDeterministic", -1, ""};
    Sx *subj = dc_form("Subject", dc_form("Representation", dc_sym(nm), NULL), dc_form("Machine", dc_sym(m->mach[R->machine].name), NULL), NULL);
    return dc_envelope_scoped(m, VERDICT_HOLDS, rep, dc_claim_of(q, "Literal"), subj, dc_form("Value", val, NULL), ev, NULL, &sc);
}

/* (SamePartition (Output D Representation) Rep2): the Partition of a Checked
 * Refinement equals the kernel of Rep2's encoding (E07). */
static int blocks_to_cls(const DcCarrier *S, const Sx *P, int *cls) {
    size_t n = S->n; for (size_t i = 0; i < n; i++) cls[i] = -1;
    for (size_t b = 1; b < P->n; b++) {
        const Sx *B = P->items[b]; if (!sx_head_is(B, "Block") || B->n < 2) return -1;
        int first = -1;
        for (size_t k = 1; k < B->n; k++) {
            int i = dc_carrier_index(S, B->items[k]); if (i < 0 || cls[i] >= 0) return -1;
            if (first < 0) first = i;
            cls[i] = first;
        }
    }
    for (size_t i = 0; i < n; i++) if (cls[i] < 0) return -1;
    return 0;
}
Sx *dc_req_same_partition(DcRun *run, const Sx *q) {
    DcModule *m = run->m;
    if (q->n != 3) return dc_invalid(m, "SamePartition: expected (SamePartition (Output D Representation) Representation)");
    const Sx *o = q->items[1];
    if (!sx_head_is(o, "Output") || o->n != 3 || o->items[1]->kind != SX_SYM || !sx_is_sym(o->items[2], "Representation"))
        return dc_invalid(m, "SamePartition: field 1 expects (Output D Representation)");
    int d = dc_find_derive(m, o->items[1]->text);
    if (d < 0) return dc_invalid(m, "SamePartition: names no declared Derive (%s)", o->items[1]->text);
    const Sx *pr = dc_run_derive(run, d);
    if (!pr) return dc_invalid(m, "SamePartition: Derive %s: cyclic reference", o->items[1]->text);
    DcStatus st = dc_result_status(pr);
    if (st == DC_UNSUPPORTED) return dc_unsupported(m, "SamePartition: premise Derive %s is outside the M2 fragment", o->items[1]->text);
    if (st != DC_CHECKED) return dc_invalid(m, "SamePartition: Output projects only from Checked results (Derive %s is %s)", o->items[1]->text, dc_status_name(st));
    const Sx *val = sx_find(pr, "Value", 1), *rf = val && val->n == 2 ? val->items[1] : NULL;
    const Sx *part = rf && sx_head_is(rf, "Refinement") ? sx_find(rf, "Partition", 1) : NULL;
    if (!part) return dc_invalid(m, "SamePartition: Derive %s has no Representation output", o->items[1]->text);
    if (q->items[2]->kind != SX_SYM) return dc_invalid(m, "SamePartition: field 2 is not a Representation name");
    const char *nm = q->items[2]->text; int ri = dc_find_repr(m, nm);
    if (ri < 0) return dc_declared_unsupported(m, nm) ? dc_unsupported(m, "SamePartition: Representation %s is outside the M2 fragment", nm)
                                                      : dc_invalid(m, "SamePartition: names no declared representation (%s)", nm);
    const Sx *subj0 = sx_find(sx_find(pr, "Binding", 1), "Subject", 1);
    const Sx *mrow = subj0 ? sx_find(subj0, "Machine", 1) : NULL;
    const char *mach = m->mach[m->rep[ri].machine].name;
    if (!mrow || mrow->n != 2 || !sx_is_sym(mrow->items[1], mach))
        return dc_invalid(m, "SamePartition: Binding mismatch: field Machine of Derive %s is not %s", o->items[1]->text, mach);
    const DcCarrier *S = &m->car[m->mach[m->rep[ri].machine].states]; size_t n = S->n;
    int *a = malloc((n ? n : 1) * sizeof *a), *b = malloc((n ? n : 1) * sizeof *b);
    if (blocks_to_cls(S, part, a)) { free(a); free(b); return dc_invalid(m, "SamePartition: the Representation output of %s is not a partition of %s", o->items[1]->text, S->name); }
    const int *enc = m->map[m->rep[ri].encode].table; int wx = -1, wy = -1;
    for (size_t i = 0; i < n; i++) { b[i] = (int)i; for (size_t j = 0; j < i; j++) if (enc[j] == enc[i]) { b[i] = b[j]; break; } }
    for (size_t i = 0; i < n && wx < 0; i++) for (size_t j = 0; j < i; j++) if ((a[i] == a[j]) != (b[i] == b[j])) { wx = (int)j; wy = (int)i; break; }
    Sx *ev;
    if (wx < 0) ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("rule"), NULL), dc_form("Rule", dc_sym("SamePartition"), NULL), dc_blocks_sx(S, n, b, "Blocks"), NULL), NULL);
    else ev = dc_form("Evidence", dc_form("Witness", dc_form("PartitionWitness", dc_form("Pair", sx_copy(S->elems[wx]), sx_copy(S->elems[wy]), NULL),
                      dc_form("Left", dc_sym(a[wx] == a[wy] ? "Same" : "Different"), NULL), dc_form("Right", dc_sym(b[wx] == b[wy] ? "Same" : "Different"), NULL), NULL), NULL), NULL);
    free(a); free(b);
    DcScope sc = {"M2-GradedDeterministic", -1, ""};
    Sx *subj = dc_form("Subject", dc_form("Partition", dc_sym(o->items[1]->text), NULL), dc_form("Representation", dc_sym(nm), NULL), dc_form("Machine", dc_sym(mach), NULL), NULL);
    return dc_envelope_scoped(m, wx < 0 ? VERDICT_HOLDS : VERDICT_FAILS, 1, dc_claim_of(q, "Literal"), subj,
                              dc_form("Value", dc_form("Verdict", dc_form("Holds", dc_sym(wx < 0 ? "True" : "False"), NULL), NULL), NULL), ev, NULL, &sc);
}
