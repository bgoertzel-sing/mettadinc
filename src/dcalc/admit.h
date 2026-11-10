/* M1 admission: the registry-driven frontend (guide 2.3, phases 1-5).
 * Mirrors validation/check_fixtures.py: every module of a file is scanned,
 * its profile read, imports resolved, every declaration and request checked
 * against the compiled-in registry, and the module rules (linear patterns,
 * acyclic map-call and derivation graphs, typed Enum elements) applied.
 * Nothing in a held declaration is evaluated here. */
#ifndef DCALC_ADMIT_H
#define DCALC_ADMIT_H
#include "sexp.h"
#include <stddef.h>

typedef struct { char **v; size_t n, cap; } DcStrSet;

typedef struct {
    char *name;            /* declared name */
    const char *kind;      /* registry declaration head */
    const Sx *form;        /* borrowed from the parsed file */
    int own;               /* declared in this module (not imported) */
} DcADecl;

typedef struct DcAModule {
    char *name;
    const Sx *form;
    const char *fname;
    DcADecl *decls; size_t ndecl, capdecl;
    DcStrSet elements, labels, fields, libraries;
    const char *dynamics, *values, *carriers;   /* registry strings, or NULL */
    const Sx **imports; size_t nimp, capimp;
} DcAModule;

typedef struct {
    char *mod;               /* module the diagnostic belongs to ("" = file level) */
    char *msg;               /* "file:line:col: where: message" */
} DcDiagItem;
typedef struct { DcDiagItem *v; size_t n, cap; } DcDiag;

typedef struct {
    const char *fname;
    DcAModule *mods; size_t nmod, capmod;
    DcDiag diag;
} DcAdmission;

/* Admit every (DC.Module ...) form of a parsed file and check its run forms.
 * Returns the number of diagnostics (0 = admitted). */
size_t dc_admit_file(const Sx *all, const char *fname, DcAdmission *out);
/* Several files as one universe: imports resolve across all of them. */
size_t dc_admit_files(const Sx *const *alls, const char *const *fnames, size_t nf, DcAdmission *out);
/* Number of diagnostics that belong to module mn. */
size_t dc_admit_module_ndiag(const DcAdmission *a, const char *mn);
DcAModule *dc_admit_find(DcAdmission *a, const char *name);
void dc_admission_free(DcAdmission *a);

/* string sets */
int dc_ss_has(const DcStrSet *s, const char *x);
void dc_ss_add(DcStrSet *s, const char *x);
void dc_ss_free(DcStrSet *s);
#endif
