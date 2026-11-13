/* Enumerated deterministic model for the MeTTaDinC M0 core.
 * A module is admitted from its DC.Module source: carriers are enumerated,
 * every map is tabulated over its source carrier, and every element is a
 * small integer index into its carrier.  Admission failures name the field. */
#ifndef DCALC_MODEL_H
#define DCALC_MODEL_H
#include "rat.h"
#include "sexp.h"

#define DC_MAX_NAME 64

typedef struct {
    char name[DC_MAX_NAME];
    size_t n;            /* number of elements */
    Sx **elems;          /* canonical value of each element */
    int value;           /* M2: synthesized carrier of a builtin value type (Rational01); grows during admission */
    int reach_parent;    /* M2: (Reach M (From e ...)): parent carrier + 1, 0 = none */
    int *sub_idx;        /* M2: sub_idx[i] = index of element i in the parent carrier */
} DcCarrier;

typedef struct {
    char name[DC_MAX_NAME];
    int from, to;        /* carrier indices */
    int *table;          /* table[i] = index in carrier `to` */
} DcMap;

typedef struct { char label[DC_MAX_NAME]; int map; int tol; /* M2: (Values Tol) index, -1 literal */ } DcPort;

typedef struct {
    char name[DC_MAX_NAME];
    int states;          /* carrier index */
    DcPort obs[16];  size_t nobs;
    DcPort act[16];  size_t nact;
    int graded_obs;      /* an Observe carries (Values Tol): outside M0 */
    int bagged;          /* (Bag ...): nondeterministic, outside M0 */
    DcPort merge[4]; size_t nmerge;   /* M2: (Merge label map), map from (Product S S) to S */
} DcMachine;

/* Exact: codes compared literally (default). All: (Codes AllCodes), every code
 * accepted as equal, the tolerance that can hide a literal failure. */
typedef enum { DC_CODES_EXACT = 0, DC_CODES_ALL = 1 } DcCodes;

typedef struct {
    char name[DC_MAX_NAME];
    int machine;
    int encode;          /* map index */
    DcCodes codes;
    int tol;             /* tolerance index, -1 when exact */
} DcRepr;

typedef struct {
    char name[DC_MAX_NAME];
    Sx *source;          /* (Output X Machine) or a machine name */
    int target;          /* machine index */
    int map;
} DcAbsMap;

typedef struct { char name[DC_MAX_NAME]; Sx *request; } DcDerive;
/* M2: a finite law on a carrier; only the uniform law is admitted. */
typedef struct { char name[DC_MAX_NAME]; int on; int uniform; } DcMeas;

/* (Tolerance Name (On C) (Trivial)): identifies every pair of elements of C.
 * Other tolerance bodies are outside M0 and are noted as unsupported. */
/* M2 graded bodies: (Discrete), (OneMinusAbsoluteDifference) on rational
 * values, (SymmetricTable (Diagonal v) (a b (Rat p q)) ...) as a kernel. */
typedef enum { DC_TOL_TRIVIAL = 0, DC_TOL_DISCRETE, DC_TOL_ONE_MINUS_ABS, DC_TOL_SYM_TABLE } DcTolKind;
typedef struct {
    char name[DC_MAX_NAME]; int on; int trivial;
    DcTolKind kind;
    DcRat *table;        /* SYM_TABLE: n*n kernel values, row-major; else NULL */
} DcTol;

typedef struct {
    char name[DC_MAX_NAME];
    char profile[DC_MAX_NAME];
    char digest[65];     /* sha256 of the canonical module text */
    Sx *source;          /* the admitted DC.Module form */
    DcCarrier car[32];  size_t ncar;
    DcMap     map[64];  size_t nmap;
    DcMachine mach[16]; size_t nmach;
    DcRepr    rep[16];  size_t nrep;
    DcAbsMap  abs[16];  size_t nabs;
    DcDerive  der[32];  size_t nder;
    DcMeas    meas[16]; size_t nmeas;   /* M2: (Measure Name (On C) (Uniform)) */
    DcTol     tol[16];  size_t ntol;
    int unsupported_decls;   /* declarations outside the M0 fragment */
    int symbolic;            /* M3: (Carriers Symbolic); requests go to ops_sym.c, nothing tabulated */
    int stochastic;          /* M4 (opt-in only): Dynamics Stochastic; requests go to stoch.c, nothing tabulated */
    int hives;               /* M6 (opt-in only): (Use Hives) in beyond-release; KernelHive/CrossKernel read by ops_hives.c from m->source */
    int contracts;           /* M6 (opt-in only): (Use Contracts) in beyond-release; Implementation decls read by ops_contracts.c from m->source */
    int nondet;              /* M5 (opt-in only): Dynamics Nondeterministic; requests go to ops_nondet.c, nothing tabulated */
    char basedir[512];       /* M4-estimates: directory Stream sources resolve against (set by dc_eval_request) */
    char profile_unsupported[2 * DC_MAX_NAME + 64];  /* non-empty: the whole module is outside M0 (reason) */
    char skipped[64][DC_MAX_NAME]; size_t nskip;  /* their names */
    char unsupported_first[2 * DC_MAX_NAME + 32];
} DcModule;

/* Admission result: 0 ok; otherwise err names the field ("Map keep-ab: ..."). */
int dc_admit(const Sx *form, DcModule *m, char *err, size_t errsz);
void dc_module_free(DcModule *m);

int dc_find_carrier(const DcModule *m, const char *name);
int dc_find_map(const DcModule *m, const char *name);
int dc_find_machine(const DcModule *m, const char *name);
int dc_find_repr(const DcModule *m, const char *name);
int dc_find_abs(const DcModule *m, const char *name);
int dc_find_derive(const DcModule *m, const char *name);
int dc_find_tol(const DcModule *m, const char *name);
int dc_find_meas(const DcModule *m, const char *name);
int dc_carrier_index(const DcCarrier *c, const Sx *v);  /* -1 if absent */
/* M2 value carriers and rational literals. */
int dc_value_carrier(DcModule *m, const char *name);    /* -1 if not a value type */
int dc_value_add(DcCarrier *c, const Sx *v);            /* index, -1 on error */
int dc_sx_rat(const Sx *v, DcRat *out);                 /* (Rat p q) or integer; 0 ok */
DcRat dc_tol_dist(const DcModule *m, int tol, int i, int j, int *ovf);  /* distance in [0,1] */
/* 1 when name was declared by a declaration outside the M0 fragment. */
int dc_is_skipped(const DcModule *m, const char *name);

void dc_sha256_hex(const char *data, size_t n, char out[65]);
#endif
