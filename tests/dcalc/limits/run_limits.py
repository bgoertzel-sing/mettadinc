#!/usr/bin/env python3
"""Review 4 F2/F3: capacity, checked arithmetic and non-finite bounds.

Runs dcalc (env DCALC, default build/dcalc/dcalc) on each fixture here and
requires exit code 0 plus the expected Status/Reason per row.  Run it with a
sanitized DCALC as well: any out-of-bounds write or signed overflow aborts
there with a nonzero exit code and fails the suite."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
OVF = 'integer overflow or out-of-range literal in Add/Mul'
FIN = 'field Within is not a finite non-negative number'
EXPECT = {
    'too_many': [('InvalidInput', 'too many representations')],
    'overflow_add': [('InvalidInput', OVF)],
    'overflow_mul': [('InvalidInput', OVF)],
    'overflow_literal': [('InvalidInput', OVF)],
    'bounds': [('InvalidInput', FIN + ' (nan)'), ('InvalidInput', FIN + ' (inf)'),
               ('InvalidInput', FIN + ' (-inf)'), ('InvalidInput', FIN + ' (1e999)'),
               ('InvalidInput', FIN + ' (-1)'), ('Checked', None)],
}

def main():
    rc = 0
    for name, want in sorted(EXPECT.items()):
        cp = subprocess.run([DCALC, os.path.join(HERE, name + '.metta')], capture_output=True, text=True)
        rows = [l for l in cp.stdout.splitlines() if ' => ' in l]
        ok = cp.returncode == 0 and len(rows) == len(want)
        for row, (st, reason) in zip(rows, want):
            m = re.search(r'\(Status (\w+)\)', row)
            if not m or m.group(1) != st or (reason and reason not in row): ok = False
        print('%s %s (rc=%d, %d rows)' % ('PASS' if ok else 'FAIL', name, cp.returncode, len(rows)))
        if not ok:
            rc = 1; sys.stdout.write(cp.stderr[-400:])
    print('limits: %s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc

if __name__ == '__main__': sys.exit(main())
