/* M2: WeakestWithin (spec Section 4.7).  Over every partition of a machine's
 * states (an exhaustive search, enumerated as restricted growth strings), the
 * defect of a partition is its behavioral diameter max{d_beh^g(x,y) : x ~ y}
 * and its weakness under the uniform law is sum_B (|B|/n)^2.  The answer is the
 * first partition in enumeration order of largest weakness whose defect is
 * within the bound; its optimality is Checked because the search is exhaustive. */
#include "graded.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define DC_WEAKEST_MAX_STATES 10
static Sx *rs(DcRat r) { char b[48]; dc_rat_str(r, b, sizeof b); return dc_sym(b); }

static int next_rgs(int *a, size_t n) {
    for (size_t i = n; i-- > 1;) {
        int mx = 0; for (size_t j = 0; j < i; j++) if (a[j] > mx) mx = a[j];
        if (a[i] <= mx) { a[i]++; for (size_t j = i + 1; j < n; j++) a[j] = 0; return 1; }
    }
    return 0;
}

Sx *dc_req_weakest(DcRun *run, const Sx *q, int slot) {
    DcModule *m = run->m;
    if (q->n < 2 || q->items[1]->kind != SX_SYM) return dc_invalid(m, "WeakestWithin: field Machine missing or not a name");
    const char *mn = q->items[1]->text; int mi = dc_find_machine(m, mn);
    if (mi < 0) return dc_declared_unsupported(m, mn) ? dc_unsupported(m, "WeakestWithin: Machine %s is outside the M2 fragment", mn)
                                                      : dc_invalid(m, "WeakestWithin: field Machine names no declared machine (%s)", mn);
    DcRat bound = {0, 1}, g = {1, 1}; int hw = 0, hk = 0, hs = 0, law = -1; char gtxt[48] = "";
    for (size_t i = 2; i < q->n; i++) {
        const Sx *f = q->items[i];
        if (sx_head_is(f, "Within") && f->n == 2 && !hw && !dc_sx_rat(f->items[1], &bound) && bound.n >= 0) { hw = 1; continue; }
        if (sx_head_is(f, "Kind") && f->n == 2 && f->items[1]->kind == SX_SYM && !hk) {
            if (strcmp(f->items[1]->text, "Behavioral")) return dc_unsupported(m, "WeakestWithin: defect kind %s is outside the M2 fragment", f->items[1]->text);
            hk = 1; continue; }
        if (sx_head_is(f, "Discount") && f->n == 2 && !gtxt[0] && !dc_sx_rat(f->items[1], &g) && g.n > 0 && g.n <= g.d) { dc_rat_str(g, gtxt, sizeof gtxt); continue; }
        if (sx_head_is(f, "Under") && f->n == 2 && f->items[1]->kind == SX_SYM && law < 0) {
            law = dc_find_meas(m, f->items[1]->text);
            if (law < 0) return dc_declared_unsupported(m, f->items[1]->text) ? dc_unsupported(m, "WeakestWithin: law %s is outside the M2 fragment", f->items[1]->text)
                                                                             : dc_invalid(m, "WeakestWithin: field Under names no declared law (%s)", f->items[1]->text);
            continue; }
        if (sx_head_is(f, "Search") && f->n == 2 && f->items[1]->kind == SX_SYM && !hs) {
            if (strcmp(f->items[1]->text, "Exhaustive")) return dc_unsupported(m, "WeakestWithin: search %s is outside the M2 fragment", f->items[1]->text);
            hs = 1; continue; }
        return dc_invalid(m, "WeakestWithin: field %zu is not (Within b), (Kind k), (Discount g), (Under law) or (Search s) with a valid value", i - 1);
    }
    if (!hw || !hk || law < 0 || !hs) return dc_invalid(m, "WeakestWithin: (Within b), (Kind Behavioral), (Under law) and (Search Exhaustive) are required");
    if (m->meas[law].on != m->mach[mi].states) return dc_invalid(m, "WeakestWithin: law %s is not on the state carrier", m->meas[law].name);
    DcView v; dc_view_of_machine(m, mi, &v); size_t n = v.n;
    if (n > DC_WEAKEST_MAX_STATES) { dc_view_free(&v); return dc_unsupported(m, "WeakestWithin: exhaustive search over more than %d states is outside the M2 table engine", DC_WEAKEST_MAX_STATES); }
    size_t N = n ? n * n : 1; int ovf = 0, agree = 1;
    DcRat *d0 = calloc(N, sizeof *d0), *bf = calloc(N, sizeof *bf), *rf = calloc(N, sizeof *rf);
    if (dc_g_seed(m, &v, d0) || dc_g_beh_bfs(&v, d0, g, -1, bf) || dc_g_beh_ref(&v, d0, g, -1, rf)) ovf = 1;
    for (size_t i = 0; i < n * n; i++) if (dc_rat_cmp(bf[i], rf[i])) agree = 0;
    int a[DC_WEAKEST_MAX_STATES] = {0}, best[DC_WEAKEST_MAX_STATES] = {0}; long bestsq = -1, count = 0; DcRat bestd = {0, 1};
    do {
        count++; DcRat diam = {0, 1}; long sq = 0;
        for (size_t i = 0; i < n; i++) for (size_t j = i + 1; j < n; j++) if (a[i] == a[j]) diam = dc_rat_max(diam, bf[i * n + j]);
        for (int b = 0; b < (int)n; b++) { long k = 0; for (size_t i = 0; i < n; i++) if (a[i] == b) k++; sq += k * k; }
        if (dc_rat_cmp(diam, bound) <= 0 && sq > bestsq) { bestsq = sq; bestd = diam; memcpy(best, a, sizeof a); }
    } while (n && next_rgs(a, n));
    int cls[DC_WEAKEST_MAX_STATES];
    for (size_t i = 0; i < n; i++) { cls[i] = (int)i; for (size_t j = 0; j < i; j++) if (best[j] == best[i]) { cls[i] = (int)j; break; } }
    const DcCarrier *S = &m->car[v.states];
    char bt[48]; dc_rat_str(bound, bt, sizeof bt);
    Sx *val = dc_form("WeakestPartition", dc_form("Representation", dc_sym(slot >= 0 ? m->der[slot].name : "?"), NULL),
        dc_blocks_sx(S, n, cls, "Partition"), dc_form("Weakness", rs(dc_rat(bestsq, (int64_t)(n * n), &ovf)), NULL),
        dc_form("Defect", dc_form("Interval", rs(bestd), rs(bestd), NULL), NULL), dc_form("Bound", dc_sym(bt), NULL),
        dc_form("Kind", dc_sym("Behavioral"), NULL), dc_form("Under", dc_sym(m->meas[law].name), NULL),
        dc_form("Optimality", dc_sym("Checked"), NULL), NULL);
    Sx *ker = dc_form("Kernel", NULL);
    for (size_t x = 0; x < n; x++) for (size_t y = x + 1; y < n; y++)
        if (!dc_rat_is_zero(bf[x * n + y])) sx_push(ker, dc_form("Entry", sx_copy(S->elems[x]), sx_copy(S->elems[y]), rs(bf[x * n + y]), NULL));
    Sx *ev = dc_form("Evidence",
        dc_form("Certificate", dc_form("Kind", dc_sym("ExhaustiveSearch"), NULL), dc_form("Family", dc_sym("AllPartitions"), NULL),
                dc_form("Count", dc_int(count), NULL), NULL),
        dc_form("Certificate", dc_form("Kind", dc_sym("Prefixpoint"), NULL), dc_form("Discount", rs(g), NULL),
                dc_form("Horizon", dc_sym("Unbounded"), NULL), ker, NULL), NULL);
    free(d0); free(bf); free(rf); dc_view_free(&v);
    if (ovf) { sx_free(val); sx_free(ev); return dc_unsupported(m, "WeakestWithin: a rational left the 64-bit exact range"); }
    DcScope sc = {"M2-GradedDeterministic", -1, ""}; snprintf(sc.discount, sizeof sc.discount, "%s", gtxt);
    Sx *res = dc_envelope_scoped(m, VERDICT_HOLDS, agree, dc_claim_of(q, "Literal"), dc_form("Subject", dc_form("Machine", dc_sym(mn), NULL), NULL),
                                 dc_form("Value", val, NULL), ev, NULL, &sc);
    dc_result_bind_models(res, mn, mn);
    return res;
}
