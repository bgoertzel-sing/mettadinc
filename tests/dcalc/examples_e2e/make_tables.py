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
def main():
    per = collections.defaultdict(list)
    for rid, doc, d, mod, libs in RUNS: per[doc].append((rid, d, mod))
    for doc, runs in sorted(per.items()):
        L = ['# Document %s: per-request CLI answers' % doc, '',
             '| run | module | request | release | beyond | reason (beyond) | bundle expects |', '|---|---|---|---|---|---|---|']
        tot = collections.Counter()
        for rid, d, mod in runs:
            rel, bey = load(rid + '_release'), load(rid + '_beyond')
            exp = inline_expect(os.path.join(E, d, mod))
            assert len(rel) == len(bey), rid
            for a, b in zip(rel, bey):
                assert a[:2] == b[:2], (rid, a, b)
                e = exp.get((a[0], a[1]), '')
                L.append('| %s | %s | `%s` | %s | %s | %s | %s |' % (rid, a[0], a[1].replace('|', '\\|'), a[2], b[2], b[3].replace('|', '\\|'), e))
                tot[(rid, a[2], b[2])] += 1
        L += ['', '## Totals (run, release, beyond): count', ''] + ['- %s %s/%s: %d' % (k + (v,)) for k, v in sorted(tot.items())]
        open(os.path.join(H, DOCS[doc]), 'w').write('\n'.join(L) + '\n')
        print(DOCS[doc], sum(tot.values()), 'rows')
if __name__ == '__main__': main()
