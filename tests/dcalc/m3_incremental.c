/* M3 incrementality (spec Lemma 4.17, Table 7) on the forty-bit fixture.
 * 1. Adding the query x1 resumes refinement from the old partition and matches
 *    refinement from scratch (ZeroMachine; and a rotate-only machine where x1 splits).
 * 2. Removing inject: the old 8-block partition stays stable (sufficient) but is no
 *    longer coarsest; a witness without inject transports and replays; a witness
 *    using inject is dropped; a checked upper bound stands.
 * Build: gcc -std=c11 -O2 -Isrc/dcalc tests/dcalc/m3_incremental.c build/dcalc/libdcalc.a -lm
 * Usage (from the repository root): m3_incremental [fixture].  Exit 0 iff all pass. */
#include "ops_sym.c"
#include <stdio.h>
static int bad;
#define CK(c, msg) do { int ok_ = (c); printf("%-72s %s\n", msg, ok_ ? "PASS" : "FAIL"); if (!ok_) bad++; } while (0)
static int same_part(const DcBdd *a, int na, const DcBdd *b, int nb) {
    if (na != nb) return 0;
    for (int i = 0; i < na; i++) { int f = 0; for (int j = 0; j < nb; j++) if (a[i] == b[j]) f = 1; if (!f) return 0; }
    return 1;
}
static int stable(DcBddMgr *bm, const SMach *M, const SymVal *av, const SymVal *ob, const DcBdd *cl, int ncl) {
    for (int i = 0; i < ncl; i++) {
        for (int p = 0; p < M->nobs; p++) for (int k = 0; k < ob[p].w; k++)
            if (dc_bdd_and(bm, cl[i], ob[p].b[k]) && dc_bdd_and(bm, cl[i], dc_bdd_not(bm, ob[p].b[k]))) return 0;
        for (int a = 0; a < M->nact; a++) {
            int in = 0;
            for (int j = 0; j < ncl && !in; j++) if (!dc_bdd_and(bm, cl[i], dc_bdd_not(bm, dc_bdd_compose(bm, cl[j], av[a].b)))) in = 1;
            if (!in) return 0;
        }
    }
    return 1;
}
static void keep_acts(SMach *D, const SMach *Z, const char *only, const char *drop) {
    D->nact = 0;
    for (int a = 0; a < Z->nact; a++)
        if ((only && !strcmp(Z->act[a].name, only)) || (drop && strcmp(Z->act[a].name, drop))) D->act[D->nact++] = Z->act[a];
}
int main(int argc, char **argv) {
    const char *F = argc > 1 ? argv[1] : "docs/e0/docs/01_language_specification/validation_package/fixtures/forty_bits.metta";
    FILE *fp = fopen(F, "rb"); if (!fp) { printf("cannot open %s\n", F); return 2; }
    static char src[1 << 20], buf[1 << 20]; size_t n = fread(src, 1, sizeof src - 1, fp); src[n] = 0; fclose(fp);
    const char *anchor = "  (Representation KeepX0", *ins = "  (Map read1 (From Word) (To Bit) (Body ($x) (BitAt $x 1)))\n";
    char *at = strstr(src, anchor); if (!at) { puts("anchor not found"); return 2; }
    snprintf(buf, sizeof buf, "%.*s%s%s", (int)(at - src), src, ins, at);
    const char *e; int el; Sx *all = sx_parse_all(buf, &e, &el); if (!all) { printf("parse: %s line %d\n", e, el); return 2; }
    const Sx *mod = NULL; for (size_t i = 0; i < all->n; i++) if (sx_head_is(all->items[i], "DC.Module")) { mod = all->items[i]; break; }
    static SymMod S; char err[256] = "";
    if (!mod || sym_read(mod, &S, err, sizeof err)) { printf("read: %s\n", err); return 2; }
    int zi = sfind_mach(&S, "ZeroMachine"), r0 = sfind_map(&S, "read0"), r1 = sfind_map(&S, "read1");
    if (zi < 0 || r0 < 0 || r1 < 0) { puts("fixture names missing"); return 2; }
    const SMach *Z = &S.mach[zi];
    SMach X1 = *Z; snprintf(X1.obs[X1.nobs].name, SYM_NM, "x1"); X1.obs[X1.nobs++].map = r1;
    SMach R = *Z; keep_acts(&R, Z, "rotate", NULL);
    SMach R1 = R; snprintf(R1.obs[R1.nobs].name, SYM_NM, "x1"); R1.obs[R1.nobs++].map = r1;
    SMach NI = *Z; keep_acts(&NI, Z, NULL, "inject");
    SymEnv E; if (senv_init(&E, S.car[Z->states].width)) return 2;
    DcBddMgr *bm = E.bm;
    static SymVal avZ[8], avR[8], avN[8], ob[8], obN[8]; static STest T0[SYM_MAXT], T1[SYM_MAXT], T2[SYM_MAXT];
    static DcBdd c0[SYM_MAXCL], c1[SYM_MAXCL], c2[SYM_MAXCL]; int nt0 = 0, n0 = 0, nt1 = 0, n1 = 0, nt2 = 0, n2 = 0, rc;
    if (mach_acts(&E, &S, Z, avZ, err, sizeof err) || mach_acts(&E, &S, &R, avR, err, sizeof err) || mach_acts(&E, &S, &NI, avN, err, sizeof err)) { printf("acts: %s\n", err); return 2; }
    /* 1a: ZeroMachine + x1 */
    rc = sym_refine(bm, &S, Z, avZ, ob, E.xv, T0, &nt0, c0, &n0, err, sizeof err);
    rc |= sym_refine(bm, &S, &X1, avZ, ob, E.xv, T1, &nt1, c1, &n1, err, sizeof err);
    memcpy(T2, T0, sizeof T0); memcpy(c2, c0, sizeof c0);
    rc |= sym_refine_from(bm, &S, &X1, avZ, ob, E.xv, T2, &nt2, c2, &n2, Z->nobs, nt0, n0, err, sizeof err);
    CK(!rc && n0 == 8, "ZeroMachine from scratch: 8 blocks");
    CK(!rc && n2 == 8 && same_part(c1, n1, c2, n2), "add query x1 to ZeroMachine: resumed == from scratch (8 blocks)");
    /* 1b: rotate-only machine, where x1 does split */
    rc = sym_refine(bm, &S, &R, avR, ob, E.xv, T0, &nt0, c0, &n0, err, sizeof err);
    rc |= sym_refine(bm, &S, &R1, avR, ob, E.xv, T1, &nt1, c1, &n1, err, sizeof err);
    memcpy(T2, T0, sizeof T0); memcpy(c2, c0, sizeof c0);
    rc |= sym_refine_from(bm, &S, &R1, avR, ob, E.xv, T2, &nt2, c2, &n2, R.nobs, nt0, n0, err, sizeof err);
    CK(!rc && n0 == 2 && n2 == 4 && same_part(c1, n1, c2, n2), "add query x1 to a rotate-only machine: resumed 2 -> 4 == from scratch");
    /* 2: remove inject */
    rc = sym_refine(bm, &S, Z, avZ, ob, E.xv, T0, &nt0, c0, &n0, err, sizeof err);
    for (int p = 0; p < NI.nobs; p++) if (sym_apply(bm, &S, NI.obs[p].map, E.xv, &obN[p], err, sizeof err)) rc = 1;
    int suff = !rc && stable(bm, &NI, avN, obN, c0, n0);
    rc |= sym_refine(bm, &S, &NI, avN, ob, E.xv, T1, &nt1, c1, &n1, err, sizeof err);
    CK(suff, "remove inject: old 8-block partition still stable (sufficient)");
    CK(!rc && n1 == 4 && n1 < n0, "remove inject: coarsest is now 4 blocks (coarseness does not transport)");
    CK(sym_transport_remove("Coarsest", NULL, "inject") == SYM_TR_SUFFICIENT, "Table 7: coarsest -> sufficient");
    CK(sym_transport_remove("UpperBound", NULL, "inject") == SYM_TR_STANDS, "Table 7: checked upper bound stands");
    Sx *w1 = sx_list(); sx_push(w1, sx_sym("Word")); sx_push(w1, sx_sym("swap"));
    Sx *w2 = sx_list(); sx_push(w2, sx_sym("Word")); sx_push(w2, sx_sym("inject")); sx_push(w2, sx_sym("swap"));
    CK(sym_transport_remove("Witness", w1, "inject") == SYM_TR_STANDS, "Table 7: witness (swap) transports");
    CK(sym_transport_remove("Witness", w2, "inject") == SYM_TR_DROPPED, "Table 7: witness (inject swap) is dropped");
    int sw = -1; for (int a = 0; a < NI.nact; a++) if (!strcmp(NI.act[a].name, "swap")) sw = a;
    int word[1] = { sw };
    CK(sw >= 0 && sym_replay_pair(&S, &NI, r0, 0, 2, word, 1, 0), "transported witness replays without inject (pair 0/2, swap, x0)");
    sx_free(w1); sx_free(w2); dc_bdd_free(bm);
    printf("m3_incremental: %s\n", bad ? "FAIL" : "PASS");
    return bad != 0;
}
