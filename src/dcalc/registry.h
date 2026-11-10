/* Read access to the compiled-in registry (registry_gen.c).
 * The registry is parsed once on first use and kept for the process lifetime.
 * Encoding (tools/gen_registry.py): (Dict ("key" value) ...), (List x ...),
 * "string", integer digits, True/False/Null. */
#ifndef DCALC_REGISTRY_H
#define DCALC_REGISTRY_H
#include "sexp.h"

/* Root (Dict ...) of the registry, or NULL if the compiled text fails to parse. */
const Sx *dc_registry(void);
/* sha256 of registry/mettadinc_registry.json. */
const char *dc_registry_digest_hex(void);
/* Value under key in a (Dict ...), or NULL. */
const Sx *dc_reg_get(const Sx *dict, const char *key);
/* Shorthands: registry section entries by name, or NULL. */
const Sx *dc_reg_decl(const char *head);
const Sx *dc_reg_request(const char *head);
const Sx *dc_reg_library(const char *name);
const Sx *dc_reg_result_type(const char *name);
/* Text of a string value, or NULL. */
const char *dc_reg_str(const Sx *v);
/* 1 if (List ...) contains the string s. */
int dc_reg_list_has(const Sx *list, const char *s);
/* 1 if the value is True. */
int dc_reg_true(const Sx *v);
/* Release the parsed registry (tests and sanitizer runs). */
void dc_registry_free(void);
#endif
