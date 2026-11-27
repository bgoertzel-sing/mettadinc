#!/usr/bin/env python3
"""Build one per-request markdown table per document from out/<id>_{release,beyond}.tsv (written by run_e2e.py).
Columns: module, request, release status, beyond status, reason (beyond), and the bundle's own inline expectation
(trailing '; InvalidInput' style comment or 'negative fixture' comment block above the request) when present."""
import csv, os, re, collections
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, 'out')
from run_e2e import RUNS, E
DOCS = {'03': 'doc03_four_worked_examples.md', '04': 'doc04_omega_memory_goals.md',
        '05': 'doc05_live_memory.md', '06': 'doc06_wmtm_worked_example.md'}
ST = r'(Checked|Refuted|Conditional|Unsupported|InvalidInput|Inconclusive)'
def load(tag):
    with open(os.path.join(OUT, tag + '.tsv')) as fh:
        r = csv.reader(fh, delimiter='\t'); next(r); return list(r)
def inline_expect(path):
    """(module, request) -> expectation from the module source: a status word in a trailing '; ...' comment on the
    request, or in the ';;' comment block directly above it. Multi-line requests are joined (whitespace collapsed)."""
    exp = {}; pend = ''; buf = None
    for l in open(path):
        t = l.rstrip('\n')
        if buf is not None:
            buf += ' ' + t
        elif t.startswith('!(dc.run'):
            buf = t
        else:
            if t.startswith(';;'):
                s = re.search(ST, t)
                if s: pend = s.group(1) + ' (fixture comment)'
            else: pend = ''
            continue
        code, _, com = buf.partition(';')
        if code.count('(') - code.count(')') > 0: continue
        code = ' '.join(code.split())
        m = re.match(r'^!\(dc\.run (\S+) (.*)\)$', code)
        if m:
            s = re.search(ST, com)
            e = s.group(1) if s else pend
            if e: exp[(m.group(1), m.group(2))] = e
        buf = None
    return exp
def load_doc():
    """(run, 1-based request index) -> (document answer, source) from doc_expected.tsv (hand-transcribed)."""
    d = {}
    with open(os.path.join(H, 'doc_expected.tsv')) as fh:
        r = csv.reader(fh, delimiter='\t'); next(r)
        for run, idx, ans, src in r: d[(run, int(idx))] = (ans, src)
    return d
