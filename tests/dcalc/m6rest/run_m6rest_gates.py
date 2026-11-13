#!/usr/bin/env python3
"""M6-rest gates (beyond release, plus release mode over every m6rest fixture).  Each check prints PASS/FAIL; exit 1 on any FAIL."""
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
# Completed hive as (Output C Hive) (review 1 F1): NoPath pairs stay Unmeasured, a claim reading them answers Unknown
xf = os.path.join(HERE, 'fixtures', 'complete_hive_output.metta'); xo = os.path.join(OUT, 'complete_hive_output.out'); xtext = run(xf); open(xo, 'w').write(xtext)
xl = [l for l in xtext.splitlines() if ' => ' in l]
report('CompleteHive output: (CheckKernelCoherence (Output ChainDone Hive)) Checked; (Output SplitDone Hive) and SplitHive Unknown', statuses(xtext) == ['Checked', 'Unknown', 'Unknown'], statuses(xtext))
report('CompleteHive output: NoPath entries are not zero-filled (SplitDone answer is Unknown via an Unmeasured correspondence, naming M3)', len(xl) > 1 and 'Unmeasured' in xl[1] and 'M3' in xl[1] and '(Status Checked)' not in xl[1], xl[1][:200] if len(xl) > 1 else '')
# LeastCoherentRefinement registry args (Search default LinearProgram; Exhaustive / Budget answer Unsupported, never a fallback)
la = os.path.join(OUT, 'lcr_args.metta')
lt = open(lf).read().split('\n!(dc.run')[0] + '\n' + '\n'.join('!(dc.run LcrLp (LeastCoherentRefinement UnequalTriangle%s))' % a for a in
     ['', ' (Search LinearProgram)', ' (Search Exhaustive)', ' (Budget (Pivots 10))', ' (Search Greedy)']) + '\n'
open(la, 'w').write(lt); lao = run(la); ls_ = statuses(lao); ll = [l for l in lao.splitlines() if ' => ' in l]
report('LCR args: default and (Search LinearProgram) Checked and identical up to the claim', ls_[:2] == ['Checked', 'Checked'] and len(ll) > 1 and ll[0].split('(Value', 1)[1] == ll[1].split('(Value', 1)[1], ls_)
report('LCR args neg: (Search Exhaustive) and (Budget ..) -> Unsupported with a reason (no silent fallback)', ls_[2:4] == ['Unsupported', 'Unsupported'] and 'not implemented' in ll[2] and 'not implemented' in ll[3], ls_)
report('LCR args neg: unregistered Search value -> InvalidInput', ls_[4:5] == ['InvalidInput'], ls_)
# Associator (request shape ours; definition spec Def 10.1 l.2827)
af = os.path.join(HERE, 'fixtures', 'associator.metta'); ao = os.path.join(OUT, 'associator.out'); atext = run(af); open(ao, 'w').write(atext)
al = [l for l in atext.splitlines() if ' => ' in l]
report('Associator statuses: Parity Checked, Coherent Checked, Partial Unsupported, repeated/unknown member InvalidInput', statuses(atext) == ['Checked', 'Checked', 'Unsupported', 'InvalidInput', 'InvalidInput'], statuses(atext))
report('Associator: parity triangle nonzero, coherent hive zero', len(al) > 1 and '(Zero False)' in al[0] and '(Zero True)' in al[1])
ar = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), af, ao], capture_output=True, text=True)
report('Associator entries replay (recomputed c_ik - c_ij o c_jk)', ar.returncode == 0, ar.stdout.strip().splitlines()[-1:])
at = os.path.join(OUT, 'associator_tampered.out'); open(at, 'w').write(al[0].replace('(Zero False)', '(Zero True)', 1) + '\n' if al else '')
atr = subprocess.run([sys.executable, os.path.join(HERE, 'replay_m6rest.py'), af, at], capture_output=True, text=True)
report('Associator neg: flipped Zero flag is rejected by the replayer', atr.returncode != 0 and 'REJECT' in atr.stdout, atr.stdout.strip().splitlines()[:1])
report('Associator neg: unmeasured entry points to CompleteHive (no zero fill)', len(al) > 2 and 'complete it first with (CompleteHive Partial)' in al[2])
# arrow kinds: the arrow_kinds registry section is documentation only (no code reads it). This gate checks the pre-existing binding type check: mixing kinds in one Then is refused (InvalidInput).
mx = os.path.join(OUT, 'then_mixed.metta')
mt = n5.replace(' (Over Copies))', ')').replace('(Derive Composite (ThenContracts (Output FirstChecked Value) (Output SecondChecked Value))))',
     '(Derive Composite (ThenContracts (Output FirstChecked Value) (Output SecondChecked Value)))\n  (Derive Mixed (Then (Output FirstChecked Value) (Output SecondChecked Value))))') + '!(dc.run Neg5Receipts Mixed)\n'
