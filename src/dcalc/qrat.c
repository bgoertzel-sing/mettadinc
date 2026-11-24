/* Arbitrary-precision exact rationals for the stochastic paths (see qrat.h
 * and docs/RATIONALS.md).  Magnitudes are little-endian base-2^32 limb
 * vectors.  Temporaries live on the heap and are freed at once; finished big
 * values are copied into the per-request arena, so a DcQ is a plain value. */
#include "qrat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t limb;
typedef uint64_t dlimb;
typedef unsigned __int128 u128;
typedef __int128 i128;
int dc_q_force_big = 0;

/* ---------- heap magnitudes ---------- */
typedef struct { limb *v; size_t n; } M;
static void *xalloc(size_t n) {
    void *p = calloc(n ? n : 1, 1);
    if (!p) { fputs("dcalc: out of memory (qrat temporaries)\n", stderr); abort(); }
    return p;
}
static M m_new(size_t cap) { M a; a.v = xalloc(sizeof(limb) * (cap ? cap : 1)); a.n = 0; return a; }
static void m_free(M *a) { free(a->v); a->v = NULL; a->n = 0; }
static void m_norm(M *a) { while (a->n && !a->v[a->n - 1]) a->n--; }
static M m_from_u128(u128 x) { M a = m_new(4); while (x) { a.v[a.n++] = (limb)x; x >>= 32; } return a; }
static M m_copy(const limb *v, size_t n) { M a = m_new(n); if (n) memcpy(a.v, v, sizeof(limb) * n); a.n = n; m_norm(&a); return a; }
static int m_is_one(M a) { return a.n == 1 && a.v[0] == 1; }
/* value of a (a.n <= 4) as u128 */
static u128 m_u128(M a) { u128 x = 0; for (size_t i = a.n; i-- > 0;) x = (x << 32) | a.v[i]; return x; }
static int m_cmp(M a, M b) {
    if (a.n != b.n) return a.n < b.n ? -1 : 1;
    for (size_t i = a.n; i-- > 0;) if (a.v[i] != b.v[i]) return a.v[i] < b.v[i] ? -1 : 1;
    return 0;
}
static M m_add(M a, M b) {
    if (a.n < b.n) { M t = a; a = b; b = t; }
    M r = m_new(a.n + 1); dlimb c = 0;
    for (size_t i = 0; i < a.n; i++) { c += (dlimb)a.v[i] + (i < b.n ? b.v[i] : 0); r.v[i] = (limb)c; c >>= 32; }
    r.n = a.n; if (c) r.v[r.n++] = (limb)c;
    return r;
}
static M m_sub(M a, M b) {   /* requires a >= b */
    M r = m_new(a.n); dlimb bw = 0;
    for (size_t i = 0; i < a.n; i++) {
        dlimb s = (dlimb)(i < b.n ? b.v[i] : 0) + bw;
        if ((dlimb)a.v[i] >= s) { r.v[i] = (limb)((dlimb)a.v[i] - s); bw = 0; }
        else { r.v[i] = (limb)(((dlimb)1 << 32) + a.v[i] - s); bw = 1; }
    }
    r.n = a.n; m_norm(&r); return r;
}
static M m_mul(M a, M b) {
    if (!a.n || !b.n) return m_new(1);
    M r = m_new(a.n + b.n);
    for (size_t i = 0; i < a.n; i++) {
        dlimb c = 0;
        for (size_t j = 0; j < b.n; j++) { c += (dlimb)a.v[i] * b.v[j] + r.v[i + j]; r.v[i + j] = (limb)c; c >>= 32; }
        r.v[i + b.n] = (limb)c;
    }
    r.n = a.n + b.n; m_norm(&r); return r;
}
/* q = a / b, r = a % b for b != 0 (Knuth 4.3.1 Algorithm D, as in Hacker's
 * Delight divmnu).  Either output may be NULL. */
