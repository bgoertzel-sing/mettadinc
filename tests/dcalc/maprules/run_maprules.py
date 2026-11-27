#!/usr/bin/env python3
"""t-2026-11-26-mettadinc-shared-loader acceptance 1: one map per shared rule (maprules.h) per loader/profile.
Every rule-breaking module must answer InvalidInput with the expected reason, every control must be decided,
in both modes (release and --beyond-release).  Expected table: expected.txt.  Binary: $DCALC_MAPRULES_DC/dcalc
(default build/dcalc/dcalc).  Used unchanged by run_maprules_mutants.py on the call-removed builds."""
import os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
DC = os.path.join(os.environ.get('DCALC_MAPRULES_DC', os.path.join(ROOT, 'build', 'dcalc')), 'dcalc')
exp = {}
for l in open(os.path.join(HERE, 'expected.txt')):
    if l.startswith('#') or l.count('|') != 4: continue
    f, md, mod, st, why = l.rstrip('\n').split('|'); exp.setdefault((f, md), []).append((mod, st, why))
fails = n = 0
for (f, md), want in sorted(exp.items()):
    args = [DC] + ([] if md == 'rel' else [md]) + [os.path.join(HERE, 'fixtures', f + '.metta')]
    out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=600).stdout.splitlines()
    got = {}
    for s in out:
        m = re.search(r'Status ([A-Za-z]+)', s); r = re.search(r'Reason "([^"]*)"', s)
        got[s.split(' ', 1)[0]] = (m.group(1) if m else '', r.group(1) if r else '')
    for mod, st, why in want:
        n += 1; g = got.get(mod, ('<none>', ''))
        ok = g == (st, why)
        print('%s  %s %s %s: %s%s' % ('PASS' if ok else 'FAIL', f, md, mod, st, '' if ok else '  :: got %s %r' % g))
        fails += not ok
print('run_maprules: %s (%d rows)' % ('PASS' if fails == 0 else 'FAIL (%d)' % fails, n))
sys.exit(1 if fails else 0)
