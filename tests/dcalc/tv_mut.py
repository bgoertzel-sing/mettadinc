#!/usr/bin/env python3
"""Mutation gate for the M3 translation-validation suite (t-2026-11-11-mettadinc-m3-tv-suite).

Takes the production CNFs dumped by build/dcalc/tv_m3 and mutates them four ways:
  drop    - one clause removed
  flip    - one literal negated
  varmap  - every occurrence of one primary (word-bit) variable renamed to another
  vacuous - a clause making the CNF contradictory (unit -true), or forcing the goal
            false (unit -goal): UNSAT whatever the obligation says
For each operator the gate searches, deterministically, for a mutant whose CNF + goal
unit is UNSAT under the pinned CaDiCaL and whose LRAT proof cake_lpr VERIFIES, preferring
targets whose real obligation is SAT (so that proof would back a false Checked).  Every
such proof-checked mutant, and a fixed sample of other mutants, is run through
tv_m3.check_tv.  A mutant TV accepts is an equivalent mutant (TV's acceptance proves it
encodes the same obligation on every x); the solver must agree (UNSAT iff the real
obligation is UNSAT), else the gate fails.  The gate also fails if an operator finds no
proof-checked mutant that TV rejects.
usage: tv_mut.py MODULE TVDIR WORKDIR      (needs DCALC_CADICAL, DCALC_CAKE_LPR)"""
import sys, os, glob, random, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tv_m3

def write_tv(path, t, cls):
    with open(path, 'w') as f:
        f.write('c tv mutant\nc goal %d\nc prim %d\nc tru %d\n' % (t['goal'], t['prim'], t['tru']))
        f.write('c kind %s\n' % ' '.join(t['kind']))
        for (p, b, w) in t['tests']: f.write('c test %s %d %s\n' % (p, b, ' '.join(w)))
        f.write('p cnf %d %d\n' % (t['nv'], len(cls)))
        for c in cls: f.write(' '.join(map(str, c)) + ' 0\n')

def prove(work, t, cls):
    """Like sym_prove: CNF + goal unit -> CaDiCaL --lrat -> cake_lpr.  'checked', 'sat' or 'error'."""
    cf, lf = os.path.join(work, 'm.cnf'), os.path.join(work, 'm.lrat')
    allc = cls + [[t['goal']]]
    with open(cf, 'w') as f:
        f.write('p cnf %d %d\n' % (t['nv'], len(allc)))
        for c in allc: f.write(' '.join(map(str, c)) + ' 0\n')
    r = subprocess.run([os.environ['DCALC_CADICAL'], '-q', '--no-binary', '--lrat', cf, lf], capture_output=True)
    if r.returncode == 10: return 'sat'
    if r.returncode != 20: return 'error'
    r = subprocess.run([os.environ['DCALC_CAKE_LPR'], cf, lf], capture_output=True, text=True)
    return 'checked' if r.returncode == 0 and 's VERIFIED UNSAT' in r.stdout else 'error'

def mutants(op, t, rng, n):
    cls, tru, g, P = t['cls'], t['tru'], t['goal'], t['prim']
    if op == 'varmap':
        # every ordered pair (a, b) where primary a actually occurs in the CNF: random pairs
        # mostly hit bits the obligation never reads, which leaves the CNF unchanged
        occ = sorted({abs(l) for c in cls for l in c if abs(l) <= P})
        for a in occ:
            for b in range(1, P + 1):
                if b != a: yield 'variable x%d read as x%d' % (a, b), [[(b if l > 0 else -b) if abs(l) == a else l for l in c] for c in cls]
        return
    if op == 'vacuous':
        yield 'add unit -true', cls + [[-tru]]
        yield 'add unit -goal', cls + [[-g]]
        return
    for _ in range(n):
        i = rng.randrange(len(cls))
        if cls[i] == [tru]: continue
        if op == 'drop': yield 'drop clause %d %s' % (i, cls[i]), cls[:i] + cls[i + 1:]
        elif op == 'flip':
            j = rng.randrange(len(cls[i])); c = list(cls[i]); c[j] = -c[j]
            yield 'flip literal %d of clause %d %s' % (j, i, cls[i]), cls[:i] + [c] + cls[i + 1:]

def main(module, tvdir, work):
    os.makedirs(work, exist_ok=True)
    sm = tv_m3.load_module(module); rng = random.Random(20261111)
    files = sorted(glob.glob(os.path.join(tvdir, '*.tv')))
    base = {}
    for p in files:
        ok, msg, ns = tv_m3.check_tv(sm, p)
        if not ok: print('baseline %s FAILS translation validation: %s' % (p, msg)); return 1
        base[p] = ns
    targets = [p for p in files if base[p] > 0] + [p for p in files if base[p] == 0]   # real-SAT first
    bad = 0
    for op, kind in [(o, k) for o in ('drop', 'flip', 'varmap', 'vacuous') for k in ('partition', 'minimize', 'now')]:
        found, tried, rejected, equiv = None, 0, 0, 0
        for p in [q for q in targets if os.path.basename(q).startswith(kind + '-')]:
            t = tv_m3.read_tv(p)
            for desc, cls in mutants(op, t, rng, 40):
                tried += 1; st = prove(work, t, cls)
                if st != 'checked' and tried > 12: continue          # sample: TV-check the first 12 of any status
                mp = os.path.join(work, '%s-%d.tv' % (op, tried)); write_tv(mp, t, cls)
                ok, msg, _ = tv_m3.check_tv(sm, mp)
                if ok:
                    # TV accepting a mutant is a proof (unit propagation is sound) that the mutant
                    # still encodes the same obligation on every x: an equivalent mutant, e.g. a
                    # flipped literal in a gate whose value is masked.  Cross-check that with the
                    # solver: its UNSAT status must match the real obligation's.
                    if (st == 'checked') != (base[p] == 0) or st == 'error':
                        bad += 1; print('  %-8s %s on %s (proof %s, real %s): PASSED translation validation -- gate broken'
                                        % (op, desc, os.path.basename(p), st, 'SAT' if base[p] else 'UNSAT'))
                    else: equiv += 1
                else: rejected += 1
                if st == 'checked' and not ok and found is None:
                    found = (os.path.basename(p), desc, base[p], msg)
            # stop at the first proof-checked mutant of a real-SAT target; once only real-UNSAT
            # targets remain (drop never makes a satisfiable CNF UNSAT), stop at the first one,
            # and never TV-check more than 60 mutants per operator
            if found and (found[2] > 0 or base[p] == 0): break
            if rejected >= 60: break
        if not found: bad += 1; print('%-8s %-9s FAIL  no mutant with a cake_lpr-checked proof found' % (op, kind)); continue
        print('%-8s %-9s PASS  %s on %s (real obligation %s): LRAT proof VERIFIED by cake_lpr, translation validation rejects: %s  [%d mutants tried; TV rejected %d, %d were equivalent (same obligation, solver agrees)]'
              % (op, kind, found[1], found[0], 'SAT, so this would be a false Checked' if found[2] else 'UNSAT', found[3][:90], tried, rejected, equiv))
    print('tv_mut: %s' % ('PASS' if not bad else 'FAIL'))
    return 1 if bad else 0

if __name__ == '__main__':
    if len(sys.argv) != 4 or not os.environ.get('DCALC_CADICAL') or not os.environ.get('DCALC_CAKE_LPR'):
        print(__doc__.split('\n')[-1]); sys.exit(2)
    sys.exit(main(*sys.argv[1:]))
