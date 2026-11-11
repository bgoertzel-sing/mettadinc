/* In-tree reduced ordered binary decision diagrams (M3, OQ5: no external
 * dependency).  Narrow interface: nodes are int handles into one manager;
 * 0 = false, 1 = true.  Variable order = variable index (0 is the root-most).
 * No garbage collection: a manager lives for one request and is freed whole. */
#ifndef DC_BDD_H
#define DC_BDD_H
#include <stddef.h>
#include <stdint.h>

typedef int DcBdd;
typedef struct DcBddMgr DcBddMgr;

DcBddMgr *dc_bdd_new(int nvars);
void dc_bdd_free(DcBddMgr *m);
int dc_bdd_nvars(const DcBddMgr *m);
size_t dc_bdd_nodes(const DcBddMgr *m);      /* nodes allocated so far (resource record) */
int dc_bdd_failed(const DcBddMgr *m);        /* 1 after an allocation limit was hit */

DcBdd dc_bdd_var(DcBddMgr *m, int v);         /* x_v */
DcBdd dc_bdd_not(DcBddMgr *m, DcBdd f);
DcBdd dc_bdd_and(DcBddMgr *m, DcBdd f, DcBdd g);
DcBdd dc_bdd_or(DcBddMgr *m, DcBdd f, DcBdd g);
DcBdd dc_bdd_xor(DcBddMgr *m, DcBdd f, DcBdd g);
DcBdd dc_bdd_ite(DcBddMgr *m, DcBdd f, DcBdd g, DcBdd h);
DcBdd dc_bdd_restrict(DcBddMgr *m, DcBdd f, int v, int val);   /* f[x_v := val] */
DcBdd dc_bdd_exists(DcBddMgr *m, DcBdd f, int v);

/* Substitution: result(x) = f(sub[0](x), ..., sub[n-1](x)); sub[i] are BDDs over the
 * same variables.  This is the image-free way to take preimages of term maps. */
DcBdd dc_bdd_compose(DcBddMgr *m, DcBdd f, const DcBdd *sub);

/* Support (variables f depends on): out[v] = 1. */
void dc_bdd_support(const DcBddMgr *m, DcBdd f, unsigned char *out);
/* Least satisfying assignment in the order "x_{n-1} ... x_0 as a binary number"
 * (i.e. least word value); returns 0 when f is false. */
int dc_bdd_min_word(const DcBddMgr *m, DcBdd f, uint64_t *word);
/* Evaluate f at a concrete word (bit v of word = x_v). */
int dc_bdd_eval(const DcBddMgr *m, DcBdd f, uint64_t word);
/* Number of satisfying words as a double (exact up to 2^53) and as log2 when huge. */
double dc_bdd_satcount(const DcBddMgr *m, DcBdd f);
#endif
