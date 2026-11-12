#!/usr/bin/env python3
"""M4 source-level mutants of the obligation generator (t-2026-11-11-mettadinc-m4).

Each mutant copies src/dcalc/ops_sym.c to build/dcalc/srcmut/<id>/, applies ONE textual
mutation inside a named CNF generator, rebuilds tests/dcalc/tv_m3.c against the copy
(-I<copy> before -Isrc/dcalc), dumps the run_tv.sh obligation set and runs
tests/dcalc/tv_m3.py check.  A real mutant must be KILLED (dump or check fails);
the identity canary (no mutation) must SURVIVE, so a broken harness cannot pass.
No fixture under tests/dcalc/mutations/ is used.  Exit 0 iff every verdict is as required."""
import os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC = os.path.join(ROOT, 'src/dcalc'); LIB = os.path.join(ROOT, 'build/dcalc/libdcalc.a')
OUT = os.path.join(ROOT, 'build/dcalc/srcmut'); M = os.path.join(ROOT, 'tests/dcalc/tv/tv_small.metta')
CC = os.environ.get('CC', 'gcc')
OBL = ['partition:ZeroTailOnly:ZeroMachine', 'partition:ZeroTailReach:ZeroReach', 'partition:Gappy:ZeroMachine',
       'partition:ByX0:ZeroMachine', 'minimize:ZeroMachine', 'minimize:ParityMachine', 'minimize:ZeroMachine:1',
       'minimize:ParityMachine:2', 'minimize:ZeroMachine:3', 'now:KeepX0', 'now:KeepX1']
# (id, function anchor, old text (first occurrence after the anchor), new text)
MUTANTS = [
    ('identity',            None, None, None),
    ('now-viol-and',        'static int sym_cnf_now(', 'viol = cnf_or(c, viol, cnf_xor(', 'viol = cnf_and(c, viol, cnf_xor('),
    ('now-goal-or',         'static int sym_cnf_now(', '*goal = cnf_and(c, same, viol);', '*goal = cnf_or(c, same, viol);'),
    ('now-drop-same',       'static int sym_cnf_now(', '*goal = cnf_and(c, same, viol);', '*goal = viol;'),
    ('min-same-sign',       'static int sym_cnf_minimize(', 'same = cnf_and(c, same, -cnf_xor(c, lx, ly));', 'same = cnf_and(c, same, cnf_xor(c, lx, ly));'),
    ('min-goal-or',         'static int sym_cnf_minimize(', '*goal = cnf_and(c, same, viol);', '*goal = cnf_or(c, same, viol);'),
    ('part-disjoint-or',    'static int sym_cnf_partition(', 'OBL("Disjointness", cnf_and(c, Bl[i], Bl[j]));', 'OBL("Disjointness", cnf_or(c, Bl[i], Bl[j]));'),
    ('part-constancy-flip', 'static int sym_cnf_partition(', '((t >> k) & 1) ? -ob.b[k] : ob.b[k]', '((t >> k) & 1) ? ob.b[k] : -ob.b[k]'),
    ('part-stability-sign', 'static int sym_cnf_partition(', 'OBL("Stability", cnf_and(c, Bl[i], -by));', 'OBL("Stability", cnf_and(c, Bl[i], by));'),
    ('part-goal-drop-C',    'static int sym_cnf_partition(', '*goal = cnf_and(c, C, viol);', '*goal = viol;'),
]
def main():
    base = open(os.path.join(SRC, 'ops_sym.c'), encoding='utf-8').read()
    only = set(sys.argv[1:]); bad = 0
    for mid, anchor, old, new in MUTANTS:
        if only and mid not in only: continue
        d = os.path.join(OUT, mid); shutil.rmtree(d, ignore_errors=True); os.makedirs(os.path.join(d, 'tv'))
        text = base
        if anchor:
            a = base.find(anchor); i = base.find(old, a) if a >= 0 else -1
            nxt = base.find('\nstatic ', a + 1)
            if a < 0 or i < 0 or (nxt >= 0 and i > nxt):
                print('%-22s HARNESS-ERROR  mutation site not found in %s' % (mid, anchor)); bad += 1; continue
            text = base[:i] + new + base[i + len(old):]
        open(os.path.join(d, 'ops_sym.c'), 'w', encoding='utf-8').write(text)
        exe = os.path.join(d, 'tv_m3')
        cc = subprocess.run([CC, '-std=c11', '-O1', '-w', '-I' + d, '-I' + SRC, '-o', exe,
                             os.path.join(ROOT, 'tests/dcalc/tv_m3.c'), LIB, '-lm'], capture_output=True, text=True)
        if cc.returncode:
            print('%-22s HARNESS-ERROR  compile failed: %s' % (mid, cc.stderr.strip().splitlines()[-1:] )); bad += 1; continue
        dump = subprocess.run([exe, M, os.path.join(d, 'tv')] + OBL, capture_output=True, text=True, timeout=120)
        chk = subprocess.run([sys.executable, os.path.join(ROOT, 'tests/dcalc/tv_m3.py'), 'check', M, os.path.join(d, 'tv')],
                             capture_output=True, text=True, timeout=300) if dump.returncode == 0 else None
        open(os.path.join(d, 'check.out'), 'w').write((chk.stdout + chk.stderr) if chk else dump.stdout + dump.stderr)
        killed = dump.returncode != 0 or chk.returncode != 0
        why = 'dump rc %d' % dump.returncode if dump.returncode else ('%d CNF check FAIL' % chk.stdout.count('FAIL') if killed else 'all CNFs agree')
        want_killed = mid != 'identity'; ok = killed == want_killed; bad += not ok
        print('%-22s %-8s %s  (%s)' % (mid, 'KILLED' if killed else 'SURVIVED', 'PASS' if ok else 'FAIL', why), flush=True)
    print('src_mutants: %s' % ('PASS' if not bad else 'FAIL (%d)' % bad)); return 1 if bad else 0
if __name__ == '__main__':
    sys.exit(main())
