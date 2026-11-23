#!/usr/bin/env python3
"""Which M0 gaps still block doc04 TaskResume once Like is lowered (t-2026-11-23-mettadinc-m0-like-machines).

Starts from module TRL of fixtures/taskresume_like.metta (every form but Like desugared; all five requests give
doc04's answers) and puts back ONE original form at a time, then prints the status of each of the five requests:
  c  derive1 as written in doc04 (Cases with If/And/Eq)                         gap (c)
  a  needs-revalidation and available declared (To Bool)                        gap (a)
  b  checkpoint-with-reads declared (To (Tuple Symbol Symbol Symbol Symbol))   gap (b)
  f  checkpoint-with-reads as written in doc04, (Body ($x) $x)                  Body map in a Crisp module
Report only (no gate): python3 tests/dcalc/m0_like/ablate_taskresume.py [--beyond-release]
"""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DC = os.environ.get('DCALC', os.path.join(ROOT, 'build', 'dcalc', 'dcalc'))
text = open(os.path.join(HERE, 'fixtures', 'taskresume_like.metta')).read()
trl = text[text.index('(DC.Module TRL'):text.index('(DC.Module TRW')]
def table_of(name):
    return re.search(r'  \(Map %s \(From Task\) \(To [^)]*\)\n    \(Table [^\n]*\)\)\n' % re.escape(name), trl).group(0)
DERIVE1 = ('  (Map derive1 (From Task) (To Task)\n    (Cases ((Tuple $v1 $v2 $r $f)\n      (If (And (Eq $v1 valid) (Eq $r none))\n'
           '          (Tuple $v1 $v2 r1 current)\n          (Tuple $v1 $v2 $r $f)))))\n')
VARIANTS = {
    'none (TRL as is)': lambda s: s,
    'c: derive1 with If/And/Eq': lambda s: s.replace(table_of('derive1'), DERIVE1),
    'a: Observe maps (To Bool)': lambda s: s.replace(table_of('needs-revalidation'), table_of('needs-revalidation').replace('(To YN)', '(To Bool)'))
                                            .replace(table_of('available'), table_of('available').replace('(To YN)', '(To Bool)')),
    'b: checkpoint-with-reads (To (Tuple ...))': lambda s: s.replace(table_of('checkpoint-with-reads'),
                                            table_of('checkpoint-with-reads').replace('(To Task)', '(To (Tuple Symbol Symbol Symbol Symbol))')),
    'f: checkpoint-with-reads (Body ($x) $x)': lambda s: s.replace(table_of('checkpoint-with-reads'),
                                            '  (Map checkpoint-with-reads (From Task) (To Task)\n    (Body ($x) $x))\n'),
}
mode = [a for a in sys.argv[1:] if a == '--beyond-release']
for name, f in VARIANTS.items():
    src = f(trl); assert name.startswith('none') or src != trl, name
    with tempfile.NamedTemporaryFile('w', suffix='.metta', delete=False) as fh: fh.write(src)
    o = subprocess.run([DC] + mode + [fh.name], capture_output=True, text=True, timeout=300); os.unlink(fh.name)
    out = []
    for l in o.stdout.splitlines():
        if ' => ' not in l: continue
        k, v = l.split(' => ', 1)
        st = re.search(r'\(Status ([A-Za-z]+)\)', v).group(1); rs = re.search(r'\(Reason "([^"]*)"', v)
        out.append('    %-30s %-12s %s' % (k[4:], st, rs.group(1) if rs else ''))
    print(name); print('\n'.join(out))