open(mx, 'w').write(mt); mo = run(mx)
report('arrow kinds neg: Then over two affine contracts (AffineContract kind) -> InvalidInput naming the type mismatch, never coerced', 'Derive Mixed' in mt and statuses(mo)[-1:] == ['InvalidInput'] and 'CheckedImplementationContract, expected Arrow' in mo, statuses(mo))
# review 2 F1: the spec's own merge fixture (receipt_packets.metta: MergeMemory declared in HyperseedMemory, P12/P13 in
# PacketMerges) carries a Fork.  The Fork's (Of MergeMemory) resolves through (Import HyperseedMemory (Only ... MergeMemory)).
SPEC_PK = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package/fixtures/receipt_packets.metta')
def pm(o): return [l for l in o.splitlines() if l.startswith('PacketMerges ')]
def hm(o): return [l for l in o.splitlines() if l.startswith('HyperseedMemory ')]
pk_spec, pk_meas, pk_unm = run(SPEC_PK), run(os.path.join(HERE, 'fixtures', 'packets_fork_measured.metta')), run(os.path.join(HERE, 'fixtures', 'packets_fork_unmeasured.metta'))
report('spec P12/P13 with a Measured fork (merge machine imported): byte for byte the spec answers up to the PacketMerges Digest', pk_meas and nodigest(pk_meas) == nodigest(pk_spec) and statuses('\n'.join(pm(pk_meas))) == ['Checked', 'Refuted'], statuses('\n'.join(pm(pk_meas))))
report('spec P1-P11 (HyperseedMemory) unchanged byte for byte including its Digest when PacketMerges carries a Measured or Unmeasured fork', len(hm(pk_spec)) == 11 and hm(pk_meas) == hm(pk_spec) == hm(pk_unm))
report('spec P12/P13 with an Unmeasured fork -> Unknown x2', statuses('\n'.join(pm(pk_unm))) == ['Unknown', 'Unknown'], statuses('\n'.join(pm(pk_unm))))
pk_bad = os.path.join(OUT, 'packets_fork_not_imported.metta')
open(pk_bad, 'w').write(open(os.path.join(HERE, 'fixtures', 'packets_fork_measured.metta')).read().replace(' PosteriorDistance MergeMemory))', ' PosteriorDistance))'))
ob = run(pk_bad); report('spec P12/P13 neg: Fork naming a machine not in the Import Only list -> InvalidInput', statuses('\n'.join(pm(ob)))[:1] == ['InvalidInput'], statuses('\n'.join(pm(ob))))
# review 2 F2: release mode.  Every m6rest fixture answers only Unsupported/InvalidInput there (Fork, CompleteHive,
# LCR LP, Associator are beyond release); the packets fork fixtures keep the spec's release answers outside PacketMerges.
for fx in sorted(os.listdir(os.path.join(HERE, 'fixtures'))):
    rel = run(os.path.join(HERE, 'fixtures', fx), beyond=False)
    st = statuses('\n'.join(pm(rel))) if fx.startswith('packets_fork') else statuses(rel)
    report('release mode: %s answers only Unsupported/InvalidInput' % fx, len(st) > 0 and set(st) <= {'Unsupported', 'InvalidInput'}, st)
rs, rm = run(SPEC_PK, beyond=False), run(os.path.join(HERE, 'fixtures', 'packets_fork_measured.metta'), beyond=False)
report('release mode: packets fork fixture leaves HyperseedMemory answers identical to the spec fixture', len(hm(rs)) == 11 and hm(rm) == hm(rs))
print('m6rest_gates: %s' % ('PASS' if not fails else 'FAIL (%d)' % fails)); sys.exit(1 if fails else 0)
