/* Families elaborator (library Families, release 1; t-2026-11-24-mettadinc-families). */
#ifndef DCALC_FAMILIES_H
#define DCALC_FAMILIES_H
#include "sexp.h"
/* A module with (Use .. Families ..) is rewritten source to source into a module without Families forms.
 * Returns 0 with *out = NULL when the module does not use Families, 0 with *out = the new module form, or
 * -2 with why set when a form cannot be elaborated (the request then answers Unsupported, never InvalidInput). */
int dc_families_expand(const Sx *all, const Sx *raw, Sx **out, char *why, size_t wn);
#endif
