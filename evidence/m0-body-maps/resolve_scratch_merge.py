
import re
p='/tmp/bodymaps/wt-merge/src/dcalc/model.c'
s=open(p).read()
blocks=list(re.finditer(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n', s, re.S))
assert len(blocks)==2
b1,b2=blocks
second = '''        if (bvar) snprintf(lab, sizeof lab, "Body"); else snprintf(lab, sizeof lab, "row %zu", hit - 1);
        int ok = 1; allow_xor = m->neural; logic_on(m); Sx *v = cases || bvar ? eval_body(out, &e, &ok) : sx_copy(out); allow_xor = 0; logic_off();
        if (ok == 4) { char *xs = sx_print(D->elems[i]); fail(err, es, "Map %s: %s%s on %s: %s", nm, bvar ? "" : "Cases ", lab, xs, logic_why); free(xs); sx_free(v); free(tab); return -1; }
        if (ok == 2 && logic_why[0]) { sx_free(v); free(tab); fail(err, es, "[M0] Map %s: %s%s: %s", nm, bvar ? "" : "Cases ", lab, logic_why); snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1; }
        if (ok == 2) { sx_free(v); free(tab); fail(err, es, "[M0] Map %s: %s%s uses an operator outside the M0 fragment", nm, bvar ? "" : "Cases ", lab); snprintf(pending_why, sizeof pending_why, "%s", err + 5); return -1; }
        if (ok == 3) { sx_free(v); free(tab); return fail(err, es, "Map %s: %s%s: integer overflow or out-of-range literal in Add/Mul", nm, bvar ? "" : "Cases ", lab); }
'''
s = s[:b1.start()] + b1.group(2) + s[b1.end():b2.start()] + second + s[b2.end():]
old = 'allow_xor = m->neural; Sx *v = eval_body(body->items[2], &e, &ok); allow_xor = 0;\n            char *xs = sx_print(F->elems[i]);\n'
assert old in s
s = s.replace(old, 'allow_xor = m->neural; logic_on(m); Sx *v = eval_body(body->items[2], &e, &ok); allow_xor = 0; logic_off();\n            char *xs = sx_print(F->elems[i]);\n            if (ok == 4) { fail(err, es, "Map %s: Body on %s: %s", nm, xs, logic_why); free(xs); sx_free(v); free(mp->table); return -1; }\n')
open(p,'w').write(s)
