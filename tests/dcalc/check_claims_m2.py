#!/usr/bin/env python3
"""M2 acceptance rows (t-2026-11-10-mettadinc-m2-v2): the 36 claims E01-E09,
P01-P11, H01-H12, G01-G04 of docs/e0/MILESTONES.md "M2".  For each row: the
status the manifest gives, the oracle keys, and a replay command that checks
the certificate independently of the producer (tests/dcalc/replay.py)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import replay as R
PKG = os.path.join(ROOT, 'docs/e0/docs/01_language_specification/validation_package')
M2_IDS = (['E0%d' % i for i in range(1, 10)] + ['P%02d' % i for i in range(1, 12)]
          + ['H%02d' % i for i in range(1, 13)] + ['G0%d' % i for i in range(1, 5)])

def m2_table():
    """Rows of the M2 claims table.  A statement cell may itself contain '|'
    (E03: n-|X/K_O|), so id, module, request and status come from the left and
    the fixture and oracle-key cells from the right."""
    rows, sec = {}, False
    for line in open(os.path.join(ROOT, 'docs/e0/MILESTONES.md'), encoding='utf-8'):
        if line.startswith('## '): sec = line.startswith('## M2:')
        if not sec or not line.startswith('| '): continue
        cells = [c.strip() for c in line.rstrip('\n').split('|')][1:-1]
        if len(cells) < 8 or cells[0] not in M2_IDS: continue
        ok = cells[-1]
        keys = {} if ok in ('–', '-', '') else dict(
            (k.strip(), json.loads(v)) for k, v in (p.split('=', 1) for p in re.split(r';\s*(?=[\w.]+=)', ok)))
        rows[cells[0]] = {'module': cells[1], 'request': cells[2].strip('`'), 'status': cells[3],
                          'fixture': cells[-2], 'keys': keys}
    return rows

import subprocess
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))
OUT = os.environ.get('DCALC_OUT', os.path.join(ROOT, 'build/dcalc/out-m2'))

def num(x):
    return int(x) if isinstance(x, str) and re.fullmatch(r'-?\d+', x) else x
def iv(val, head='Defect'):
    d = R.find(val, head); d = d[1] if d and isinstance(d[1], list) else d
    return d[1] if d and d[0] == 'Interval' and d[1] == d[2] else None
def tup(x):
    return [num(v) for v in x[1:]] if isinstance(x, list) and x and x[0] == 'Tuple' else num(x)
def witness(env):
    evd = R.find(env, 'Evidence'); w = R.find(evd, 'Witness')
    if w is None:
        for p in evd[1:]:
            if isinstance(p, list) and p[0] == 'Part': w = R.find(p, 'Witness') or w
    return w[1] if w else None

ENVS = {}
def row_defect(cid):
    e = ENVS.get(cid); return iv(R.find(e, 'Value')[1]) if e is not None else None
def extra_defect(row, req):
    """Runs one request not in the fixture (appended to a copy) and returns its defect."""
    src = open(fixture_of(row), encoding='utf-8').read() + '\n!(dc.run %s %s)\n' % (row['module'], req)
    os.makedirs(OUT, exist_ok=True); tmp = os.path.join(OUT, 'extra-%s.metta' % row['module'])
    open(tmp, 'w').write(src); rc, out, lines = run_fixture(tmp); line = lines.get((row['module'], req))
    return iv(R.find(R.parse(line.split(' => ', 1)[1])[0], 'Value')[1]) if line else None

def oracle_value(key, env, res):
    """Reads an oracle key off the producer's result (never off the oracle)."""
    val = R.find(env, 'Value')[1]
    if key == 'eight_state.witness':
        w = witness(env); P = R.find(w, 'Pair')
        return [[tup(P[1]), tup(P[2])], [d[1] for d in R.find(w, 'Word')[1:]], R.find(w, 'Query')[1],
                num(R.find(w, 'Left')[1]), num(R.find(w, 'Right')[1])]
    if key == 'eight_state.witness_bound':
        b = R.find(witness(env), 'LengthBound'); return num(b[1]) if b else None
    if key in ('packets.d_UV', 'packets.d_UV_disc_9_10', 'counterexamples.restriction.full'):
        v = iv(val); return num(v) if key.endswith('full') else v
    # Cross-row keys: the oracle records several claims under one key; each part is read
    # off the producer's own result for the row that makes that claim.
    if key == 'packets.defects_posterior_only':     # P03 gives the three defects, P04 the discounted one
        return [iv(val, k) for k in ('Current', 'Update', 'Behavioral')] + [row_defect('P04')]
    if key == 'counterexamples.horizon_index.correct':   # H05-H07 give h = 0, 1, 2; h = 3 is one extra request
        return [num(row_defect(c)) for c in ('H05', 'H06', 'H07')] + [num(extra_defect(res, '(CheckBehavioral Merge01 (Horizon (Steps 3)))'))]
    if key == 'small_fixtures.descent_converse':    # H09 behavioral defect, H10 update defect
        return {'behavioral': row_defect('H09'), 'update': row_defect('H10')}
    if key == 'counterexamples.pseudometric_zero':
        return 'dnow 0 without literal decoder' if iv(val) == '0' and R.find(val, 'Equality') == ['Equality', 'Observer'] else None
    if key == 'small_fixtures.chain_six_witness_length':
        return len(R.find(witness(env), 'Word')) - 1
    if key == 'counterexamples.non_surjective_homomorphism':
        return R.find(val, 'Kind')[1] == 'Homomorphism' and R.find(val, 'Surjective')[1] == 'False'
    if key == 'eight_state.repair_blocks':
        return [[tup(x) for x in B[1:]] for B in R.find(val, 'Partition')[1:]]
    if key in ('small_fixtures.eight_state_ledger', 'small_fixtures.packet_ledger'):
        L = R.find(val, 'Ledger'); return [R.find(L, 'Before')[1], R.find(L, 'After')[1]]
    if key == 'packets.frontier.1':   # the oracle writes packets E, U, V, B (spec Example 4.3): first letters
        P = [[x[0] for x in B[1:]] for B in R.find(val, 'Partition')[1:]]
        return [iv(val), R.find(val, 'Weakness')[1], P]
    if key == 'packets.induced_defect_E_UVB':
        return iv(val)
    raise KeyError('no extractor yet for oracle key ' + key)

