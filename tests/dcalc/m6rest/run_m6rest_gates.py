#!/usr/bin/env python3
"""M6-rest gates (beyond release only).  Each check prints PASS/FAIL; exit 1 on any FAIL."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '../../..'))
DCALC = os.path.join(ROOT, 'build/dcalc/dcalc'); OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m6rest')); os.makedirs(OUT, exist_ok=True)
fails = 0
def report(name, ok, detail=''):
    global fails; fails += 0 if ok else 1; print('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, str(detail)[:200]))
def run(fx, beyond=True): return subprocess.run([DCALC] + (['--beyond-release'] if beyond else []) + [fx], capture_output=True, text=True, timeout=600).stdout
def statuses(o): return [l.split('(Status ', 1)[1].split(')', 1)[0] for l in o.splitlines() if '(Status ' in l]
def nodigest(o): return re.sub(r'\(Digest "[0-9a-f]+"\)', '(Digest D)', o)
# merge model: a Measured fork reproduces the fork-free (M6) answers byte for byte, up to the module digest
# (the digest hashes the module text, which necessarily contains the Fork declaration)
n5 = open(os.path.join(HERE, '..', 'm6', 'fixtures', 'neg5_receipts.metta')).read()
fm = os.path.join(OUT, 'fork_measured.metta'); open(fm, 'w').write(n5.replace('(Shared Unmeasured)', '(Shared Measured)'))
nf_txt = '\n'.join(l for l in n5.splitlines() if not re.match(r'\s*\((Fork |Machine ForkMemory|Map keep-left|Carrier XX)', l)).replace(' (Over Copies))', ')') + '\n'
nf = os.path.join(OUT, 'fork_free.metta'); open(nf, 'w').write(nf_txt)
of, on = run(fm), run(nf)
report('merge model: Measured fork == fork-free module, byte for byte up to the module Digest', of and nodigest(of) == nodigest(on), statuses(of))
report('merge model control: Unmeasured fork answers Unknown x3 through the Fork', statuses(run(os.path.join(HERE, '..', 'm6', 'fixtures', 'neg5_receipts.metta'))) == ['Unknown'] * 3)
# negative: the old flag is refused, a fork naming a missing Merge port is refused
bad1 = os.path.join(OUT, 'fork_oldflag.metta'); open(bad1, 'w').write(nf_txt.replace('(OutputDistance Gap))', '(OutputDistance Gap) (ReceiptIdentities Unmeasured))', 1))
o1 = run(bad1); report('merge model neg: ReceiptIdentities flag -> InvalidInput naming the merge model', statuses(o1)[:1] == ['InvalidInput'] and 'merge model' in o1, statuses(o1))
bad2 = os.path.join(OUT, 'fork_noport.metta'); open(bad2, 'w').write(n5.replace('(Merge join) (Shared', '(Merge nosuch) (Shared'))
o2 = run(bad2); report('merge model neg: Fork naming no Merge port of its machine -> InvalidInput', statuses(o2)[:1] == ['InvalidInput'] and 'no Merge port' in o2, statuses(o2))
bad3 = os.path.join(OUT, 'fork_nomerge.metta'); open(bad3, 'w').write(n5.replace('(Machine ForkMemory (States X) (Merge join keep-left))', '(Machine ForkMemory (States X))'))
o3 = run(bad3); report('merge model neg: forked machine without a Merge port -> InvalidInput (nothing reconciles the forks)', statuses(o3)[:1] == ['InvalidInput'] and 'no Merge port' in o3, statuses(o3))
# LeastCoherentRefinement general LP: fixtures replay
lf = os.path.join(HERE, 'fixtures', 'lcr_lp.metta'); lo = os.path.join(OUT, 'lcr_lp.out'); open(lo, 'w').write(run(lf))
rr = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), lf, lo], capture_output=True, text=True)
report('LCR exact LP fixtures replay (Fractions)', rr.returncode == 0 and statuses(open(lo).read()) == ['Checked'] * 3, rr.stdout.strip().splitlines()[-1:] )
# CompleteHive (hive decision 2, our reading of spec l.2896-2906)
cf = os.path.join(HERE, 'fixtures', 'complete_hive.metta'); co = os.path.join(OUT, 'complete_hive.out'); ctext = run(cf); open(co, 'w').write(ctext)
cl = [l for l in ctext.splitlines() if ' => ' in l]
report('CompleteHive statuses: Chain Checked, Split Checked, ParityFull Unsupported, ConsensusCost on unmeasured Unsupported', statuses(ctext) == ['Checked', 'Checked', 'Unsupported', 'Unsupported'], statuses(ctext))
cr = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), cf, co], capture_output=True, text=True)
report('CompleteHive certificates replay (Fractions: Fill paths, NoPath rows, transitivity, alignment cost)', cr.returncode == 0, cr.stdout.strip().splitlines()[-1:])
report('CompleteHive neg: non-Lipschitz measured hive -> Unsupported naming the measured path', len(cl) > 2 and 'not Lipschitz' in cl[2] and '(Path' not in cl[2] and 'M3[' in cl[2], cl[2][:160] if len(cl) > 2 else '')
report('CompleteHive neg: ConsensusCost refuses unmeasured entries and points to CompleteHive (no zero fill)', len(cl) > 3 and 'complete them first with (CompleteHive ChainHive)' in cl[3])
# zero-fill tamper: the Chain answer with its fills removed and cost 0 must be rejected by the replayer
tz = os.path.join(OUT, 'complete_zero.out')
zl = re.sub(r'\(Filled .*?\)\)\) \(NoPaths', '(Filled) (NoPaths', cl[0]).replace('(Value (Rat 1 9))', '(Value (Rat 0 1))') if cl else ''
open(tz, 'w').write(zl + '\n')
zr = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), cf, tz], capture_output=True, text=True)
report('CompleteHive neg: zero-filled completion (no Fill rows, cost 0) is rejected by the replayer', zl != cl[0] and zr.returncode != 0 and 'REJECT' in zr.stdout, zr.stdout.strip().splitlines()[:1])
# LeastCoherentRefinement registry args (Search default LinearProgram; Exhaustive / Budget answer Unsupported, never a fallback)
la = os.path.join(OUT, 'lcr_args.metta')
lt = open(lf).read().split('\n!(dc.run')[0] + '\n' + '\n'.join('!(dc.run LcrLp (LeastCoherentRefinement UnequalTriangle%s))' % a for a in
     ['', ' (Search LinearProgram)', ' (Search Exhaustive)', ' (Budget (Pivots 10))', ' (Search Greedy)']) + '\n'
open(la, 'w').write(lt); lao = run(la); ls_ = statuses(lao); ll = [l for l in lao.splitlines() if ' => ' in l]
report('LCR args: default and (Search LinearProgram) Checked and identical up to the claim', ls_[:2] == ['Checked', 'Checked'] and len(ll) > 1 and ll[0].split('(Value', 1)[1] == ll[1].split('(Value', 1)[1], ls_)
report('LCR args neg: (Search Exhaustive) and (Budget ..) -> Unsupported with a reason (no silent fallback)', ls_[2:4] == ['Unsupported', 'Unsupported'] and 'not implemented' in ll[2] and 'not implemented' in ll[3], ls_)
report('LCR args neg: unregistered Search value -> InvalidInput', ls_[4:5] == ['InvalidInput'], ls_)
print('m6rest_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails)); sys.exit(1 if fails else 0)
