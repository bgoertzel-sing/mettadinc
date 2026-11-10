/* Minimal s-expression reader/printer for the MeTTaDinC M0 core. */
#include "sexp.h"
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

static void *xmalloc(size_t n) { void *p = malloc(n ? n : 1); if (!p) abort(); return p; }
static char *xstrdup(const char *s) { size_t n = strlen(s); char *p = xmalloc(n + 1); memcpy(p, s, n + 1); return p; }

Sx *sx_sym(const char *s) { Sx *x = xmalloc(sizeof *x); memset(x, 0, sizeof *x); x->kind = SX_SYM; x->text = xstrdup(s); return x; }
Sx *sx_str(const char *s) { Sx *x = sx_sym(s); x->kind = SX_STR; return x; }
Sx *sx_list(void) { Sx *x = xmalloc(sizeof *x); memset(x, 0, sizeof *x); x->kind = SX_LIST; return x; }

void sx_push(Sx *l, Sx *x) {
    if (l->n == l->cap) {
        l->cap = l->cap ? l->cap * 2 : 4;
        l->items = realloc(l->items, l->cap * sizeof *l->items);
        if (!l->items) abort();
    }
    l->items[l->n++] = x;
}

void sx_free(Sx *x) {
    if (!x) return;
    for (size_t i = 0; i < x->n; i++) sx_free(x->items[i]);
    free(x->items); free(x->text); free(x);
}

Sx *sx_copy(const Sx *x) {
    if (!x) return NULL;
    if (x->kind != SX_LIST) { Sx *c = x->kind == SX_SYM ? sx_sym(x->text) : sx_str(x->text); c->line = x->line; c->col = x->col; return c; }
    Sx *c = sx_list(); c->line = x->line; c->col = x->col;
    for (size_t i = 0; i < x->n; i++) sx_push(c, sx_copy(x->items[i]));
    return c;
}

typedef struct { const char *s; size_t i; int line; const char *err; int errline; size_t ls; } Rd;
#define COL(r) ((int)((r)->i - (r)->ls) + 1)

static void skip_ws(Rd *r) {
    for (;;) {
        char c = r->s[r->i];
        if (c == '\n') { r->line++; r->i++; r->ls = r->i; }
        else if (c && isspace((unsigned char)c)) r->i++;
        else if (c == ';') { while (r->s[r->i] && r->s[r->i] != '\n') r->i++; }
        else return;
    }
}

static Sx *read_form(Rd *r, int depth) {
    skip_ws(r);
    char c = r->s[r->i];
    if (!c) { r->err = "unexpected end of input"; r->errline = r->line; return NULL; }
    if (depth > 200) { r->err = "nesting too deep"; r->errline = r->line; return NULL; }
    if (c == ')') { r->err = "unbalanced ')'"; r->errline = r->line; return NULL; }
    if (c == '(') {
        Sx *l = sx_list(); l->line = r->line; l->col = COL(r); r->i++;
        for (;;) {
            skip_ws(r);
            if (!r->s[r->i]) { sx_free(l); r->err = "unclosed '('"; r->errline = l ? r->line : r->line; return NULL; }
            if (r->s[r->i] == ')') { r->i++; return l; }
            Sx *x = read_form(r, depth + 1);
            if (!x) { sx_free(l); return NULL; }
            sx_push(l, x);
        }
    }
    if (c == '"') {
        size_t cap = 16, n = 0; char *buf = xmalloc(cap); int line = r->line, col = COL(r); r->i++;
        for (;;) {
            char d = r->s[r->i];
            if (!d) { free(buf); r->err = "unterminated string"; r->errline = line; return NULL; }
            r->i++;
            if (d == '"') break;
            if (d == '\\' && r->s[r->i]) d = r->s[r->i++];
            if (d == '\n') { r->line++; r->ls = r->i; }
            if (n + 2 > cap) { cap *= 2; buf = realloc(buf, cap); if (!buf) abort(); }
            buf[n++] = d;
        }
        buf[n] = 0; Sx *x = sx_str(buf); free(buf); x->line = line; x->col = col; return x;
    }
    size_t st = r->i; int col = COL(r);
    while (r->s[r->i] && !isspace((unsigned char)r->s[r->i]) && r->s[r->i] != '(' && r->s[r->i] != ')' && r->s[r->i] != ';' && r->s[r->i] != '"') r->i++;
    size_t len = r->i - st; char *t = xmalloc(len + 1); memcpy(t, r->s + st, len); t[len] = 0;
    Sx *x = sx_sym(t); free(t); x->line = r->line; x->col = col; return x;
}

Sx *sx_parse_all(const char *src, const char **err, int *errline) {
    Rd r = { src, 0, 1, NULL, 0, 0 };
    Sx *all = sx_list();
    for (;;) {
        skip_ws(&r);
        if (!r.s[r.i]) return all;
        Sx *x = read_form(&r, 0);
        if (!x) { sx_free(all); if (err) *err = r.err; if (errline) *errline = r.errline; return NULL; }
        sx_push(all, x);
    }
}

typedef struct { char *b; size_t n, cap; } Buf;
static void bput(Buf *b, const char *s, size_t n) {
    if (b->n + n + 1 > b->cap) { while (b->n + n + 1 > b->cap) b->cap = b->cap ? b->cap * 2 : 64; b->b = realloc(b->b, b->cap); if (!b->b) abort(); }
    memcpy(b->b + b->n, s, n); b->n += n; b->b[b->n] = 0;
}
static void print_rec(Buf *b, const Sx *x) {
    if (x->kind == SX_SYM) { bput(b, x->text, strlen(x->text)); return; }
    if (x->kind == SX_STR) {
        bput(b, "\"", 1);
        for (const char *p = x->text; *p; p++) { if (*p == '"' || *p == '\\') bput(b, "\\", 1); bput(b, p, 1); }
        bput(b, "\"", 1); return;
    }
    bput(b, "(", 1);
    for (size_t i = 0; i < x->n; i++) { if (i) bput(b, " ", 1); print_rec(b, x->items[i]); }
    bput(b, ")", 1);
}
char *sx_print(const Sx *x) { Buf b = {0}; bput(&b, "", 0); print_rec(&b, x); return b.b; }

int sx_is_sym(const Sx *x, const char *s) { return x && x->kind == SX_SYM && strcmp(x->text, s) == 0; }
int sx_head_is(const Sx *x, const char *s) { return x && x->kind == SX_LIST && x->n > 0 && sx_is_sym(x->items[0], s); }
Sx *sx_find(const Sx *l, const char *name, size_t from) {
    if (!l || l->kind != SX_LIST) return NULL;
    for (size_t i = from; i < l->n; i++) if (sx_head_is(l->items[i], name)) return l->items[i];
    return NULL;
}
int sx_equal(const Sx *a, const Sx *b) {
    if (a->kind != b->kind) return 0;
    if (a->kind != SX_LIST) return strcmp(a->text, b->text) == 0;
    if (a->n != b->n) return 0;
    for (size_t i = 0; i < a->n; i++) if (!sx_equal(a->items[i], b->items[i])) return 0;
    return 1;
}