static void m_divmod(M a, M b, M *q, M *r) {
    if (m_cmp(a, b) < 0) { if (q) *q = m_new(1); if (r) *r = m_copy(a.v, a.n); return; }
    if (b.n == 1) {
        M qq = m_new(a.n); dlimb rem = 0;
        for (size_t i = a.n; i-- > 0;) { dlimb cur = (rem << 32) | a.v[i]; qq.v[i] = (limb)(cur / b.v[0]); rem = cur % b.v[0]; }
        qq.n = a.n; m_norm(&qq);
        if (q) *q = qq; else m_free(&qq);
        if (r) { *r = m_new(1); if (rem) { r->v[0] = (limb)rem; r->n = 1; } }
        return;
    }
    size_t n = b.n, mlen = a.n - b.n;
    int s = __builtin_clz(b.v[n - 1]);
    limb *vn = xalloc(sizeof(limb) * n), *un = xalloc(sizeof(limb) * (a.n + 1));
    for (size_t i = n - 1; i > 0; i--) vn[i] = (limb)(((dlimb)b.v[i] << s) | ((dlimb)b.v[i - 1] >> (32 - s)));
    vn[0] = (limb)((dlimb)b.v[0] << s);
    un[a.n] = (limb)((dlimb)a.v[a.n - 1] >> (32 - s));
    for (size_t i = a.n - 1; i > 0; i--) un[i] = (limb)(((dlimb)a.v[i] << s) | ((dlimb)a.v[i - 1] >> (32 - s)));
    un[0] = (limb)((dlimb)a.v[0] << s);
    M qq = m_new(mlen + 1);
    for (size_t j = mlen + 1; j-- > 0;) {
        dlimb num = ((dlimb)un[j + n] << 32) | un[j + n - 1];
        dlimb qhat = num / vn[n - 1], rhat = num % vn[n - 1];
        while (qhat >> 32 || qhat * vn[n - 2] > ((rhat << 32) | un[j + n - 2])) {
            qhat--; rhat += vn[n - 1];
            if (rhat >> 32) break;
        }
        int64_t k = 0, t;
        for (size_t i = 0; i < n; i++) {
            dlimb p = qhat * vn[i];
            t = (int64_t)un[i + j] - k - (int64_t)(p & 0xFFFFFFFFu);
            un[i + j] = (limb)t;
            k = (int64_t)(p >> 32) - (t >> 32);
        }
        t = (int64_t)un[j + n] - k; un[j + n] = (limb)t;
        qq.v[j] = (limb)qhat;
        if (t < 0) {
            qq.v[j]--; dlimb c = 0;
            for (size_t i = 0; i < n; i++) { c += (dlimb)un[i + j] + vn[i]; un[i + j] = (limb)c; c >>= 32; }
            un[j + n] = (limb)((dlimb)un[j + n] + c);
        }
    }
    qq.n = mlen + 1; m_norm(&qq);
    if (q) *q = qq; else m_free(&qq);
    if (r) {
        M rr = m_new(n);
        for (size_t i = 0; i < n; i++) rr.v[i] = (limb)(((dlimb)un[i] >> s) | ((dlimb)un[i + 1] << (32 - s)));
        rr.n = n; m_norm(&rr); *r = rr;
    }
    free(vn); free(un);
}
static M m_gcd(M a, M b) {
    M x = m_copy(a.v, a.n), y = m_copy(b.v, b.n);
    while (y.n) {
        if (x.n <= 2 && y.n <= 2) {   /* finish in 64 bits */
            dlimb p = (dlimb)m_u128(x), q = (dlimb)m_u128(y);
            while (q) { dlimb t = p % q; p = q; q = t; }
            m_free(&x); m_free(&y); return m_from_u128(p);
        }
        M r; m_divmod(x, y, NULL, &r); m_free(&x); x = y; y = r;
    }
    m_free(&y); return x;
}
/* a * m + add, single-limb m and add (decimal parsing). */
static M m_muladd(M a, limb mul, limb add) {
    M r = m_new(a.n + 1); dlimb c = add;
    for (size_t i = 0; i < a.n; i++) { c += (dlimb)a.v[i] * mul; r.v[i] = (limb)c; c >>= 32; }
    r.n = a.n; if (c) r.v[r.n++] = (limb)c;
    return r;
}

