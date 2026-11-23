#!/usr/bin/env python3
"""Gates for t-2026-11-14-mettadinc-review-fixes: D1 (duplicate Cases rows), partial Cases,
D2 (unpinned proof backend fails closed) and the refreshed ConeOfInfluence reason.
Needs DCALC_CADICAL (real solver); the pinned check also needs DCALC_CAKE_LPR and both *_SHA256 pins."""
import os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DC = os.path.join(ROOT, 'build', 'dcalc', 'dcalc')
HERE = os.path.dirname(os.path.abspath(__file__))
FXD = os.path.join(HERE, 'fixtures'); CHK = os.path.join(HERE, 'checks')
FORTY = os.path.join(ROOT, 'docs', 'e0', 'docs', '01_language_specification', 'validation_package', 'fixtures', 'forty_bits.metta')
fails = 0
def report(name, ok, det=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '  :: ' + str(det)[:300]))
    if not ok: fails += 1
def rows(path, args=(), env=None):
    o = subprocess.run([DC] + list(args) + [path], capture_output=True, text=True, timeout=120, env=env)
    out = {}
    for l in o.stdout.splitlines():
        if ' => ' not in l: continue
        k, v = l.split(' => ', 1)
        st = re.search(r'\(Status ([A-Za-z]+)\)', v); rs = re.search(r'\(Reason "([^"]*)"', v)
        out[k.strip()] = (st.group(1) if st else None, rs.group(1) if rs else '')
    return out
# D1: two rows for the same case are refused, naming the duplicate (both reviewer variants)
for f in ('mut_m7_caseoverlap_eq', 'mut_m7_caseoverlap_ne'):
    r = rows(os.path.join(FXD, f + '.metta'), ['--beyond-release'])
    ok = bool(r) and all(s == 'InvalidInput' and 'duplicate case Absent' in why for s, why in r.values())
    report('D1: %s -> InvalidInput "duplicate case Absent" on every request' % f, ok, r)
# D1 via Import (review 1 F1): a duplicate-row map declared in an imported module is refused for the importer too
for mode in (['--beyond-release'], []):
    r = rows(os.path.join(FXD, 'mut_m7_caseoverlap_import.metta'), mode)
    ok = bool(r) and 'Availability (CheckNow Bias)' in r and all(s == 'InvalidInput' and 'duplicate case Absent' in why for s, why in r.values())
    report('D1 import (single file%s): importer and Lib -> InvalidInput "duplicate case Absent"' % (' ' + mode[0] if mode else ', release'), ok, r)
r = rows(os.path.join(FXD, 'import_cross', 'lib.metta'), ['--beyond-release', os.path.join(FXD, 'import_cross', 'main.metta')])
b = r.get('Availability (CheckNow Bias)')
report('D1 import (cross-file main.metta lib.metta, --beyond-release): importer -> InvalidInput "(imported): duplicate case Absent"',
       b is not None and b[0] == 'InvalidInput' and '(imported): duplicate case Absent' in b[1], r)
# release LIBS (t-2026-11-20-mettadinc-release-libs): release mode loads library files after FILE, and the gate still applies
RL = os.path.join(FXD, 'release_libs')
def full(args):
    o = subprocess.run([DC] + list(args), capture_output=True, text=True, timeout=120)
    return [l for l in o.stdout.splitlines() if ' => ' in l]
for mode in ([], ['--beyond-release']):
    tag = mode[0] if mode else 'release'
    cross = full(mode + [os.path.join(RL, 'main_ok.metta'), os.path.join(RL, 'lib_ok.metta')])
    single = full(mode + [os.path.join(RL, 'single_ok.metta')])
    report('release LIBS (%s): main_ok.metta lib_ok.metta resolves the import and equals the single-file answer' % tag,
           bool(cross) and cross == single and not any('Import of unknown module' in l for l in cross), cross)
    r = rows(os.path.join(RL, 'lib_gated.metta'), mode + [os.path.join(RL, 'main_gated.metta')])   # dcalc [mode] main_gated lib_gated
    report('release LIBS (%s): import of a NatArith module stays Unsupported "library NatArith is outside the first release"' % tag,
           bool(r) and all(st == 'Unsupported' and 'library NatArith is outside the first release' in why for st, why in r.values()), r)
r = rows(os.path.join(RL, 'main_ok.metta'))
report('release LIBS: main_ok.metta alone still answers "Import of unknown module LibCar"',
       bool(r) and all(st == 'Unsupported' and 'Import of unknown module LibCar' in why for st, why in r.values()), r)
# partial Cases: Encode map without Both -> InvalidInput naming map and state
r = rows(os.path.join(FXD, 'mut_m7_partial.metta'), ['--beyond-release'])
b = r.get('Availability (CheckNow Bias)')
report('partial: Bias -> InvalidInput naming map bias and state Both',
       b is not None and b[0] == 'InvalidInput' and 'Encode map bias has no case for state Both' in b[1], r)
