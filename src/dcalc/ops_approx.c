/* M2: InduceApprox (spec Def 4.15, Prop 4.16).  The classes come from a Checked
 * premise with a Representation output (Refine, WeakestWithin).  A section r picks
 * one member per class: Center (least largest behavioral distance to the class,
 * ties by declaration order, the default), First, or (Choose map).  The induced
 * machine has observations o(r(C)) and updates C -> class of Ta r(C).  Radius
 * = max_x d_beh(x, r(qx)) on the concrete machine; defect = max_x d_beh(x, qx) on
 * the disjoint union, computed by both engines; a priori bound radius/(1-g) for
 * g < 1 (Prop 4.16(1)), Unbounded at g = 1. */
#include "graded.h"
#include "ops_run.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static Sx *rs(DcRat r) { char b[48]; dc_rat_str(r, b, sizeof b); return dc_sym(b); }

Sx *dc_req_induce_approx(DcRun *run, const Sx *q, int slot) {
    DcModule *m = run->m;
    if (q->n < 2) return dc_invalid(m, "InduceApprox: expected (InduceApprox (Output D Representation) ...)");
    const Sx *o = q->items[1];
    if (!sx_head_is(o, "Output") || o->n != 3 || o->items[1]->kind != SX_SYM || !sx_is_sym(o->items[2], "Representation"))
        return dc_invalid(m, "InduceApprox: field 1 expects (Output D Representation)");
    const char *dn = o->items[1]->text; int d = dc_find_derive(m, dn);
    if (d < 0) return dc_invalid(m, "InduceApprox: names no declared Derive (%s)", dn);
    const Sx *pr = dc_run_derive(run, d);
    if (!pr) return dc_invalid(m, "InduceApprox: Derive %s: cyclic reference", dn);
    DcStatus st = dc_result_status(pr);
    if (st == DC_UNSUPPORTED) return dc_unsupported(m, "InduceApprox: premise Derive %s is outside the M2 fragment", dn);
    if (st != DC_CHECKED) return dc_invalid(m, "InduceApprox: Output projects only from Checked results (Derive %s is %s)", dn, dc_status_name(st));
    const Sx *val = sx_find(pr, "Value", 1), *pv = val && val->n == 2 ? val->items[1] : NULL;
    const Sx *part = pv ? sx_find(pv, "Partition", 1) : NULL;
    if (!part) return dc_invalid(m, "InduceApprox: Derive %s has no Representation output", dn);
    const Sx *subj0 = sx_find(sx_find(pr, "Binding", 1), "Subject", 1);
    const Sx *mrow = subj0 ? sx_find(subj0, "Machine", 1) : NULL;
    if (!mrow || mrow->n != 2 || mrow->items[1]->kind != SX_SYM) return dc_invalid(m, "InduceApprox: Binding of Derive %s names no machine", dn);
    const char *mn = mrow->items[1]->text; int mi = dc_find_machine(m, mn);
    if (mi < 0) return dc_invalid(m, "InduceApprox: Binding mismatch: Derive %s names no admitted machine (%s)", dn, mn);
    int sel = 0, chmap = -1, hw = 0; DcRat g = {1, 1}, within = {0, 1}; char gtxt[48] = "", wtxt[48] = "0";
    for (size_t i = 2; i < q->n; i++) {
        const Sx *f = q->items[i];
        if (sx_head_is(f, "Representatives") && f->n == 2) {
            const Sx *s = f->items[1];
            if (sx_is_sym(s, "Center")) { sel = 0; continue; }
            if (sx_is_sym(s, "First")) { sel = 1; continue; }
            if (sx_head_is(s, "Choose") && s->n == 2 && s->items[1]->kind == SX_SYM && (chmap = dc_find_map(m, s->items[1]->text)) >= 0) { sel = 2; continue; }
        }
        if (sx_head_is(f, "Within") && f->n == 2 && !hw && !dc_sx_rat(f->items[1], &within) && within.n >= 0) { hw = 1; dc_rat_str(within, wtxt, sizeof wtxt); continue; }
        if (sx_head_is(f, "Discount") && f->n == 2 && !gtxt[0] && !dc_sx_rat(f->items[1], &g) && g.n > 0 && g.n <= g.d) { dc_rat_str(g, gtxt, sizeof gtxt); continue; }
        return dc_invalid(m, "InduceApprox: field %zu is not (Representatives Center|First|(Choose map)), (Within b) or (Discount g)", i - 1);
    }
    DcView v; dc_view_of_machine(m, mi, &v); size_t n = v.n;
    if (n > 256) { dc_view_free(&v); return dc_unsupported(m, "InduceApprox: more than 256 states is outside the M2 table engine"); }
    const DcCarrier *S = &m->car[v.states];
    if (sel == 2 && (m->map[chmap].from != v.states || m->map[chmap].to != v.states)) { dc_view_free(&v); return dc_invalid(m, "InduceApprox: section map %s is not from and to the states of %s", m->map[chmap].name, mn); }
    int *cls = malloc((n ? n : 1) * sizeof *cls), k = 0, bad = 0;
    for (size_t i = 0; i < n; i++) cls[i] = -1;
    for (size_t b = 1; b < part->n && !bad; b++, k++) {
        const Sx *B = part->items[b]; if (!sx_head_is(B, "Block") || B->n < 2) { bad = 1; break; }
        for (size_t j = 1; j < B->n; j++) { int i = dc_carrier_index(S, B->items[j]); if (i < 0 || cls[i] >= 0) { bad = 1; break; } cls[i] = k; }
    }
    for (size_t i = 0; i < n; i++) if (cls[i] < 0) bad = 1;
    if (bad) { free(cls); dc_view_free(&v); return dc_invalid(m, "InduceApprox: the Representation output of %s is not a partition of %s", dn, S->name); }
    size_t N = n ? n * n : 1; int ovf = 0;
    DcRat *d0 = calloc(N, sizeof *d0), *bf = calloc(N, sizeof *bf);
    if (dc_g_seed(m, &v, d0) || dc_g_beh_bfs(&v, d0, g, -1, bf)) ovf = 1;
    int *rep = malloc((k ? k : 1) * sizeof *rep);
    for (int c = 0; c < k && !bad; c++) {
        rep[c] = -1; DcRat best = {0, 1};
        for (size_t x = 0; x < n; x++) {
            if (cls[x] != c) continue;
            if (sel == 1) { if (rep[c] < 0) rep[c] = (int)x; continue; }
            if (sel == 2) { int r = m->map[chmap].table[x]; if (cls[r] != c || (rep[c] >= 0 && rep[c] != r)) bad = 1; rep[c] = r; continue; }
            DcRat ecc = {0, 1};
            for (size_t y = 0; y < n; y++) if (cls[y] == c) ecc = dc_rat_max(ecc, bf[x * n + y]);
            if (rep[c] < 0 || dc_rat_cmp(ecc, best) < 0) { rep[c] = (int)x; best = ecc; }
        }
    }
    if (bad) { free(cls); free(rep); free(d0); free(bf); dc_view_free(&v); return dc_invalid(m, "InduceApprox: section map %s does not pick one member of each class", m->map[chmap].name); }
    /* the disjoint union X + classes */
    size_t U = n + (size_t)k, NU = U * U; DcView u; memset(&u, 0, sizeof u);
    u.n = U; u.states = v.states; u.nobs = v.nobs; u.nact = v.nact;
    for (size_t p = 0; p < v.nobs; p++) {
        u.obs[p] = malloc(U * sizeof(int)); u.obs_tol[p] = v.obs_tol[p]; u.obs_car[p] = v.obs_car[p];
        for (size_t x = 0; x < n; x++) u.obs[p][x] = v.obs[p][x];
        for (int c = 0; c < k; c++) u.obs[p][n + c] = v.obs[p][rep[c]];
    }
    for (size_t a = 0; a < v.nact; a++) {
        u.act[a] = malloc(U * sizeof(int));
        for (size_t x = 0; x < n; x++) u.act[a][x] = v.act[a][x];
        for (int c = 0; c < k; c++) u.act[a][n + c] = (int)n + cls[v.act[a][rep[c]]];
    }
    DcRat *u0 = calloc(NU, sizeof *u0), *ub = calloc(NU, sizeof *ub), *ur = calloc(NU, sizeof *ur);
    if (dc_g_seed(m, &u, u0) || dc_g_beh_bfs(&u, u0, g, -1, ub) || dc_g_beh_ref(&u, u0, g, -1, ur)) ovf = 1;
    int agree = 1; for (size_t i = 0; i < NU; i++) if (dc_rat_cmp(ub[i], ur[i])) agree = 0;
    DcRat radius = {0, 1}, defect = {0, 1};
    for (size_t x = 0; x < n; x++) {
        radius = dc_rat_max(radius, bf[x * n + rep[cls[x]]]);
        defect = dc_rat_max(defect, ub[x * U + n + cls[x]]);
    }
    DcRat one = {1, 1}; Sx *bound = dc_rat_cmp(g, one) < 0 ? rs(dc_rat_div(radius, dc_rat_sub(one, g, &ovf), &ovf)) : dc_sym("Unbounded");
    Sx *reps = dc_form("Representatives", NULL), *upd = dc_form("Updates", NULL);
    for (int c = 0; c < k; c++) {
        Sx *B = dc_form("Block", NULL); for (size_t x = 0; x < n; x++) if (cls[x] == c) sx_push(B, sx_copy(S->elems[x]));
        sx_push(reps, dc_form("Class", dc_int(c), B, sx_copy(S->elems[rep[c]]), NULL));
    }
    for (size_t a = 0; a < v.nact; a++) {
        Sx *row = dc_form("Do", dc_sym(v.act_label[a]), NULL);
        for (int c = 0; c < k; c++) sx_push(row, dc_form("Step", dc_int(c), dc_int(u.act[a][n + c] - (int)n), NULL));
        sx_push(upd, row);
    }
    Sx *selx = sel == 0 ? dc_sym("Center") : sel == 1 ? dc_sym("First") : dc_form("Choose", dc_sym(m->map[chmap].name), NULL);
    Sx *valx = dc_form("ApproximateAbstraction",
        dc_form("Machine", dc_form("Output", dc_sym(slot >= 0 ? m->der[slot].name : "?"), dc_sym("Machine"), NULL), NULL),
        dc_form("States", dc_int(k), NULL), dc_form("Selector", selx, NULL), reps,
        dc_form("Radius", rs(radius), NULL), dc_form("Defect", dc_form("Interval", rs(defect), rs(defect), NULL), NULL),
        dc_form("Bound", bound, NULL), dc_form("AbstractionMap", dc_form("Kind", dc_sym("Graded"), NULL), dc_form("Defect", rs(defect), NULL), NULL), NULL);
    if (hw) sx_push(valx, dc_form("Within", dc_sym(wtxt), NULL));
    Sx *ev = dc_form("Evidence", dc_form("Certificate", dc_form("Kind", dc_sym("InducedMachine"), NULL), dc_form("Discount", rs(g), NULL), upd, NULL), NULL);
    for (size_t p = 0; p < u.nobs; p++) free(u.obs[p]);
    for (size_t a = 0; a < u.nact; a++) free(u.act[a]);
    free(u0); free(ub); free(ur); free(cls); free(rep); free(d0); free(bf); dc_view_free(&v);
    if (ovf) { sx_free(valx); sx_free(ev); return dc_unsupported(m, "InduceApprox: a rational left the 64-bit exact range"); }
    DcScope sc = {"M2-GradedDeterministic", -1, ""}; snprintf(sc.discount, sizeof sc.discount, "%s", gtxt);
    DcVerdict vd = hw && dc_rat_cmp(defect, within) > 0 ? VERDICT_FAILS : VERDICT_HOLDS;
    Sx *res = dc_envelope_scoped(m, vd, agree, dc_claim_of(q, "Literal"),
        dc_form("Subject", dc_form("Partition", dc_sym(dn), NULL), dc_form("Machine", dc_sym(mn), NULL), NULL),
        dc_form("Value", valx, NULL), ev, NULL, &sc);
    dc_result_bind_models(res, mn, slot >= 0 ? m->der[slot].name : "?");
    return res;
}
