#!/usr/bin/env python3
"""m6-graded step 2 replayer for (Then (Output D1 Value) (Output D2 Value)) on two simulations (Fractions-free, independent
of the C code).  Extends tests/dcalc/m5/replay_m5.py (unchanged): a Then row is replayed by reading the two Derives, checking
that each is a CheckSimulation and target(first) = source(second), recomposing the declared relations R1 ; R2 (spec Table 4
l.893-909: Simulation arrows compose relationally), and re-checking the certificate with replay_m5.check_simulation against
the recomposed relation (every pair, observer, Match and Coverage).  Other rows go to replay_m5 unchanged.
usage: replay_then.py MODULE.metta OUT [MODULE.metta OUT ...]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'm5'))
import replay_m5 as R
from replay_m5 import field, head, need

_init = R.Module.__init__
def _init2(self, t): _init(self, t); self._raw = t
R.Module.__init__ = _init2

def replay_then(M, req, res):
    st = field(res, 'Status')[1]; need(st == 'Checked', 'Then replays Checked rows only')
    der = {x[1]: x[2] for x in M._raw[2:] if head(x) == 'Derive'}; sims = []
    for o in req[1:3]:
        need(head(o) == 'Output' and o[2] == 'Value' and o[1] in der, 'premise is not (Output Derive Value)')
        rq = der[o[1]]; need(head(rq) == 'CheckSimulation' and rq[1] in M.sim, 'premise %s is not a CheckSimulation' % o[1]); sims.append((o[1], rq[1]))
    (d1, h1), (d2, h2) = sims; s1, t1, _ = M.sim[h1]; s2, t2, _ = M.sim[h2]
    need(t1 == s2, 'target of %s is not the source of %s' % (h1, h2))
    comp = {(x, z) for (x, y) in M.rel(h1) for (y2, z) in M.rel(h2) if y == y2}
    v = field(field(res, 'Value'), 'ComposedArrow')
    need(field(v, 'Source')[1] == s1 and field(v, 'Target')[1] == t2 and field(v, 'Kind')[1] == 'Simulation', 'ComposedArrow Source/Target/Kind differ')
    ev = field(res, 'Evidence'); cm = field(ev, 'Composition')
    need(field(cm, 'Rule')[1] == 'RelationalComposition' and field(cm, 'First')[1:] == [d1, h1] and field(cm, 'Second')[1:] == [d2, h2], 'Composition rows differ')
    cert = field(ev, 'Certificate'); cn = field(cert, 'Relation')[1]
    need(cn not in M.sim, 'composite certificate reuses a declared simulation name')
    orel = M.rel; M.sim[cn] = (s1, t2, None); M.rel = lambda n: comp if n == cn else orel(n)
    try: R.check_simulation(M, cert, None)
    finally: del M.sim[cn]; M.rel = orel
    return st, ['ThenSimulation: R1;R2 recomposed (%d pairs), certificate rechecked' % len(comp)]

_line = R.replay_line
def replay_line2(M, req, res): return replay_then(M, req, res) if head(req) == 'Then' else _line(M, req, res)
R.replay_line = replay_line2
if __name__ == '__main__': sys.exit(R.main(sys.argv[1:]))
