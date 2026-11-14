#!/usr/bin/env python3
"""M7 negative gates 1-7 (t-2026-11-14-mettadinc-m7; MILESTONES.md M7 'Negative tests').  Gate 6 (clock-rate
exactness) uses fixtures gate6a-f.  Each gate must be refused AS STATED
(Refuted / InvalidInput / replay REJECT), never merely passed off as Unsupported.  Runs dcalc --beyond-release."""
import hashlib, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tests', 'dcalc')); import replay as R
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build', 'dcalc', 'dcalc'))
FX = os.path.join(ROOT, 'docs', 'e0', 'docs', '01_language_specification', 'validation_package', 'fixtures')
MU = os.path.join(HERE, 'm7'); OUT = os.environ.get('M7_GATES_OUT', os.path.join(ROOT, 'build', 'm7_gates')); os.makedirs(OUT, exist_ok=True)
def run(f): return subprocess.run([DCALC, '--beyond-release', f], capture_output=True, text=True, timeout=300).stdout
def rows(text):
    out = {}
    for line in text.splitlines():
        if ' => ' not in line: continue
        res = R.parse(line.split(' => ', 1)[1])[0]
        st = R.find(res, 'Status'); rs = R.find(res, 'Reason')
        out[line.split(' => ')[0]] = (st[1] if st else None, R.show(rs) if rs else '', res)
    return out
bad = 0
def report(name, ok, detail=''):
    global bad
    bad += not ok; print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, (' -- ' + detail) if detail and not ok else ''))
def refused(f, key, word):
    r = rows(run(os.path.join(MU, f))); hits = [v for k, v in r.items() if key in k]
    return bool(hits) and all(v[0] == 'InvalidInput' and word in v[1] for v in hits), str([(v[0], v[1][:120]) for v in hits])

# gate 1: unavailable (Absent/Missing) must not be silently converted to neither: W01/W02 Refuted with (Absent, Neither)
av = os.path.join(FX, 'availability.metta'); at = run(av); open(os.path.join(OUT, 'availability.out'), 'w').write(at); r = rows(at)
for req in ('(CheckNow DefaultZero)', '(CheckNow Bias)'):
    v = [x for k, x in r.items() if k.endswith(req)]
    report('gate 1: %s Refuted with merged pair (Absent Neither)' % req, len(v) == 1 and v[0][0] == 'Refuted' and '(Pair Absent Neither)' in R.show(R.find(v[0][2], 'Value')), str(v[:1])[:200])
# gate 2: a self-authored Checked claim is refused at admission (no bypass of checking)
ok, d = refused('gate2_self_authored.metta', 'Availability', 'unknown declaration head Claim'); report('gate 2: self-authored (Claim .. (Status Checked)) refused', ok, d)
# gate 3: a certificate reused after its context changed: the stale output's Binding Digest no longer matches the module
g3 = os.path.join(MU, 'gate3_context_changed.metta')
mods = {m[1]: m for m in R.parse(open(g3).read()) if isinstance(m, list) and m and m[0] == 'DC.Module'}
dg = hashlib.sha256(R.show(mods['Availability']).encode()).hexdigest()
stale = [x[2] for x in r.values()]
mism = [R.find(R.find(res, 'Binding'), 'Digest') for res in stale]
report('gate 3: every stale certificate is refused by digest (%s.. now)' % dg[:12], bool(stale) and all(m is not None and R.show(m).strip('()').split('"')[1] != dg for m in mism))
fresh = rows(run(g3)); fd = [R.show(R.find(R.find(v[2], 'Binding'), 'Digest')) for v in fresh.values()]
report('gate 3: the changed module re-binds to its own digest', bool(fd) and all(dg in x for x in fd), str(fd)[:200])
rp = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'dcalc', 'm7', 'replay_m7.py'), g3, os.path.join(OUT, 'availability.out')], capture_output=True, text=True, timeout=120)   # review-1 F3
rj = [l for l in rp.stdout.splitlines() if l.startswith('REJECT') and 'stale certificate' in l]
report('gate 3: replay itself REJECTs every stale row (Binding Digest check in replay_m7.py)', rp.returncode != 0 and len(rj) == len(stale) > 0, rp.stdout[-300:])
rp = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'dcalc', 'm7', 'replay_m7.py'), g3, os.path.join(OUT, 'availability.out')], capture_output=True, text=True, timeout=120)   # review-1 F3
rj = [l for l in rp.stdout.splitlines() if l.startswith('REJECT') and 'stale certificate' in l]
report('gate 3: replay_m7 itself rejects every stale row (digest), not only this script', rp.returncode != 0 and len(rj) == len(stale) and len(rj) > 0, rp.stdout[-300:])
# gate 4: observer on an unbound global operator / free global symbol
ok, d = refused('gate4_unbound_operator.metta', 'Separation', 'unknown head Frobenius'); report('gate 4: undeclared operator Frobenius refused', ok, d)
ok, d = refused('gate4b_free_symbol.metta', 'Separation', 'undeclared name G'); report('gate 4: free global symbol G refused', ok, d)
# gate 5: invariance asserted without a derivation
ok, d = refused('gate5_no_derivation.metta', 'Separation', 'missing required argument Require'); report('gate 5: SeekSeparator without Require refused', ok, d)
ok, d = refused('gate5b_dangling_derivation.metta', 'Separation', 'not a derivation'); report('gate 5: Require of a removed Invariance Derive refused', ok, d)
ok, d = refused('gate5c_wrong_derivation.metta', 'Separation', 'has no field Derivation'); report('gate 5: Require of a non-invariance Derive refused', ok, d)
# gate 6: clock-rate exactness without a full-support product law over declared coordinates is refused as stated
for f, word, what in (('gate6a_library.metta', 'expected one of Coordinates', 'Library other than Coordinates'),
                      ('gate6b_dirac.metta', 'lacks full support', 'measure without full support (Dirac)'),
                      ('gate6c_nomeasure.metta', 'undeclared name Missing', 'undeclared measure'),
                      ('gate6d_product_nofull.metta', 'lacks full support', 'admissible Product law with a zero-mass factor (refused by ClockRates, not admission)'),
                      ('gate6e_zero_masses.metta', 'lacks full support', 'Masses listing every point but four with mass 0 (review-1 F4 probe)'),
                      ('gate6f_product_partial.metta', 'lacks full support', 'admissible Product law whose Bit factor omits a point (Enum coverage)')):
    ok, d = refused(os.path.join(ROOT, 'tests', 'dcalc', 'm7', 'fixtures', f), 'G', word); report('gate 6: ClockRates with %s refused' % what, ok, d)
