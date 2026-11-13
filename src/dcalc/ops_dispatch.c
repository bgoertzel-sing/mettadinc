/* Request dispatcher and memoised Derive evaluation. */
#include "ops_internal.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static Sx *dispatch(DcRun *r, const Sx *q, int slot);

const Sx *dc_run_derive(DcRun *r, int slot) {
    if (r->memo[slot]) return r->memo[slot];
    if (r->busy[slot]) return NULL;   /* caller turns a cycle into InvalidInput */
    r->busy[slot] = 1;
    Sx *res = dispatch(r, r->m->der[slot].request, slot);
    r->busy[slot] = 0;
    r->memo[slot] = res;
    return res;
}

/* M0 request heads.  Every other head is reported as Unsupported. */
static Sx *dispatch(DcRun *r, const Sx *q, int slot) {
    DcModule *m = r->m;
    if (q->kind == SX_SYM) {
        int d = dc_find_derive(m, q->text);
        if (d < 0) return dc_invalid(m, "request: names no declared Derive (%s)", q->text);
        if (r->busy[d]) return dc_invalid(m, "Derive %s: cyclic reference", q->text);
        const Sx *res = dc_run_derive(r, d);
        return res ? sx_copy(res) : dc_invalid(m, "Derive %s: cyclic reference", q->text);
    }
    if (q->kind != SX_LIST || q->n == 0 || q->items[0]->kind != SX_SYM)
        return dc_invalid(m, "request: expected (Head args...) or a Derive name");
    const char *h = q->items[0]->text;
    if ((!strcmp(h, "EstimateRate") || !strcmp(h, "CompareRates") || !strcmp(h, "EstimateDupRate")) && !m->profile_unsupported[0]) return dc_req_estimates(r, q, h);   /* M4-estimates opt-in */
    if (!strcmp(h, "RatesSeparated") && !m->profile_unsupported[0]) return dc_req_separated(r, q);   /* review 1 F3 */
    if (m->stochastic && !m->profile_unsupported[0]) return dc_req_stoch(r, q, h, slot);   /* M4 opt-in */
    if (m->contracts && !m->profile_unsupported[0] && (!strcmp(h, "CheckImplementation") || !strcmp(h, "ThenContracts"))) return dc_req_contracts(r, q, h);   /* M6 opt-in */
    if (m->hives && !m->profile_unsupported[0] && (!strcmp(h, "CheckKernelCoherence") || !strcmp(h, "Holonomy") || !strcmp(h, "ConsensusCost") || !strcmp(h, "LeastCoherentRefinement") || !strcmp(h, "CompleteHive") || !strcmp(h, "Associator"))) return dc_req_hives(r, q, h);   /* M6 opt-in */
    if (m->transfers && !m->profile_unsupported[0] && (!strcmp(h, "CheckTransfer") || !strcmp(h, "CheckValuePullback") || !strcmp(h, "LibraryGap") || !strcmp(h, "ComposeTransfers") || !strcmp(h, "CheckTransferHive") || !strcmp(h, "KernelOf"))) return dc_req_transfers(r, q, h);   /* M6 opt-in */
    if (m->nondet && !m->profile_unsupported[0]) return dc_req_nondet(r, q, h, slot);   /* M5 opt-in */
    if (m->symbolic && !m->profile_unsupported[0]) return dc_req_sym(r, q, h, slot);   /* M3 */
    if (m->profile_unsupported[0]) return dc_unsupported(m, "request %s: %s", h, m->profile_unsupported);
    /* M2: graded heads, and the M0 heads on a graded representation */
    if (!strcmp(h, "PathClosure") || !strcmp(h, "Bracket") || !strcmp(h, "Delta") || !strcmp(h, "Threshold") || !strcmp(h, "CheckTransitive"))
        return dc_req_kernels(r, q, h, slot);
    if (!strcmp(h, "Refine")) return dc_req_refine(r, q, slot);
    if (!strcmp(h, "BehavioralTolerance")) return dc_req_beh_tol(r, q);
    if (!strcmp(h, "MinimizeForQueries")) return dc_req_minimize(r, q, slot);
    if (!strcmp(h, "SamePartition")) return dc_req_same_partition(r, q);
    if (!strcmp(h, "WeakestWithin")) return dc_req_weakest(r, q, slot);
    if (!strcmp(h, "InduceApprox")) return dc_req_induce_approx(r, q, slot);
    if (!strcmp(h, "Defects") || !strcmp(h, "MeasureUpdates") || !strcmp(h, "MeasureBehavioral") || !strcmp(h, "CheckBehavioral")
        || !strcmp(h, "MeasureTrace") || !strcmp(h, "CheckTrace"))
        return dc_req_graded(r, q, h);
    if ((!strcmp(h, "MeasureNow") || !strcmp(h, "CheckNow") || !strcmp(h, "CheckUpdates")) && q->n >= 2 && q->items[1]->kind == SX_SYM) {
        int ri = dc_find_repr(r->m, q->items[1]->text);
        if (ri >= 0 && dc_repr_graded(r->m, ri)) return dc_req_graded(r, q, h);
    }
    if (!strcmp(h, "MeasureNow")) return dc_req_measure_now(r, q);
    if (!strcmp(h, "CheckUpdates")) return dc_req_check_updates(r, q);
    if (!strcmp(h, "CheckNow")) return dc_req_check_now(r, q);
    if (!strcmp(h, "InduceExact")) return dc_req_induce_exact(r, q, slot);
    if (!strcmp(h, "CheckAbstractionMap")) return dc_req_check_abs(r, q, slot);
    if (!strcmp(h, "Then")) return dc_req_then(r, q, slot);
    return dc_unsupported(m, "request %s is outside the M0 fragment", h);
}

Sx *dc_run(DcRun *r, const Sx *q) {
    if (!q) return dc_invalid(r ? r->m : NULL, "request: missing");
    return dispatch(r, q, -1);
}