/* ---------- arena for finished big values ---------- */
typedef struct Chunk { struct Chunk *prev; size_t base, used, cap; uint64_t data[]; } Chunk;
static Chunk *g_top; static size_t g_live, g_peak, g_cap = (size_t)1 << 30;
static void *arena_alloc(size_t sz) {
    sz = (sz + 7) & ~(size_t)7;
    if (!g_top || g_top->cap - g_top->used < sz) {
        size_t c = sz > ((size_t)1 << 20) ? sz : ((size_t)1 << 20);
        if (g_live + c > g_cap) return NULL;
        Chunk *k = malloc(sizeof(Chunk) + c);
        if (!k) return NULL;
        k->prev = g_top; k->base = g_top ? g_top->base + g_top->used : 0; k->used = 0; k->cap = c;
        g_top = k; g_live += c; if (g_live > g_peak) g_peak = g_live;
    }
    void *p = (unsigned char *)g_top->data + g_top->used; g_top->used += sz;
    return p;
}
size_t dc_q_arena_mark(void) { return g_top ? g_top->base + g_top->used : 0; }
void dc_q_arena_release(size_t mark) {
    while (g_top && g_top->base > mark) { Chunk *k = g_top; g_top = k->prev; g_live -= k->cap; free(k); }
    if (g_top && mark - g_top->base <= g_top->used) g_top->used = mark - g_top->base;
}
void dc_q_arena_reset(void) { while (g_top) { Chunk *k = g_top; g_top = k->prev; free(k); } g_live = 0; }
void dc_q_arena_cap(size_t bytes) { g_cap = bytes; }
size_t dc_q_arena_peak(void) { return g_peak; }