MS = {'ex3': 'M6', 'ex4': 'M4'}
def classify(rid, mode, st, reason, doc):
    """One class per (mode, answer). Order matters: specific causes before generic ones."""
    dw = re.match(ST + '|Estimated', doc)
    dw = dw.group(0) if dw else ''
    if st == dw: return 'match' + (' (negative fixture)' if st == 'InvalidInput' else '')
    if doc.startswith('value:') and st in ('Checked', 'Refuted'):
        return 'VALUE: the document gives a value, not a status word; dcalc answers %s, the value itself is not compared' % st
    if st == 'Unknown' and doc.startswith('Unknown'): return 'match'
    if st == 'Unsupported' and rid == 'ex2' and ('outside this step of M3' in reason or 'limit' in reason
                                                 or 'not implemented by the symbolic engine' in reason):
        return 'GAP: symbolic-engine limit for Families modules (t-2026-11-24-mettadinc-families follow-ups); Unsupported, not InvalidInput'
    if mode == 'release' and st == 'Unsupported' and rid in MS:
        return 'match: doc03 s2.6 says %s is a %s target, Unsupported in the first release' % (rid, MS[rid])
    if st == 'Unsupported' and 'backend fragment' in reason:
        return 'GAP: valid by the spec (l.1719 Reach carrier) but outside the stochastic backend fragment; Unsupported since t-2026-11-23-mettadinc-lowering-unsupported, Reach support in the stochastic reader is a later task'
    # t-2026-11-26-mettadinc-natarith-v2 review 1 finding 1: rows that NatArith admission moves past the library gate
    # land on engine limits; name them before the generic 'carrier' rule below (which is for the stochastic reader).
    if st == 'Unsupported' and 'outside the transfer table engine fragment' in reason:
        return 'GAP: transfer-engine limit (MethodSystem States/Methods carrier outside the transfer table engine fragment); Unsupported, not InvalidInput'
    if st == 'Unsupported' and 'outside the contract table engine fragment' in reason:
        return 'GAP: contract-engine limit (Ideal/Actual Map outside the contract table engine fragment); Unsupported, not InvalidInput'
    if st == 'Unsupported' and 'tolerance option is not implemented' in reason:
        return 'GAP: (Within d) tolerance option not implemented in the transfer engine; Unsupported, not InvalidInput'
    if st == 'Unsupported' and reason.startswith('Families:') and 'not a declared map with a Body' in reason:
        return 'GAP: Families port map is not a declared Body map (lowering limit); Unsupported, not InvalidInput'
    if st == 'Unsupported' and 'the import inliner copies only' in reason:
        return 'GAP: the import inliner copies only Carrier/Map/Tolerance, so an imported MethodSystem or Derive is not visible; Unsupported, not InvalidInput'
    if st == 'Unsupported' and re.search(r'premise Derive \S+ is Unsupported', reason):
        return 'GAP: a ComposeTransfers premise is itself Unsupported (engine limit upstream); Unsupported, not InvalidInput'
    if st == 'Unsupported' and 'a bare Representation name' in reason:
        return 'GAP: a bare Representation name is not evaluated, only (Output D Representation); Unsupported, not InvalidInput'
    if st == 'Unsupported' and 'is evaluated only on a (Use Hyperseed) module' in reason:
        return 'GAP: (Output D Representation) is evaluated only on a Hyperseed module (M7); Unsupported, not InvalidInput'
    if st == 'Unsupported' and re.search(r'premise Derive \S+ is outside the M[0-9] fragment', reason):
        return 'GAP: an InduceApprox premise is outside the M2 fragment; Unsupported, not InvalidInput'
    if 'map-call cycle' in reason: return 'BUG: false map-call cycle, Map named like an Enum element (admit.c:776)'
    if 'Reach' in reason or 'carrier' in reason.lower(): return 'BUG: stochastic reader rejects Reach carrier (stoch.c:52)'
    if 'Import of unknown module' in reason: return 'CLI: release mode ignores LIBS (main.c:129)'
    m = re.search(r'library (\w+) is outside', reason)
    if m:
        c = 'GATED: PROPOSED library %s admitted by no milestone' % m.group(1)
        if rid == 'ex2': c += '; CONTRADICTS doc03 s2.6 (ex2 declared within the first release)'
        return c
    if 'Profile Dynamics Stochastic is outside the first release' in reason:
        return 'GATED: stochastic profile outside the first release (doc03 s2.6: first release covers deterministic dynamics)'
    m = re.search(r'Profile ([\\w ]+?) is outside the first release', reason)
    if m: return 'GATED: Profile %s outside the first release (release gate, stoch profile is post-M0)' % m.group(1)
    if 'request CheckBlockPartition is outside the M0 fragment' in reason:   # t-2026-11-26-mettadinc-families-followups-v2 step 4
        return 'GAP: CheckBlockPartition is outside the M0 fragment on a Crisp module (the M0 lowering has no block-partition request); Unsupported, not InvalidInput'
    # review 1 finding 1: the generic rule below used to label every 'outside the M[0-9] fragment' row as the (g)
    # blocker, which is lowered; name the actual cause first.
    m = re.search(r'\((Eq|And|Or|Not|If) \.\.\.\) in a Cases body is lowered only in a Crisp module', reason)
    if st == 'Unsupported' and m:
        return 'GAP: (%s ...) in a Cases body is lowered only in a Crisp module, not in a Graded profile; Unsupported, not InvalidInput' % m.group(1)
    m = re.search(r'request (\w+) is outside the M0 fragment', reason)
    if st == 'Unsupported' and m:
        return 'GAP: request %s has no M0 lowering; Unsupported, not InvalidInput' % m.group(1)
    m = re.search(r'(Machine|Representation|Map) \S+ is outside the (M[0-9]) fragment', reason)
    if st == 'Unsupported' and m:
        return 'GAP: a %s is outside the %s fragment (lowering limit, see the reason); Unsupported, not InvalidInput' % (m.group(1), m.group(2))
    if re.search(r'outside the M[0-9] fragment', reason):
        # t-2026-11-26-mettadinc-natarith-v2 review 1 finding 1: the old label named blocker (g), which is lowered;
        # with NatArith admitted these rows reach the M0/M2 fragment check itself, so say that.
        return 'GAP: the request, Machine or Representation is outside the M0/M2 fragment the checker decides (engine limit, not a lowering blocker); Unsupported, not InvalidInput'
    return 'UNCLASSIFIED'
def main():
    per = collections.defaultdict(list); D = load_doc()
    for rid, doc, d, mod, libs in RUNS: per[doc].append((rid, d, mod))
    for doc, runs in sorted(per.items()):
        L = ['# Document %s: per-request comparison' % doc, '',
             'Columns: the document\'s answer (with its source), our answer in release and in --beyond-release mode, the class of each answer, and the beyond-mode reason. See README for the class legend.', '',
             '| run | # | module | request | document answer | source | release | beyond | class (release) | class (beyond) | reason (beyond) |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
        tot = collections.Counter()
        for rid, d, mod in runs:
            rel, bey = load(rid + '_release'), load(rid + '_beyond')
            assert len(rel) == len(bey), rid
            for i, (a, b) in enumerate(zip(rel, bey), 1):
                assert a[:2] == b[:2], (rid, a, b)
                ans, src = D[(rid, i)]
                cr = classify(rid, 'release', a[2], a[3], ans); cb = classify(rid, 'beyond', b[2], b[3], ans)
                esc = lambda x: x.replace('|', '\\|')
                L.append('| %s | %d | %s | `%s` | %s | %s | %s | %s | %s | %s | %s |' % (rid, i, a[0], esc(a[1]), esc(ans), src, a[2], b[2], cr, cb, esc(b[3])))
                tot[('release', cr.split(':')[0].split(' (')[0])] += 1; tot[('beyond', cb.split(':')[0].split(' (')[0])] += 1
        L += ['', '## Class totals (mode, class): count', ''] + ['- %s %s: %d' % (k + (v,)) for k, v in sorted(tot.items())]
        open(os.path.join(H, DOCS[doc]), 'w').write('\n'.join(L) + '\n')
        print(DOCS[doc], dict(tot))
if __name__ == '__main__': main()