def fixture_of(row):
    m = re.match(r'`([\w.]+\.metta)`', row['fixture']); return os.path.join(PKG, 'fixtures', m.group(1)) if m else None

def run_fixture(path):
    """dcalc output lines of one fixture, keyed by (module, request text)."""
    os.makedirs(OUT, exist_ok=True); out = os.path.join(OUT, os.path.basename(path)[:-6] + '.out')
    p = subprocess.run([DCALC, path], capture_output=True, text=True, timeout=60)
    open(out, 'w').write(p.stdout); lines = {}
    for line in p.stdout.splitlines():
        if ' => ' not in line: continue
        head, env = line.split(' => ', 1); mod, req = head.split(' ', 1); lines[(mod, req)] = line
    return p.returncode, out, lines

def replay_row(cid):
    """Independent replay of one row: its single result line goes through replay.py alone."""
    row = m2_table()[cid]; path = fixture_of(row); rc, out, lines = run_fixture(path)
    line = lines.get((row['module'], row['request']))
    if line is None: print('%s: no result line' % cid); return 1
    one = os.path.join(OUT, 'row-%s.out' % cid); open(one, 'w').write(line + '\n')
    p = subprocess.run([sys.executable, os.path.join(HERE, 'replay.py'), path, one], capture_output=True, text=True)
    print(p.stdout.strip()); ok = p.returncode == 0 and 'replay: 1 replayed' in p.stdout
    print('%s replay: %s' % (cid, 'PASS' if ok else 'FAIL')); return 0 if ok else 1

def main():
    rows = m2_table(); fails = []; cache = {}; n_pass = 0
    if len(rows) != 36: fails.append('M2 table has %d rows, expected 36' % len(rows))
    for cid in M2_IDS:                              # first pass: every row's result, for cross-row keys
        row = rows.get(cid)
        if not row: continue
        path = fixture_of(row)
        if path not in cache: cache[path] = run_fixture(path)
        line = cache[path][2].get((row['module'], row['request']))
        ENVS[cid] = R.parse(line.split(' => ', 1)[1])[0] if line else None
    for cid in M2_IDS:
        row = rows.get(cid)
        if not row: fails.append('row %s missing' % cid); continue
        path = fixture_of(row)
        if path not in cache: cache[path] = run_fixture(path)
        rc, out, lines = cache[path]
        line = lines.get((row['module'], row['request']))
        st, env = ('missing', None)
        if line: env = R.parse(line.split(' => ', 1)[1])[0]; st = R.find(env, 'Status')[1]
        ok = st == row['status']; notes = []
        for k, v in row['keys'].items():
            try: got = oracle_value(k, env, row) if env is not None else None
            except (KeyError, IndexError, TypeError) as ex: got = 'ERR:%s' % ex
            if got != v: ok = False; notes.append('%s=%r expected %r' % (k, got, v))
            else: notes.append('%s=%s' % (k, json.dumps(got)))
        cmd = 'python3 tests/dcalc/check_claims_m2.py --replay %s' % cid
        print('%-4s %-17s %-58s %-11s %s | %s | %s' % (cid, row['module'], row['request'][:58], st, 'PASS' if ok else 'FAIL', cmd, ' '.join(notes)))
        if ok: n_pass += 1
        else: fails.append('claim %s' % cid)
    for path, (rc, out, lines) in sorted(cache.items()):
        p = subprocess.run([sys.executable, os.path.join(HERE, 'replay.py'), path, out], capture_output=True, text=True)
        print('%s: %s' % (os.path.basename(path), p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'no output'))
        if p.returncode: fails.append('replay failed on %s' % os.path.basename(path))
    for x in fails: print('FAIL', x)
    print('check_claims_m2: %d/36 rows pass; %s' % (n_pass, 'PASS' if not fails else 'FAIL (%d)' % len(fails)))
    return 1 if fails else 0

if __name__ == '__main__':
    if sys.argv[1:2] == ['--table']:
        t = m2_table()
        for cid in M2_IDS: r = t.get(cid); print(cid, r['status'] if r else 'MISSING', r['request'] if r else '', json.dumps(r['keys']) if r else '')
        sys.exit(0)
    if sys.argv[1:2] == ['--replay']: sys.exit(replay_row(sys.argv[2]))
    sys.exit(main())
