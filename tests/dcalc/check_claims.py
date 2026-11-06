#!/usr/bin/env python3
"""M0 acceptance check (AC2 + AC5) for the dcalc core.

* Runs build/dcalc/dcalc over every fixture of the validation package.
* AC2: the nine M0 claims must return their manifest status; expected
  statuses come from manifest.json and oracle keys from the M0 table in
  docs/e0/MILESTONES.md (both read at run time, nothing hard-coded here).
  Oracle values are extracted from the result envelopes.
* AC5: every request is answered (no crash, one envelope per request); a
  Checked/Refuted answer outside the nine claims must match a manifest claim.
* Every Checked/Refuted envelope is replayed by replay.py (independent).
Exit 0 iff everything passes."""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import replay as R

PKG = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package')
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out'))
M0_IDS = ['E05', 'E08', 'E09', 'H08', 'H10', 'H12', 'C01', 'C02', 'C03']

def oracle_table():
    keys = {}
    for line in open(os.path.join(ROOT, 'docs/e0/MILESTONES.md'), encoding='utf-8'):
        cells = [c.strip() for c in line.split('|')]
        if len(cells) > 9 and cells[1] in M0_IDS:
            ok = cells[8]
            keys[cells[1]] = {} if ok in ('–', '-', '') else dict(
                (k.strip(), json.loads(v)) for k, v in (p.split('=', 1) for p in re.split(r';\s*(?=[\w.]+=)', ok)))
    return keys

def num(x): return int(x) if re.fullmatch(r'-?\d+', x) else x

def oracle_value(key, env):
    val = R.find(env, 'Value')[1]; evd = R.find(env, 'Evidence')
    if key == 'counterexamples.non_surjective_homomorphism':
        return R.find(val, 'Kind')[1] == 'Homomorphism' and R.find(val, 'Surjective')[1] == 'False'
    if key in ('literal_congruence.now', 'literal_congruence.updates'):
        iv = R.find(val, 'Defect')[1]; return iv[1] if iv[1] == iv[2] else None
    if key == 'literal_congruence.witness':
        w = R.find(evd, 'Witness')[1]; p = R.find(w, 'Pair')
        return [num(p[1]), num(p[2]), R.find(w, 'Action')[1], num(R.find(w, 'Left')[1]), num(R.find(w, 'Right')[1])]
    raise KeyError('no extractor for oracle key ' + key)

def main():
    claims = json.load(open(os.path.join(PKG, 'manifest.json')))['claims']
    by_req = {(c['module'], c['request']): c for c in claims}
    oracles = oracle_table(); os.makedirs(OUT, exist_ok=True); fails = []
    results, counts, crashes = {}, {}, 0
    fixtures = sorted(f for f in os.listdir(os.path.join(PKG, 'fixtures')) if f.endswith('.metta'))
    for f in fixtures:
        path = os.path.join(PKG, 'fixtures', f); out = os.path.join(OUT, f[:-6] + '.out')
        p = subprocess.run([DCALC, path], capture_output=True, text=True, timeout=60)
        if p.returncode != 0: crashes += 1; fails.append('crash rc=%d on %s' % (p.returncode, f))
        open(out, 'w').write(p.stdout)
        src = open(path, encoding='utf-8', errors='replace').read()
        expected = len(re.findall(r'!\(dc\.run\s', src)); got = 0
        for line in p.stdout.splitlines():
            if ' => ' not in line: continue
            got += 1; head, env = line.split(' => ', 1); mod, req = head.split(' ', 1)
            env = R.parse(env)[0]; st = R.find(env, 'Status')[1]
            counts[st] = counts.get(st, 0) + 1; results[(mod, req)] = (st, env)
        if got != expected: fails.append('%s: %d envelopes for %d requests' % (f, got, expected))
        rc = subprocess.run([sys.executable, os.path.join(HERE, 'replay.py'), path, out], capture_output=True, text=True)
        if rc.returncode: fails.append('replay failed on %s: %s' % (f, rc.stdout.strip()[-400:]))
    m0 = {c['id']: c for c in claims if c['id'] in M0_IDS}
    for cid in M0_IDS:
        c = m0[cid]; st, env = results.get((c['module'], c['request']), ('missing', None))
        ok = st == c['status']; notes = []
        for k, v in oracles.get(cid, {}).items():
            got = oracle_value(k, env) if env is not None else None
            if got != v: ok = False; notes.append('%s=%r expected %r' % (k, got, v))
            else: notes.append('%s=%s' % (k, json.dumps(got)))
        print('%-4s %-18s %-36s %-9s %s %s' % (cid, c['module'], c['request'], st, 'PASS' if ok else 'FAIL', ' '.join(notes)))
        if not ok: fails.append('claim %s' % cid)
    for (mod, req), (st, env) in sorted(results.items()):
        c = by_req.get((mod, req))
        if st in ('Checked', 'Refuted') and (c is None or c['id'] not in M0_IDS):
            if c is None or c['status'] != st: fails.append('%s %s: %s outside the M0 claims without a matching manifest claim' % (mod, req, st))
            else: print('extra %s %s %s %s (matches manifest)' % (c['id'], mod, req, st))
        if st not in ('Checked', 'Refuted', 'Unsupported', 'InvalidInput'): fails.append('%s %s: status %s' % (mod, req, st))
    print('AC5: %d fixtures, %d requests, %d crashes, statuses %s' % (len(fixtures), sum(counts.values()), crashes, json.dumps(counts, sort_keys=True)))
    for x in fails: print('FAIL', x)
    print('check_claims: %s' % ('PASS' if not fails else 'FAIL (%d)' % len(fails)))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