# canary (sanity gate): the unmutated fixtures are decided, not refused, through the same path
ar = rows(run(os.path.join(FX, 'arithmetic_probes.metta'))); sep = [v for k, v in ar.items() if k.endswith('Separation')]
report('canary: unmutated arithmetic_probes Separation is Checked', len(sep) == 1 and sep[0][0] == 'Checked', str([(v[0], v[1][:100]) for v in sep]))
report('canary: unmutated availability rows are Refuted, not InvalidInput', len(r) == 2 and all(v[0] == 'Refuted' for v in r.values()), str([v[0] for v in r.values()]))
# gate 7: an Estimated result is never turned into an exact channel, and an order-2 U-statistic is never treated as
# n independent counts: Status stays Estimated, IndependentPairs = floor(n/2), and the interval is at least as wide as
# Hoeffding with floor(n/2) pairs (with n counts it would be narrower).  A tampered copy must be refused.
import math, re
from fractions import Fraction as Fr
def rfind(x, h):
    if isinstance(x, list):
        if x and x[0] == h: return x
        for y in x:
            z = rfind(y, h)
            if z is not None: return z
    return None
def num(x):
    if isinstance(x, list) and x and x[0] == 'Rat': return Fr(int(x[1]), int(x[2]))
    return Fr(x if isinstance(x, str) else x[1])
def ustat_ok(text):
    us = 0; errs = []
    for k, (st, rs, res) in rows(text).items():
        u = rfind(res, 'UStatistic')
        if u is None: continue
        us += 1; n = int(rfind(res, 'SampleSize')[1]); ip = int(rfind(u, 'IndependentPairs')[1])
        lo, hi = num(rfind(res, 'Lower')[1]), num(rfind(res, 'Upper')[1]); dl = num(rfind(u, 'Level')[1])
        need_w = 2 * math.sqrt(math.log(2 / float(dl)) / (2 * (n // 2)))
        if st != 'Estimated': errs.append('%s: status %s' % (k[:60], st))
        if ip != n // 2: errs.append('%s: IndependentPairs %d != floor(%d/2)' % (k[:60], ip, n))
        re_ = rfind(res, 'RateEstimate'); cn, ob = (rfind(re_, 'Count'), rfind(re_, 'Observations')) if re_ else (None, None); pr = float(Fr(int(cn[1]), int(ob[1]))) if cn and ob and int(ob[1]) else None
        hw = need_w / 2   # the interval may be clipped to [0, 1]; compare each side with the floor(n/2)-pair Hoeffding half-width
        if pr is None: errs.append('%s: no RateEstimate Count/Observations' % k[:60])
        elif float(lo) > max(0.0, pr - hw) + 1e-6 or float(hi) < min(1.0, pr + hw) - 1e-6:
            errs.append('%s: [%.4f, %.4f] narrower than p %.4f +- Hoeffding(floor(n/2)) %.4f' % (k[:60], float(lo), float(hi), pr, hw))
    return us > 0 and not errs, us, errs
est = os.path.join(ROOT, 'tests', 'dcalc', 'm4', 'fixtures', 'est_review1.metta'); et = run(est); open(os.path.join(OUT, 'est_review1.out'), 'w').write(et)
ok, us, errs = ustat_ok(et); report('gate 7: %d U-statistic rows stay Estimated with floor(n/2) pairs and Hoeffding(floor(n/2)) width' % us, ok, str(errs)[:200])
tam = re.sub(r'\(IndependentPairs (\d+)\)', lambda m_: '(IndependentPairs %d)' % (2 * int(m_.group(1))), et, count=1)
ok, _, errs = ustat_ok(tam); report('gate 7: tampered copy (pairs counted as n independent) is refused', not ok, 'tamper accepted')
ls_ = et.splitlines(); iu = next(i for i, l in enumerate(ls_) if 'UStatistic' in l and '(Status Estimated)' in l)
ls_[iu] = ls_[iu].replace('(Status Estimated)', '(Status Checked)', 1); tam2 = '\n'.join(ls_) + '\n'
ok, _, errs = ustat_ok(tam2); report('gate 7: tampered copy (U-statistic Estimated relabelled as exact Checked) is refused', not ok, 'tamper accepted')
print('run_m7_gates: %s' % ('PASS' if not bad else 'FAIL (%d)' % bad)); sys.exit(1 if bad else 0)
