#!/usr/bin/env python3
"""Mutation harness skeleton (boundary 3, AC3).

For every module that carries an M0 claim, each mutant changes exactly one
row of one Table map to another element of the map's target carrier. Each
mutant is run through build/dcalc/dcalc, and its output goes through the
independent replay checker.
  * Soundness (required): every Checked/Refuted envelope of every mutant
    must still replay. A certificate must never survive a change to the
    module it certifies.
  * Sensitivity (reported): a mutant is "killed" when the status or value of
    some M0-claim request changes. The kill rate is printed. Later
    milestones raise it into a threshold as obligation generators grow.
Exit 0 iff no mutant breaks replay."""
import os, subprocess, sys, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import replay as R
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FIX = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package/fixtures')
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
TARGETS = {'eight_state.metta': ['EightState'],
           'hypotheses.metta': ['Staged', 'DescentConverse', 'LiteralCongruence', 'Surjectivity']}
LIMIT = int(os.environ.get('MUTANT_LIMIT', '200'))

def render(forms): return '\n'.join(R.show(f) for f in forms) + '\n'

def outcomes(text):
    res = {}
    for line in text.splitlines():
        if ' => ' not in line: continue
        head, env = line.split(' => ', 1); e = R.parse(env)[0]
        val = R.find(e, 'Value'); res[head] = (R.find(e, 'Status')[1], R.show(val) if val else '')
    return res

def mutants(forms, mods):
    for fi, f in enumerate(forms):
        if not (isinstance(f, list) and f and f[0] == 'DC.Module' and f[1] in mods): continue
        M = R.Module(f)
        for di, d in enumerate(f):
            if not (isinstance(d, list) and d and d[0] == 'Map' and len(d) == 5 and d[4][0] == 'Table'): continue
            dst = M.car.get(d[3][1], [])
            for ri, row in enumerate(d[4][1:], 1):
                for alt in dst:
                    if R.key(alt) == R.key(row[1]): continue
                    yield (fi, di, ri, alt, '%s/%s row %s -> %s' % (f[1], d[1], R.show(row[0]), R.show(alt)))

def run(path):
    p = subprocess.run([DCALC, path], capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout

def main():
    tmp = tempfile.mkdtemp(prefix='dcalc-mut-'); total = killed = broken = 0
    try:
        for fx, mods in TARGETS.items():
            src = os.path.join(FIX, fx); forms = R.parse(open(src, encoding='utf-8', errors='replace').read())
            base_path = os.path.join(tmp, 'base_' + fx); open(base_path, 'w').write(render(forms))
            rc, out = run(base_path); base = outcomes(out)
            for fi, di, ri, alt, label in mutants(forms, mods):
                if total >= LIMIT: break
                total += 1
                row = forms[fi][di][4][ri]; old = row[1]; row[1] = alt
                mp = os.path.join(tmp, 'mut.metta'); open(mp, 'w').write(render(forms)); row[1] = old
                rc, out = run(mp)
                if rc: broken += 1; print('CRASH', label); continue
                op = os.path.join(tmp, 'mut.out'); open(op, 'w').write(out)
                rp = subprocess.run([sys.executable, os.path.join(HERE, 'replay.py'), mp, op], capture_output=True, text=True)
                if rp.returncode: broken += 1; print('REPLAY BROKEN', label, rp.stdout.strip()[-200:])
                now = outcomes(out)
                if any(now.get(h) != v for h, v in base.items() if h.split(' ', 1)[0] in mods and v[0] in ('Checked', 'Refuted')): killed += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('mutation: %d mutants, %d killed (%.0f%%), %d broke replay or crashed' % (total, killed, 100.0 * killed / max(total, 1), broken))
    return 1 if broken else 0

if __name__ == '__main__':
    sys.exit(main())
