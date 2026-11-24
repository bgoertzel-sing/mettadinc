/* Test driver for src/dcalc/qrat.c: reads lines "OP A B" (A, B as p/q of any
 * length) and prints the result; OP in add sub mul div cmp.  Argument "big"
 * forces every result through the bignum path (dc_q_force_big). */
#include "qrat.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "big")) dc_q_force_big = 1;
    static char line[1 << 16], op[8], a[1 << 15], b[1 << 15], buf[64];
    while (fgets(line, sizeof line, stdin)) {
        if (sscanf(line, "%7s %32767s %32767s", op, a, b) != 3) continue;
        DcQ x, y, r; int ovf = 0;
        if (dc_q_parse(a, &x) || dc_q_parse(b, &y)) { puts("PARSE_ERR"); continue; }
        if (!strcmp(op, "cmp")) { printf("%d\n", dc_q_cmp(x, y)); continue; }
        if (!strcmp(op, "add")) r = dc_q_add(x, y, &ovf);
        else if (!strcmp(op, "sub")) r = dc_q_sub(x, y, &ovf);
        else if (!strcmp(op, "mul")) r = dc_q_mul(x, y, &ovf);
        else if (!strcmp(op, "div")) r = dc_q_div(x, y, &ovf);
        else { puts("BAD_OP"); continue; }
        if (ovf) printf("OVF%d\n", ovf); else puts(dc_q_str(r, buf, sizeof buf));
        dc_q_arena_reset();
    }
    return 0;
}
