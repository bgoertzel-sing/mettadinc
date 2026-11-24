#!/usr/bin/env python3
"""Gates for t-2026-11-23-mettadinc-m0-typeform-maps: Crisp M0 maps declared with a type form in From/To
(spec 5.1 grammar, Map From/To are registry "expr" fields; 5.2 typed carriers; 5.3 admission by enumeration).
Every gate runs in release mode and with --beyond-release.
  1. probe P2 (examples_e2e/repro/m0_blocker_b_typeform_map.metta): B1 Checked, with the same answer as its
     carrier-name control B1C (only module, digest and the code carrier's name in Target differ);
  2. fixtures/typeform_gates.metta: every request's status and witness equal Ben's reference evaluator
     (reference_answers.py: docs/e0 mg_eval.World + models/dclib), and every type-form module TFn answers
     exactly as its carrier-name twin TFnC (Refuted and Checked cases, so a lowering with another meaning fails);
  3. fixtures/typeform_negative.metta: malformed uses answer InvalidInput, each with its reason;
  4. fixtures/typeform_unsupported.metta: forms still outside M0 answer Unsupported, the reason naming the form.
DCALC overrides the binary (used to show the gate fails on the base binary and on a mutant)."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DC = os.environ.get('DCALC') or os.path.join(ROOT, 'build', 'dcalc', 'dcalc')
FXD = os.path.join(HERE, 'fixtures')
PROBE = os.path.join(ROOT, 'tests', 'dcalc', 'examples_e2e', 'repro', 'm0_blocker_b_typeform_map.metta')
fails = 0
def report(name, ok, det=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '  :: ' + str(det)[:400]))
    if not ok: fails += 1
def rows(path, args=()):
    o = subprocess.run([DC] + list(args) + [path], capture_output=True, text=True, timeout=120)
    out = {}
    for l in o.stdout.splitlines():
        if ' => ' not in l: continue
        k, v = l.split(' => ', 1)
        st = re.search(r'\(Status ([A-Za-z]+)\)', v); rs = re.search(r'\(Reason "([^"]*)"', v)
        out[k.strip()] = (st.group(1) if st else None, rs.group(1) if rs else '', v)
    return out
def strip_ids(v):
    """The answer without the module name, digest and the code carrier's name (the only intended differences)."""
    v = re.sub(r'\(Module [^()\s]+\)', '(Module _)', v)
    v = re.sub(r'\(Digest "[0-9a-f]*"\)', '(Digest _)', v)
    return re.sub(r'\(Target (\([^()]*\)|[^()\s]+)\)', '(Target _)', v)
ref = {}
rp = subprocess.run([sys.executable, os.path.join(HERE, 'reference_answers.py')], capture_output=True, text=True, timeout=120)
for l in rp.stdout.splitlines():
    k, st, w = l.split('\t'); ref[k] = (st, w)
report('reference evaluator ran (docs/e0 mg_eval + dclib) and answered all 18 requests', rp.returncode == 0 and len(ref) == 18, rp.stderr[-300:])
NEG = {
    'NA (CheckNow R)': 'Map fst: From type (Tuple Symbol Symbol) is not the element type of carrier A',
    'NB (CheckNow R)': 'Map short: row 0 gives (Tuple p) on (Tuple p r), which is not of the To type (Tuple Symbol Symbol)',
    'NC (CheckNow R)': 'Map swap: sends (Tuple p r) to (Tuple r p), which leaves carrier AB',
    'ND (CheckNow R)': 'Map bad: field From: (Tuple) is not a well-formed type',
    'NE (CheckNow R)': 'Map id: Cases row 0: (Tuple $a $b $c) cannot be a value of the From type (Tuple Symbol Symbol)',
    'NF (CheckNow R)': 'Map part: not total on carrier AA; no value for (Tuple q p)',
    'NG (CheckNow R)': 'Map first: To type (Tuple Symbol) is not the element type of carrier AA',
    'NH (CheckNow R)': 'Map pick: input (Tuple p p) matches Cases rows 0 and 1',
}
UNS = {
    'UA (CheckNow R)': 'Map law: field To: type (Law Bit) is outside the M0 fragment',
    'UB (CheckNow R)': 'Map pick: Cases row 0 of a type-form map uses an operator outside the M0 fragment',
    'UD (CheckNow R)': 'Map id: field From: type (Tuple A A) is outside the M0 fragment',
    'UE (CheckAbstractionMap H)': 'Map pick: Cases row 0 of a type-form map uses an operator outside the M0 fragment',
}
# UC (a type-form Body map) was Unsupported here; t-2026-11-24-mettadinc-m0-body-maps lowers Body maps, so the identity
# on AA = {p,q}^2 is injective and CheckNow R is Checked with four singleton blocks (gated in tests/dcalc/m0_body_maps).
UC_BLOCKS = '(Blocks (Block (Tuple p p)) (Block (Tuple p q)) (Block (Tuple q p)) (Block (Tuple q q)))'
for mode in ([], ['--beyond-release']):
    tag = ' [%s]' % (mode[0] if mode else 'release')
    g = rows(os.path.join(FXD, 'typeform_unsupported.metta'), mode).get('UC (CheckNow R)')
    report('UC (Body type-form identity map) -> Checked, four singleton blocks (Body maps lowered by t-2026-11-24-mettadinc-m0-body-maps)' + tag,
           g is not None and g[0] == 'Checked' and UC_BLOCKS in g[2], g)
    r = rows(PROBE, mode)
    b, c = r.get('B1 (CheckNow R)'), r.get('B1C (CheckNow R)')
    report('probe P2: B1 (From/To (Tuple Symbol Symbol)) -> Checked' + tag, b is not None and b[0] == 'Checked', b)
    report('probe P2: B1 answers as its carrier-name control B1C' + tag, b is not None and c is not None and strip_ids(b[2]) == strip_ids(c[2]), (b, c))
    r = rows(os.path.join(FXD, 'typeform_gates.metta'), mode)
    for k, (st, w) in sorted(ref.items()):
        g = r.get(k)
        ok = g is not None and g[0] == st
        if ok and w != '-':
            ok = all(part in g[2] for part in re.findall(r'\((?:Pair|State|Action|Observe) (?:[^()]|\([^()]*\))*\)', w))
        report('%s -> %s %s (reference evaluator)%s' % (k, st, '' if w == '-' else w, tag), ok, g)
    for k in sorted(ref):
        mod = k.split(' ', 1)[0]
        if mod.endswith('C'): continue
        twin = mod + 'C' + k[len(mod):]
        g, h = r.get(k), r.get(twin)
        report('%s answers exactly as its carrier-name twin %s%s' % (k, twin, tag), g is not None and h is not None and strip_ids(g[2]) == strip_ids(h[2]), (g, h))
    r = rows(os.path.join(FXD, 'typeform_negative.metta'), mode)
    for k, why in NEG.items():
        g = r.get(k); report('%s -> InvalidInput: %s%s' % (k, why, tag), g is not None and g[0] == 'InvalidInput' and why in g[1], g)
    r = rows(os.path.join(FXD, 'typeform_unsupported.metta'), mode)
    for k, why in UNS.items():
        g = r.get(k); report('%s -> Unsupported naming the form: %s%s' % (k, why, tag), g is not None and g[0] == 'Unsupported' and why in g[1], g)
print('m0_typeform_maps: %s (%d failing)' % ('PASS' if not fails else 'FAIL', fails))
sys.exit(1 if fails else 0)