# D2: fake checkers with the pins unset never give Checked
cad = os.environ.get('DCALC_CADICAL')
base = {k: v for k, v in os.environ.items() if k not in ('DCALC_CADICAL_SHA256', 'DCALC_CAKE_LPR_SHA256')}
for fk in ('fake_cake_lie', 'fake_cake_exit1', 'fake_cake_silent'):
    if not cad: report('D2: %s unpinned (needs DCALC_CADICAL)' % fk, False, 'DCALC_CADICAL unset'); continue
    r = rows(FORTY, [], dict(base, DCALC_CAKE_LPR=os.path.join(CHK, fk + '.sh')))
    st = sorted(set(s for s, _ in r.values()))
    report('D2: %s with pins unset -> never Checked' % fk, bool(r) and 'Checked' not in st, st)
# D2: the real backend unpinned is refused too (not only fake checkers)
if cad and os.environ.get('DCALC_CAKE_LPR'):
    r = rows(FORTY, [], base)
    st = sorted(set(s for s, _ in r.values()))
    why = ' '.join(w for _, w in r.values())
    report('D2: real backend with pins unset -> never Checked, reason names the pins',
           bool(r) and 'Checked' not in st and 'proof backend not pinned' in why, st)
# D2: the pinned real backend still gives Checked (suite configuration)
if all(os.environ.get(k) for k in ('DCALC_CADICAL', 'DCALC_CAKE_LPR', 'DCALC_CADICAL_SHA256', 'DCALC_CAKE_LPR_SHA256')):
    r = rows(FORTY)
    report('D2: pinned real backend -> Checked rows as before', any(s == 'Checked' for s, _ in r.values()), r)
else:
    report('D2: pinned real backend (needs DCALC_* and both *_SHA256)', False, 'pins missing')
# item 4: ConeOfInfluence reason no longer says "M3 in progress"
r = rows(FORTY, ['--beyond-release'])
c = r.get('FortyBitsScreens Cone')
report('item 4: ConeOfInfluence Unsupported, reason "not implemented by the symbolic engine"',
       c is not None and c[0] == 'Unsupported' and 'not implemented by the symbolic engine' in c[1] and 'M3 in progress' not in c[1], c)
# t-2026-11-20-mettadinc-admit-profile-uninit: parse_profile read an uninitialized buffer when naming an
# unknown profile shorthand, so the reason sometimes held garbage. Repeated release runs must all give exactly
# "unknown profile shorthand Quantum" with byte-identical output; the sanitized build (limits_sanitized step) must be clean.
BADP = os.path.join(ROOT, 'docs', 'review', 'inputs', 'mut_m1_badprofile.metta')
WANT = re.compile(r'^.*mut_m1_badprofile\.metta:3:3: LiteralCongruence: unknown profile shorthand Quantum$')
def raw(exe, path, env=None):
    o = subprocess.run([exe, path], capture_output=True, timeout=120, env=env)
    return o.returncode, o.stdout.decode('latin-1'), o.stderr.decode('latin-1')
def why_all(out):
    return [m.group(1) for m in re.finditer(r'\(Reason "([^"]*)"', out)]
N = int(os.environ.get('DCALC_BADPROFILE_RUNS', '20'))
outs = [raw(DC, BADP) for _ in range(N)]
bad = [i for i, (rc, out, _) in enumerate(outs) if rc != 0 or not why_all(out) or not all(WANT.match(w) for w in why_all(out))]
report('profile shorthand: %d release runs of mut_m1_badprofile -> every reason exactly "unknown profile shorthand Quantum"' % N,
       not bad, [why_all(outs[i][1])[:1] for i in bad[:3]])
report('profile shorthand: %d release runs byte-identical' % N, len(set(o for _, o, _ in outs)) == 1, len(set(o for _, o, _ in outs)))
SAN = os.path.join(ROOT, 'build', 'dcalc-sanitized', 'dcalc')
if os.path.exists(SAN):
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    res = [raw(SAN, BADP, env) for _ in range(3)]
    clean = all(rc == 0 and 'Sanitizer' not in err and 'runtime error' not in err and why_all(out) and all(WANT.match(w) for w in why_all(out)) for rc, out, err in res)
    report('profile shorthand: ASan+UBSan build, 3 runs -> exit 0, no sanitizer report, reason Quantum', clean,
           [(rc, err[-200:]) for rc, _, err in res])
else:
    report('profile shorthand: sanitized build (build/dcalc-sanitized/dcalc, built by the limits_sanitized step)', False, 'missing')
print('review_fixes: %s (%d failing)' % ('PASS' if not fails else 'FAIL', fails))
sys.exit(1 if fails else 0)
