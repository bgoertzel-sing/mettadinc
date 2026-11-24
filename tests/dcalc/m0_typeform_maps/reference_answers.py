#!/usr/bin/env python3
"""Expected answers for fixtures/typeform_gates.metta from Ben's reference evaluator (docs/e0, doc04 bundle):
mg_eval.World reads the module text (it applies a map to values and ignores From/To), and models/dclib.py's
check_now / check_updates / check_abstraction_map give the canonical witness (least pair in carrier order,
actions and queries in declaration order).  This is the same machinery mg_oracle.py uses for doc04's
AnchorMigration and TaskResume.  Prints one line per request: <label>\t<status>\t<witness or ->.
Usage: reference_answers.py [fixture]   (default: fixtures/typeform_gates.metta)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
BUNDLE = os.path.join(ROOT, 'docs', 'e0', 'docs', '04_omega_memory_goals_part1', 'validation_bundle')
sys.path.insert(0, BUNDLE); sys.path.insert(0, os.path.join(BUNDLE, 'models'))
from mg_eval import World            # noqa: E402
from dclib import Machine, check_now, check_updates, check_abstraction_map   # noqa: E402

def sx(v):
    """A value as dcalc prints it: tuples as (Tuple ...), Bool as True/False."""
    if isinstance(v, tuple): return '(Tuple ' + ' '.join(sx(x) for x in v) + ')'
    if isinstance(v, bool): return 'True' if v else 'False'
    return str(v)

def main(path):
    W = World(path)
    def mach(mod, name):
        st, acts, obs = W.machine(mod, name)
        return Machine(st, acts, obs)
    for run in W.runs:
        mod, rq = run[1], run[2]
        label = '%s (%s)' % (mod, ' '.join(rq))
        head, arg = rq[0], rq[1]
        if head in ('CheckNow', 'CheckUpdates'):
            of, enc = W.representation(mod, arg)
            w = (check_now if head == 'CheckNow' else check_updates)(mach(mod, of), enc)
            wit = '-' if w is None else '(Pair %s %s)' % (sx(w['pair'][0]), sx(w['pair'][1]))
            if w is not None and head == 'CheckUpdates': wit += ' (Action %s)' % w['action']
            if w is not None and head == 'CheckNow': wit += ' (Observe %s)' % w['query']
        elif head == 'CheckAbstractionMap':
            src, tgt, h = W.abstraction_map(mod, arg)
            w = check_abstraction_map(mach(mod, src), mach(mod, tgt), h)
            wit = '-' if w is None else '(State %s) (%s %s)' % (sx(w['state']), 'Action' if 'action' in w else 'Observe', w.get('action', w.get('query')))
        else:
            raise SystemExit('unsupported request ' + label)
        print('%s\t%s\t%s' % (label, 'Checked' if w is None else 'Refuted', wit))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'fixtures', 'typeform_gates.metta'))
