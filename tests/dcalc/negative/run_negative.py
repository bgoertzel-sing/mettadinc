#!/usr/bin/env python3
"""M0 negative acceptance suite (AC4): the ten entries of docs/e0/MILESTONES.md.

Each entry names a fixture, the requests it concerns (a substring of
"<Module> <request>"), and the statuses M0 may return.  Entries whose request
needs a later milestone must be Unsupported (entries 9 and 10 may also be
Unknown); binding failures (entries 1-3) must be InvalidInput naming the field.
Entry 3 tampers a copy of the bundle (every stale label set to 0, declared
digest kept) in a temporary directory; the original must not be refused.
Exit 0 iff every entry passes.  See README.md for the table."""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DOCS = os.path.join(ROOT, 'docs/e0/docs')
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
LM = '05_live_memory_part2/validation_bundle/live_memory.metta'
WX = '06_wmtm_worked_example/validation_bundle/wmtm_example.metta'
AP = '03_four_worked_examples/validation_bundles/ex2_access_policy/access_policy.metta'
MG = '04_omega_memory_goals_part1/validation_bundle/memory_goals.metta'
HY = '01_language_specification/validation_package/fixtures/hypotheses.metta'
CL = '01_language_specification/validation_package/fixtures/certificate_limits.metta'

# (n, title, fixture, request substrings, allowed statuses, reason must contain)
ENTRIES = [
 (1, 'Keyed index with a statistic of the wrong machine', LM, ['(CheckStatistic EngineAsItems'], {'InvalidInput'}, 'field Item'),
 (2, 'CheckSafety via a simulation of another machine', LM, ['(CheckSafety NormFirst (Never (Shows unlawful True)) (Via StutterWeighted)'], {'InvalidInput'}, 'field Via'),
 (3, 'receipt stream that does not match its declared digest', 'TAMPERED:' + WX, ['(On RepliesGate)'], {'InvalidInput'}, 'field Digest'),
 (4, 'access policy approver rule reads the auditor session', AP, ['AccessPolicy '], {'Unsupported'}, None),
 (5, 'anti-nag passes CheckNow but fails interpretation', MG, ['AntiAsNag', 'NagForAntiNag'], {'Unsupported'}, None),
 (6, 'E2 does not transport to a policy withholding first proposals', WX, ['WMTM'], {'Unsupported'}, None),
 (7, 'Consumer accepting only some Conditional backends', MG, ['Consumer'], {'Unsupported'}, None),
 (8, 'literal congruence under an indiscrete code tolerance', HY, ['LiteralCongruence '], {'Checked', 'Refuted'}, None),
 (9, 'adaptive probe certificate limits', CL, ['AdaptiveProbe'], {'Unsupported', 'Unknown'}, None),
 (10, 'unattained supremum', CL, ['UnattainedSupremum'], {'Unsupported', 'Unknown'}, None),
]

def zero_stale(x):
    if isinstance(x, dict): return {k: (0 if k == 'stale' else zero_stale(v)) for k, v in x.items()}
    if isinstance(x, list): return [zero_stale(v) for v in x]
    return x

def tampered_copy(tmp):
    src = os.path.dirname(os.path.join(DOCS, WX)); dst = os.path.join(tmp, 'wx')
    shutil.copytree(src, dst)
    p = os.path.join(dst, 'streams/replies_gate.json'); raw = open(p).read()
    try: new = json.dumps(zero_stale(json.loads(raw)))
    except ValueError: new = raw
    if new == raw: new = raw + '\n'
    open(p, 'w').write(new)
    return os.path.join(dst, os.path.basename(WX))

def run(path):
    p = subprocess.run([DCALC, path], capture_output=True, text=True, timeout=60)
    if p.returncode: raise RuntimeError('dcalc rc=%d on %s' % (p.returncode, path))
    out = []
    for line in p.stdout.splitlines():
        if ' => ' not in line: continue
        head, env = line.split(' => ', 1)
        st = re.search(r'\(Status (\w+)\)', env).group(1)
        rs = re.search(r'\(Reason "((?:\\.|[^"\\])*)"\)', env)
        out.append((head, st, rs.group(1) if rs else ''))
    return out

def main():
    fails = 0; tmp = tempfile.mkdtemp(prefix='dcalc-neg-')
    # review 2 F8: AC4 table with the expected and the ACTUAL statuses of this run
    rows = ['| # | Entry | Requests matched | M0 status (allowed) | Actual status (this run) | Result |',
            '|---|---|---|---|---|---|']
    try:
        for n, title, fx, pats, allowed, why in ENTRIES:
            path = tampered_copy(tmp) if fx.startswith('TAMPERED:') else os.path.join(DOCS, fx)
            hits = [r for r in run(path) if any(p in r[0] for p in pats)]
            bad = [r for r in hits if r[1] not in allowed or (why and why not in r[2])]
            ok = bool(hits) and not bad
            if n == 3:   # the untampered stream must not be refused
                clean = [r for r in run(os.path.join(DOCS, WX)) if r[1] == 'InvalidInput']
                if clean: ok = False; bad += clean
            counts = {}
            for r in hits: counts[r[1]] = counts.get(r[1], 0) + 1
            print('%2d %-4s %-62s %d requests %s' % (n, 'PASS' if ok else 'FAIL', title, len(hits), json.dumps(counts, sort_keys=True)))
            for r in bad[:3]: print('     got %s on %s: %s' % (r[1], r[0][:90], r[2][:120]))
            fails += not ok
            rows.append('| %d | %s | %d | %s | %s | %s |' % (n, title, len(hits), ' or '.join(sorted(allowed)),
                        ', '.join('%s %d' % kv for kv in sorted(counts.items())) or 'none', 'PASS' if ok else 'FAIL'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
    os.makedirs(os.path.join(root, 'build'), exist_ok=True)
    with open(os.path.join(root, 'build', 'negative-table.md'), 'w') as f: f.write('\n'.join(rows) + '\n')
    print('negative suite: %s' % ('PASS (10/10)' if not fails else 'FAIL (%d)' % fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