/* ---------- DcQ values ---------- */
/* Big form: sign lives in q.n (-1/+1), q.d = 1, magnitudes in *b. */
struct DcQBig { uint32_t nn, nd; limb v[]; };
static const DcQ QZERO = {0, 1, NULL};
static int set_ovf(int *ovf, int code) { if (ovf && *ovf < code) *ovf = code; return 0; }
static int m_fits63(M a) { return a.n <= 2 && m_u128(a) <= (u128)INT64_MAX; }
/* Takes ownership of num and den. */
static DcQ q_make(int sign, M num, M den, int *ovf) {
    m_norm(&num); m_norm(&den);
    if (!den.n) { m_free(&num); m_free(&den); set_ovf(ovf, 1); return QZERO; }
    if (!num.n || !sign) { m_free(&num); m_free(&den); return QZERO; }
    M g = m_gcd(num, den);
    if (!m_is_one(g)) { M a, b; m_divmod(num, g, &a, NULL); m_divmod(den, g, &b, NULL); m_free(&num); m_free(&den); num = a; den = b; }
    m_free(&g);
    DcQ r = QZERO;
    if (!dc_q_force_big && m_fits63(num) && m_fits63(den)) {
        r.n = (int64_t)m_u128(num) * (sign < 0 ? -1 : 1); r.d = (int64_t)m_u128(den);
    } else {
        DcQBig *bg = arena_alloc(sizeof(DcQBig) + sizeof(limb) * (num.n + den.n));
        if (!bg) set_ovf(ovf, 2);   /* memory cap: Unsupported "memory limit", never a wrong value */
        else {
            bg->nn = (uint32_t)num.n; bg->nd = (uint32_t)den.n;
            memcpy(bg->v, num.v, sizeof(limb) * num.n); memcpy(bg->v + num.n, den.v, sizeof(limb) * den.n);
            r.n = sign < 0 ? -1 : 1; r.d = 1; r.b = bg;
        }
    }
    m_free(&num); m_free(&den); return r;
}
static i128 gcd_i128(i128 a, i128 b) { if (a < 0) a = -a; if (b < 0) b = -b; while (b) { i128 t = a % b; a = b; b = t; } return a; }
static DcQ q_i128(i128 n, i128 d, int *ovf) {
    if (d == 0) { set_ovf(ovf, 1); return QZERO; }
    if (d < 0) { n = -n; d = -d; }
    if (n == 0) return QZERO;
    i128 g = gcd_i128(n, d); if (g > 1) { n /= g; d /= g; }
    if (!dc_q_force_big && n <= INT64_MAX && n >= -INT64_MAX && d <= INT64_MAX) { DcQ r = {(int64_t)n, (int64_t)d, NULL}; return r; }
    return q_make(n < 0 ? -1 : 1, m_from_u128(n < 0 ? (u128)(-n) : (u128)n), m_from_u128((u128)d), ovf);
}
int dc_q_sign(DcQ a) { return a.n < 0 ? -1 : a.n > 0; }
static void q_parts(DcQ a, M *num, M *den) {
    if (a.b) { *num = m_copy(a.b->v, a.b->nn); *den = m_copy(a.b->v + a.b->nn, a.b->nd); }
    else { *num = m_from_u128(a.n < 0 ? (u128)(-(i128)a.n) : (u128)a.n); *den = m_from_u128((u128)a.d); }
}
DcQ dc_q(int64_t n, int64_t d, int *ovf) { return q_i128(n, d, ovf); }
DcQ dc_q_from_rat(DcRat a) { int o = 0; return q_i128(a.n, a.d, &o); }
DcRat dc_q_to_rat(DcQ a, int *ovf) {
    DcRat r = {0, 1};
    if (!a.b) { r.n = a.n; r.d = a.d; return r; }
    M n, d; q_parts(a, &n, &d);
    if (m_fits63(n) && m_fits63(d)) { r.n = (int64_t)m_u128(n) * (a.n < 0 ? -1 : 1); r.d = (int64_t)m_u128(d); }
    else set_ovf(ovf, 1);
    m_free(&n); m_free(&d); return r;
}
static DcQ q_addsub(DcQ a, DcQ b, int neg, int *ovf) {
    if (!a.b && !b.b) {
        i128 bn = neg ? -(i128)b.n : (i128)b.n;
        return q_i128((i128)a.n * b.d + bn * a.d, (i128)a.d * b.d, ovf);
    }
    int sa = dc_q_sign(a), sb = dc_q_sign(b) * (neg ? -1 : 1);
    M an, ad, bn, bd; q_parts(a, &an, &ad); q_parts(b, &bn, &bd);
    M t1 = m_mul(an, bd), t2 = m_mul(bn, ad), den = m_mul(ad, bd), num; int s;
    if (!sb) { num = t1; s = sa; m_free(&t2); }
    else if (!sa) { num = t2; s = sb; m_free(&t1); }
    else if (sa == sb) { num = m_add(t1, t2); s = sa; m_free(&t1); m_free(&t2); }
    else {
        int c = m_cmp(t1, t2);
        if (c >= 0) { num = m_sub(t1, t2); s = sa; } else { num = m_sub(t2, t1); s = sb; }
        m_free(&t1); m_free(&t2);
    }
    m_free(&an); m_free(&ad); m_free(&bn); m_free(&bd);
    return q_make(s, num, den, ovf);
}
DcQ dc_q_add(DcQ a, DcQ b, int *ovf) { return q_addsub(a, b, 0, ovf); }
DcQ dc_q_sub(DcQ a, DcQ b, int *ovf) { return q_addsub(a, b, 1, ovf); }
DcQ dc_q_mul(DcQ a, DcQ b, int *ovf) {
    if (!a.b && !b.b) return q_i128((i128)a.n * b.n, (i128)a.d * b.d, ovf);
    int s = dc_q_sign(a) * dc_q_sign(b); if (!s) return QZERO;
    M an, ad, bn, bd; q_parts(a, &an, &ad); q_parts(b, &bn, &bd);
    M num = m_mul(an, bn), den = m_mul(ad, bd);
    m_free(&an); m_free(&ad); m_free(&bn); m_free(&bd);
    return q_make(s, num, den, ovf);
}
DcQ dc_q_div(DcQ a, DcQ b, int *ovf) {
    if (!dc_q_sign(b)) { set_ovf(ovf, 1); return QZERO; }
    if (!a.b && !b.b) return q_i128((i128)a.n * b.d, (i128)a.d * b.n, ovf);
    int s = dc_q_sign(a) * dc_q_sign(b); if (!s) return QZERO;
    M an, ad, bn, bd; q_parts(a, &an, &ad); q_parts(b, &bn, &bd);
    M num = m_mul(an, bd), den = m_mul(ad, bn);
    m_free(&an); m_free(&ad); m_free(&bn); m_free(&bd);
    return q_make(s, num, den, ovf);
}
int dc_q_cmp(DcQ a, DcQ b) {
    int sa = dc_q_sign(a), sb = dc_q_sign(b);
    if (sa != sb) return sa < sb ? -1 : 1;
    if (!sa) return 0;
    if (!a.b && !b.b) { i128 l = (i128)a.n * b.d, r = (i128)b.n * a.d; return l < r ? -1 : l > r; }
    M an, ad, bn, bd; q_parts(a, &an, &ad); q_parts(b, &bn, &bd);
    M l = m_mul(an, bd), r = m_mul(bn, ad); int c = m_cmp(l, r);
    m_free(&an); m_free(&ad); m_free(&bn); m_free(&bd); m_free(&l); m_free(&r);
    return sa > 0 ? c : -c;
}
DcQ dc_q_max(DcQ a, DcQ b) { return dc_q_cmp(a, b) >= 0 ? a : b; }
DcQ dc_q_min(DcQ a, DcQ b) { return dc_q_cmp(a, b) <= 0 ? a : b; }
DcQ dc_q_abs(DcQ a) { if (a.n < 0) a.n = -a.n; return a; }   /* big: flips the sign word only */
int dc_q_is_zero(DcQ a) { return a.n == 0; }
int dc_q_is_big(DcQ a) { return a.b != NULL; }
/* decimal digits of a into out (most significant first); returns length */
static size_t m_dec(M a, char *out) {
    if (!a.n) { out[0] = '0'; out[1] = 0; return 1; }
    M x = m_copy(a.v, a.n); size_t nch = 0; uint32_t *ch = xalloc(sizeof(uint32_t) * (a.n * 2 + 2));
    while (x.n) {
        dlimb rem = 0;
        for (size_t i = x.n; i-- > 0;) { dlimb cur = (rem << 32) | x.v[i]; x.v[i] = (limb)(cur / 1000000000u); rem = cur % 1000000000u; }
        m_norm(&x); ch[nch++] = (uint32_t)rem;
    }
    size_t len = (size_t)sprintf(out, "%u", ch[nch - 1]);
    for (size_t i = nch - 1; i-- > 0;) len += (size_t)sprintf(out + len, "%09u", ch[i]);
    free(ch); m_free(&x); return len;
}
const char *dc_q_str(DcQ a, char *buf, size_t n) {
    if (!a.b) {
        int k = a.d == 1 ? snprintf(buf, n, "%lld", (long long)a.n) : snprintf(buf, n, "%lld/%lld", (long long)a.n, (long long)a.d);
        if (k >= 0 && (size_t)k < n) return buf;
    }
    M num, den; q_parts(a, &num, &den);
    size_t cap = (num.n + den.n) * 10 + 24;
    char *t = xalloc(cap); size_t len = 0;
    if (a.n < 0) t[len++] = '-';
    len += m_dec(num, t + len);
    if (!m_is_one(den)) { t[len++] = '/'; len += m_dec(den, t + len); }
    t[len] = 0; m_free(&num); m_free(&den);
    char *dst = len < n ? buf : arena_alloc(len + 1);
    if (!dst) { free(t); return "?"; }
    memcpy(dst, t, len + 1); free(t); return dst;
}
static int m_parse(const char **s, M *out) {
    const char *p = *s; M a = m_new(1);
    if (*p < '0' || *p > '9') { m_free(&a); return -1; }
    while (*p >= '0' && *p <= '9') { M b = m_muladd(a, 10, (limb)(*p - '0')); m_free(&a); a = b; p++; }
    *s = p; *out = a; return 0;
}
int dc_q_parse(const char *s, DcQ *out) {
    int sign = 1; M num, den;
    if (*s == '-') { sign = -1; s++; }
    if (m_parse(&s, &num)) return -1;
    if (*s == '/') { s++; if (m_parse(&s, &den)) { m_free(&num); return -1; } }
    else den = m_from_u128(1);
    if (*s || !den.n) { m_free(&num); m_free(&den); return -1; }
    int ovf = 0; *out = q_make(sign, num, den, &ovf); return ovf ? -1 : 0;
}
