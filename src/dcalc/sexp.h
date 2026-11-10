/* Minimal s-expression reader/printer for the MeTTaDinC M0 core.
 * Atoms are symbols, numbers kept as text, and strings; lists are vectors. */
#ifndef DCALC_SEXP_H
#define DCALC_SEXP_H
#include <stddef.h>

typedef enum { SX_SYM, SX_STR, SX_LIST } SxKind;

typedef struct Sx {
    SxKind kind;
    char *text;          /* SX_SYM / SX_STR */
    struct Sx **items;   /* SX_LIST */
    size_t n, cap;
    int line;            /* source line of the opening token */
    int col;             /* source column (1-based, bytes) of the opening token */
} Sx;

Sx *sx_sym(const char *s);
Sx *sx_str(const char *s);
Sx *sx_list(void);
void sx_push(Sx *l, Sx *x);
void sx_free(Sx *x);
Sx *sx_copy(const Sx *x);

/* Parse every top-level form of src.  Comments start with ';'.
 * Returns a list of forms, or NULL with *err set (static text) and *errline. */
Sx *sx_parse_all(const char *src, const char **err, int *errline);

/* Canonical printing: single spaces, no trailing newline.  Caller frees. */
char *sx_print(const Sx *x);

int sx_is_sym(const Sx *x, const char *s);
int sx_head_is(const Sx *x, const char *s);
/* First list child whose head is name, starting at index from. */
Sx *sx_find(const Sx *l, const char *name, size_t from);
int sx_equal(const Sx *a, const Sx *b);
#endif
