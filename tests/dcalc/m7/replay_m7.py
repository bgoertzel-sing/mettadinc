#!/usr/bin/env python3
"""M7 replayer (independent of the C code): availability rows W01-W02 (CheckNow on a (Use Hyperseed) module) and
M7-Neural rows N03 (CompareDistinctions pair counts) and N04 (AuditIntervention accuracies), and
M7-Discovery rows X01-X04 (exact F7 matrix ranks, first separator, Hom-dimensions).
Recomputes, from the fixture declarations only, every pair of states with equal Encode code that differ on some
declared observation; the Value must list exactly those pairs (sorted) and every Witness Merge must re-check."""
import hashlib
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'm6'))
from replay_m6 import read_all, field, head, need

def decl(mod, h, name):
    for d in mod[2:]:
        if head(d) == h and len(d) > 1 and d[1] == name: return d
    return None
def cases(mp):
    cs = field(mp, 'Cases'); need(cs is not None, 'map %s has no Cases' % mp[1])
    return {c[0]: c[1] for c in cs[1:]}
def show(t): return t if isinstance(t, str) else '(' + ' '.join(show(x) for x in t) + ')'

def replay_avail(mod, req, res):
    rep = decl(mod, 'Representation', req[1]); need(rep, 'no Representation %s' % req[1])
    mach = decl(mod, 'Machine', field(rep, 'Of')[1]); car = decl(mod, 'Carrier', field(mach, 'States')[1])
    states = field(car, 'Enum')[1:]; code = cases(decl(mod, 'Map', field(rep, 'Encode')[1]))
    obs = []
    for o in mach[2:]:
        if head(o) == 'Observe':
            for k in range(1, len(o) - 1, 2): obs.append((o[k], cases(decl(mod, 'Map', o[k + 1]))))
    need(obs, 'no observations')
    want = sorted(tuple(sorted((a, b))) for i, a in enumerate(states) for b in states[i + 1:]
                  if show(code[a]) == show(code[b]) and any(show(m[a]) != show(m[b]) for _, m in obs))
    st = field(res, 'Status')[1]
    need(st == ('Refuted' if want else 'Checked'), 'status %s, recomputed %s' % (st, 'Refuted' if want else 'Checked'))
    v = field(field(res, 'Value'), 'MergedPairs'); need(v is not None, 'no MergedPairs value')
    got = [(x[1], x[2]) for x in v[1:]]; need(got == want, 'MergedPairs %s != recomputed %s' % (got, want))
    w = field(field(field(res, 'Evidence'), 'Witness'), 'MergedPairs'); need(w is not None, 'no witness')
    need(sorted(tuple(sorted((x[1][1], x[1][2]))) for x in w[1:]) == want, 'witness pairs differ from value')
    om = dict(obs)
    for x in w[1:]:
        a, b = x[1][1], x[1][2]; c = field(x, 'Code')[1]; o = field(x, 'Observe')
        need(show(code[a]) == show(c) == show(code[b]), 'witness code differs for %s %s' % (a, b))
        need(o[1] in om and show(om[o[1]][a]) == show(o[2]) and show(om[o[1]][b]) == show(o[3]) and show(o[2]) != show(o[3]),
             'witness observation does not separate %s %s' % (a, b))
    return '%s %s: %d merged pairs %s' % (req[0], req[1], len(want), want)

# ---- M7-Neural rows (N03 CompareDistinctions, N04 AuditIntervention): recomputed from the declarations only ----
from fractions import Fraction as Fr
def carrier_elems(mod, c):
    if isinstance(c, list) and head(c) == 'Product': return [['Tuple', a, b] for a in carrier_elems(mod, c[1]) for b in carrier_elems(mod, c[2])]
    car = decl(mod, 'Carrier', c); need(car, 'no Carrier %s' % show(c))
    e = field(car, 'Enum')
    if e is not None: return e[1:]
    p = field(car, 'Product'); need(p is not None, 'carrier %s neither Enum nor Product' % c)
    return carrier_elems(mod, ['Product'] + p[1:])
def unify(p, v, env):
    if isinstance(p, str) and p.startswith('$'): env[p] = v; return True
    if isinstance(p, str) or isinstance(v, str): return show(p) == show(v)
    return len(p) == len(v) and all(unify(a, b, env) for a, b in zip(p, v))
def ev(mod, b, env):
    if isinstance(b, str): return env.get(b, b) if b.startswith('$') else b
    h = b[0]
    if h == 'Tuple': return ['Tuple'] + [ev(mod, x, env) for x in b[1:]]
    if h == 'Xor':
        x, y = int(ev(mod, b[1], env)), int(ev(mod, b[2], env)); need(x in (0, 1) and y in (0, 1), 'Xor on non-bit'); return str(x ^ y)
    if h == 'GetTuple': t = ev(mod, b[1], env); return t[1 + int(b[2])]
    mp = decl(mod, 'Map', h); need(mp is not None and len(b) == 2, 'unknown body head %s' % h)
    return apply_map(mod, mp, ev(mod, b[1], env))
def apply_map(mod, mp, v):
    cs = field(mp, 'Cases')
    if cs is not None:
        for c in cs[1:]:
            env = {}
            if unify(c[0], v, env): return ev(mod, c[1], env)
        raise ValueError('map %s: no case for %s' % (mp[1], show(v)))
    bd = field(mp, 'Body'); need(bd is not None and len(bd[1]) == 1, 'map %s has no Cases/Body' % mp[1])
    return ev(mod, bd[2], {bd[1][0]: v})
def uniform_on(mod, name):
    me = decl(mod, 'Measure', name); need(me is not None and field(me, 'Uniform') is not None, 'measure %s not uniform' % name)
    return carrier_elems(mod, field(me, 'On')[1])
def rat(x): return Fr(x) if isinstance(x, str) else None
def replay_compare(mod, req, res):
    enc = [decl(mod, 'Map', field(decl(mod, 'Representation', r), 'Encode')[1]) for r in req[1:3]]
    pl = decl(mod, 'PairLaw', field(req, 'Under')[1]); ind = field(pl, 'Independent')
    need(ind[1] == ind[2] and field(pl, 'Diagonal')[1] == 'Included', 'pair law not (Independent M M) (Diagonal Included)')
    X = uniform_on(mod, ind[1]); n = len(X)
    co = [show(apply_map(mod, enc[0], x)) for x in X]; cn = [show(apply_map(mod, enc[1], x)) for x in X]
    mo = mn = cr = er = 0
    for i in range(n):
        for j in range(n):
            dO, dN = co[i] != co[j], cn[i] != cn[j]; mo += dO; mn += dN; cr += dN and not dO; er += dO and not dN
    want = {'MassOld': Fr(mo, n * n), 'MassNew': Fr(mn, n * n), 'Creation': Fr(cr, n * n), 'Erasure': Fr(er, n * n), 'Turnover': Fr(cr + er, n * n)}
    v = field(field(res, 'Value'), 'DistinctionComparison'); need(v is not None, 'no DistinctionComparison')
    got = {x[0]: rat(x[1]) for x in v[1:]}; need(got == want, 'values %s != recomputed %s' % (got, want))
    need(field(res, 'Status')[1] == 'Checked', 'status not Checked')
    return 'CompareDistinctions: %s' % ', '.join('%s %s' % (k, want[k]) for k in want)
def replay_audit(mod, req, res):
    systems = field(req, 'Systems')[1:]; iv = field(req, 'Intervention')[1]; need(head(iv) == 'SetReport', 'only SetReport')
    task = decl(mod, 'Map', field(req, 'Task')[1]); X = uniform_on(mod, field(req, 'Under')[1])
    need(field(req, 'Metric')[1] == 'Accuracy', 'only Accuracy')
    want = {}
    for sname in systems:
        rs = decl(mod, 'ReportSystem', sname); E = decl(mod, 'Map', field(rs, 'Encoder')[1]); R = decl(mod, 'Map', field(rs, 'Readout')[1])
        base = sum(show(apply_map(mod, R, ['Tuple', x, apply_map(mod, E, x)])) == show(apply_map(mod, task, x)) for x in X)
        intv = sum(show(apply_map(mod, R, ['Tuple', x, iv[1]])) == show(apply_map(mod, task, x)) for x in X)
        want[sname] = (Fr(base, len(X)), Fr(intv, len(X)))
    t = field(field(field(res, 'Value'), 'MetricTable'), 'Table'); need(t is not None, 'no MetricTable Table')
    got = {r[1]: (rat(field(r, 'Baseline')[1]), rat(field(r, 'Intervened')[1])) for r in t[1:]}
    need(got == want, 'table %s != recomputed %s' % (got, want)); need(field(res, 'Status')[1] == 'Checked', 'status not Checked')
    return 'AuditIntervention: %s' % ', '.join('%s %s->%s' % (k, a, b) for k, (a, b) in want.items())

# ---- M7 Neural rows (N01-N06): own evaluator for carriers, Cases/Body maps, machines ----
import itertools
from fractions import Fraction as Fr
def uses(mod, lib): return any(head(d) == 'Use' and lib in d[1:] for d in mod[2:])
def _match(p, v, env):
    if isinstance(p, str):
        if p.startswith('$'): env[p] = v; return True
        return p == v
    return isinstance(v, list) and len(p) == len(v) and all(_match(a, b, env) for a, b in zip(p, v))
class Mod:
    def __init__(s, mod):
        s.mod, s.car, s.maps = mod, {}, {}
        for d in mod[2:]:
            if head(d) == 'Carrier':
                e, pr = field(d, 'Enum'), field(d, 'Product')
                if e: s.car[d[1]] = list(e[1:])
                elif pr: s.car[d[1]] = [['Tuple'] + list(x) for x in itertools.product(*[s.car[c] for c in pr[1:]])]
            elif head(d) == 'Map': s.maps[d[1]] = d
    def ev(s, b, env):
        if isinstance(b, str):
            if b.startswith('$'): need(b in env, 'unbound %s' % b); return env[b]
            return b
        h = b[0]
        if h == 'Tuple': return ['Tuple'] + [s.ev(x, env) for x in b[1:]]
        if h == 'Xor':
            a, c = s.ev(b[1], env), s.ev(b[2], env); need(a in ('0', '1') and c in ('0', '1'), 'Xor on non-bits')
            return str(int(a) ^ int(c))
        if h == 'GetTuple':
            x = s.ev(b[1], env); k = int(b[2]); need(head(x) == 'Tuple' and 0 <= k < len(x) - 1, 'GetTuple out of range')
            return x[k + 1]
        if h in s.maps and len(b) == 2: return s.app(h, s.ev(b[1], env))
        raise AssertionError('unknown body operator %s' % h)
    def app(s, name, v):
        d = s.maps[name]; cs = field(d, 'Cases')
        if cs:
            for row in cs[1:]:
                env = {}
                if _match(row[0], v, env): return s.ev(row[1], env)
            raise AssertionError('map %s has no case for %s' % (name, show(v)))
        bd = field(d, 'Body'); need(bd is not None, 'map %s has neither Cases nor Body' % name)
        return s.ev(bd[2], {bd[1][0]: v})
def _mach(M, nm):
    mach = decl(M.mod, 'Machine', nm); need(mach, 'no Machine %s' % nm)
    S = M.car[field(mach, 'States')[1]]
    obs = [o[k + 1] for o in mach[2:] if head(o) == 'Observe' for k in range(1, len(o) - 1, 2)]
    lab = [o[k] for o in mach[2:] if head(o) == 'Observe' for k in range(1, len(o) - 1, 2)]
    act = [o[k + 1] for o in mach[2:] if head(o) == 'Action' for k in range(1, len(o) - 1, 2)]
    return mach, S, obs, lab, act
def n_checknow(M, req, res):
    rep = decl(M.mod, 'Representation', req[1]); mach, S, obs, lab, act = _mach(M, field(rep, 'Of')[1])
    enc = field(rep, 'Encode')[1]
    code = {show(x): show(M.app(enc, x)) for x in S}; O = {show(x): [show(M.app(m, x)) for m in obs] for x in S}
    bad = [(a, b) for i, a in enumerate(S) for b in S[i + 1:] if code[show(a)] == code[show(b)] and O[show(a)] != O[show(b)]]
    st = field(res, 'Status')[1]; need(st == ('Refuted' if bad else 'Checked'), 'status %s, recomputed %s' % (st, 'Refuted' if bad else 'Checked'))
    iv = field(field(field(res, 'Value'), 'DefectCheck'), 'Defect')[1]; need((iv[1] == '0') == (not bad), 'defect interval disagrees')
    if bad:
        w = field(field(field(res, 'Evidence'), 'Witness'), 'CurrentWitness'); pr = field(w, 'Pair'); a, b = show(pr[1]), show(pr[2])
        need(a in code and b in code and code[a] == code[b] and O[a] != O[b], 'witness pair does not refute')
        k = lab.index(field(w, 'Observe')[1])
        need(show(field(w, 'Left')[1]) == O[a][k] and show(field(w, 'Right')[1]) == O[b][k] and O[a][k] != O[b][k], 'witness observation wrong')
    else:
        bl = [[show(x) for x in blk[1:]] for blk in field(field(field(res, 'Evidence'), 'Certificate'), 'Blocks')[1:]]
        need(sorted(sum(bl, [])) == sorted(code), 'blocks are not a partition of the states')
        need(all(len({code[x] for x in g}) == 1 and len({tuple(O[x]) for x in g}) == 1 for g in bl), 'a block mixes codes or observations')
    return '%s %s: %s (%d refuting pairs)' % (req[0], req[1], st, len(bad))
def _stable(M, S, act, key0):
    key = {show(x): key0(x) for x in S}
    while True:
        ids = {}
        for x in S: ids.setdefault(key[show(x)], len(ids))
        nk = {show(x): (ids[key[show(x)]],) + tuple(ids[key[show(M.app(a, x))]] for a in act) for x in S}
        if len(set(nk.values())) == len(set(key.values())): break
        key = nk
    g = {}
    for x in S: g.setdefault(key[show(x)], []).append(show(x))
    return sorted(sorted(v) for v in g.values())
def n_partition(M, req, res):
    if req[0] == 'Refine':
        need(['Preserve', 'Encoding'] in req[2:], 'Refine without (Preserve Encoding)')
        rep = decl(M.mod, 'Representation', req[1]); mach, S, obs, lab, act = _mach(M, field(rep, 'Of')[1]); enc = field(rep, 'Encode')[1]
        want = _stable(M, S, act, lambda x: (show(M.app(enc, x)),) + tuple(show(M.app(m, x)) for m in obs))
    else:
        mach, S, obs, lab, act = _mach(M, req[1])
        want = _stable(M, S, act, lambda x: tuple(show(M.app(m, x)) for m in obs))
    need(field(res, 'Status')[1] == 'Checked', 'status not Checked')
    part = field(field(field(res, 'Value'), 'Refinement'), 'Partition')
    got = sorted(sorted(show(x) for x in b[1:]) for b in part[1:]); need(got == want, 'partition %s != recomputed %s' % (got, want))
    return '%s %s: %d classes' % (req[0], req[1], len(want))
def n_compare(M, req, res):
    ro, rn = decl(M.mod, 'Representation', req[1]), decl(M.mod, 'Representation', req[2])
    mach, S, obs, lab, act = _mach(M, field(ro, 'Of')[1]); need(field(rn, 'Of')[1] == field(ro, 'Of')[1], 'different machines')
    pl = decl(M.mod, 'PairLaw', req[3][1]); ind = field(pl, 'Independent'); need(ind[1] == ind[2] and field(pl, 'Diagonal')[1] == 'Included', 'pair law not i.i.d. with diagonal')
    ms = decl(M.mod, 'Measure', ind[1]); need(field(ms, 'Uniform') is not None or ['Uniform'] in ms, 'measure not uniform')
    need(M.car[field(ms, 'On')[1]] == S, 'measure not on the states')
    eo = [show(M.app(field(ro, 'Encode')[1], x)) for x in S]; en = [show(M.app(field(rn, 'Encode')[1], x)) for x in S]
    n = len(S); P = range(n); D = n * n
    mo = sum(eo[x] != eo[y] for x in P for y in P); mn = sum(en[x] != en[y] for x in P for y in P)
    cr = sum(en[x] != en[y] and eo[x] == eo[y] for x in P for y in P); er = sum(eo[x] != eo[y] and en[x] == en[y] for x in P for y in P)
    want = {'MassOld': Fr(mo, D), 'MassNew': Fr(mn, D), 'Creation': Fr(cr, D), 'Erasure': Fr(er, D), 'Turnover': Fr(cr + er, D)}
    need(field(res, 'Status')[1] == 'Checked', 'status not Checked')
    v = field(field(res, 'Value'), 'DistinctionComparison')
    for k, w in want.items(): need(Fr(field(v, k)[1]) == w, '%s %s != recomputed %s' % (k, field(v, k)[1], w))
    return 'CompareDistinctions: %s' % ', '.join('%s %s' % (k, w) for k, w in want.items())
def n_audit(M, req, res):
    sy = field(req, 'Systems')[1:]; v = field(field(req, 'Intervention'), 'SetReport')[1]; task = field(req, 'Task')[1]
    ms = decl(M.mod, 'Measure', field(req, 'Under')[1]); S = M.car[field(ms, 'On')[1]]; n = len(S)
    need(field(req, 'Metric')[1] == 'Accuracy', 'metric not Accuracy'); need(field(res, 'Status')[1] == 'Checked', 'status not Checked')
    rows = {r[1]: r for r in field(field(field(res, 'Value'), 'MetricTable'), 'Table')[1:]}; need(sorted(rows) == sorted(sy), 'table rows differ from systems')
    out = []
    for s in sy:
        rs = decl(M.mod, 'ReportSystem', s); enc, rd = field(rs, 'Encoder')[1], field(rs, 'Readout')[1]
        b = Fr(sum(show(M.app(rd, ['Tuple', x, M.app(enc, x)])) == show(M.app(task, x)) for x in S), n)
        i = Fr(sum(show(M.app(rd, ['Tuple', x, v])) == show(M.app(task, x)) for x in S), n)
        need(Fr(field(rows[s], 'Baseline')[1]) == b and Fr(field(rows[s], 'Intervened')[1]) == i, '%s accuracies differ from recomputed %s/%s' % (s, b, i))
        out.append('%s %s->%s' % (s, b, i))
    return 'AuditIntervention: ' + ', '.join(out)
NEURAL = {'CheckNow': n_checknow, 'CompareDistinctions': n_compare, 'AuditIntervention': n_audit, 'Refine': n_partition, 'MinimizeForQueries': n_partition}

# ---- M7 Patterns rows (Q01-Q02), spec 12.6: own decoder/cost (Literal | Tokens | Repeat, decoder Expand) ----
def p_dec(d, w):
    h = head(d)
    if h == 'Tokens': return list(d[1:]), w['Tokens'] * (len(d) - 1)
    if h == 'Literal': return p_dec(d[1], w)
    if h == 'Repeat':
        s, c = p_dec(d[1], w); k = int(d[2]); need(k >= 1, 'Repeat count < 1'); return s * k, c + w['Operator'] + w['Count']
    raise AssertionError('description operator %s outside Literal|Tokens|Repeat' % h)
def p_row(mod, req, res):
    if req[0] == 'FindCheapestDescription': sysd = decl(mod, 'DescriptionSystem', req[1]); tg = field(req, 'Target')
    else:
        wd = decl(mod, 'PatternWitness', req[1]); sysd = decl(mod, 'DescriptionSystem', field(wd, 'System')[1]); tg = field(wd, 'Target')
    need(field(sysd, 'Decoder')[1] == 'Expand', 'decoder not Expand')
    w = {f[0]: int(f[1]) for f in field(sysd, 'Cost')[1:]}
    target = list(tg[1][1:]); ds = {d[1]: p_dec(d[2], w) for d in sysd[2:] if head(d) == 'Description'}
    st = field(res, 'Status')[1]
    if req[0] == 'FindCheapestDescription':
        ok = {n: c for n, (s, c) in ds.items() if s == target}; need(ok, 'no description decodes to the target')
        bc = min(ok.values()); v = field(field(res, 'Value'), 'DescriptionResult')
        need(st == 'Checked' and field(v, 'Optimality')[1] == 'Checked', 'status/optimality not Checked')
        need(int(field(v, 'Cost')[1]) == bc and ok.get(field(v, 'Description')[1]) == bc, 'cheapest %s/%s != recomputed cost %d' % (field(v, 'Description')[1], field(v, 'Cost')[1], bc))
        cands = {c[1]: int(field(c, 'Cost')[1]) for c in field(field(field(res, 'Evidence'), 'Certificate'), 'Candidates')[1:]}
        need(cands == {n: c for n, (s, c) in ds.items()}, 'candidate costs differ from recomputed')
        return 'FindCheapestDescription: costs %s, min %d' % (sorted(c for _, c in ds.values()), bc)
    s, c = ds[field(wd, 'Description')[1]]; base = ds[field(sysd, 'Baseline')[1]][1]
    holds = s == target and c < base; need(st == ('Checked' if holds else 'Refuted'), 'status %s, recomputed holds=%s' % (st, holds))
    for where, ce in (('Evidence', field(field(res, 'Evidence'), 'Certificate')), ('Value', field(field(field(res, 'Value'), 'Verdict'), 'Certificate'))):
        need(ce is not None, '%s certificate missing' % where)
        need(field(ce, 'Decodes')[1] == ('True' if s == target else 'False'), '%s Decodes differs' % where)
        need(int(field(ce, 'Cost')[1]) == c and int(field(ce, 'BaselineCost')[1]) == base and int(field(ce, 'Gain')[1]) == base - c, '%s certificate costs differ' % where)
    return 'CheckPatternWitness %s: cost %d < baseline %d' % (req[1], c, base)

# ---- M7-Discovery rows X01-X04 (arithmetic_probes): exact F7 4x4 arithmetic recomputed from the declarations only ----
def x_inv7(a): return pow(a % 7, 5, 7)
def x_rank7(M):
    M = [[x % 7 for x in r] for r in M]; rk = 0; cols = len(M[0]) if M else 0
    for c in range(cols):
        p = next((i for i in range(rk, len(M)) if M[i][c]), None)
        if p is None: continue
        M[rk], M[p] = M[p], M[rk]; iv = x_inv7(M[rk][c]); M[rk] = [(x * iv) % 7 for x in M[rk]]
        for i in range(len(M)):
            if i != rk and M[i][c]: f = M[i][c]; M[i] = [(x - f * y) % 7 for x, y in zip(M[i], M[rk])]
        rk += 1
    return rk
def x_mul(A, B): return [[sum(A[i][k] * B[k][j] for k in range(4)) % 7 for j in range(4)] for i in range(4)]
def x_lit(m): need(head(m) == 'Matrix4' and len(m) == 5, 'not a Matrix4 literal'); return [[int(x) % 7 for x in r] for r in m[1:]]
def x_mat(b, env):
    if b == 'I4': return [[int(i == j) for j in range(4)] for i in range(4)]
    h = head(b)
    if h == 'Get': return x_lit(field(env[b[1]], b[2])[1])
    if h == 'Sub': A, B = x_mat(b[1], env), x_mat(b[2], env); return [[(A[i][j] - B[i][j]) % 7 for j in range(4)] for i in range(4)]
    if h == 'Scale': c = int(env.get(b[1], b[1])); A = x_mat(b[2], env); return [[(c * x) % 7 for x in r] for r in A]
    if h == 'Square': A = x_mat(b[1], env); return x_mul(A, A)
    raise ValueError('matrix term %s' % show(b))
def x_val(b, env):
    h = head(b)
    if h == 'Rank': return str(x_rank7(x_mat(b[1], env)))
    if h == 'PowerRanks':
        A = x_mat(b[1], env); P_ = A; out = ['Tuple']
        for _ in range(int(b[2])): out.append(str(x_rank7(P_))); P_ = x_mul(P_, A)
        return out
    if h == 'Tuple': return ['Tuple'] + [x_val(x, env) for x in b[1:]]
    raise ValueError('value term %s' % show(b))
def x_const(mod, nm): d = decl(mod, 'Const', nm); need(d is not None, 'no Const %s' % nm); return d[3]
def x_apply(mod, mp, cand): bd = field(mp, 'Body'); return show(x_val(bd[2], {bd[1][0]: x_const(mod, cand)}))
def x_states(mod, mach): return field(decl(mod, 'Carrier', field(mach, 'States')[1]), 'Enum')[1:]
def x_obs(mod, mach, s): return [x_apply(mod, decl(mod, 'Map', o[2]), s) for o in mach[2:] if head(o) == 'Observe']
def x_hom(A, B):
    rows = []
    for Af, Bf in zip(A, B):
        for i in range(4):
            for j in range(4):
                r = [0] * 16
                for k in range(4): r[i * 4 + k] += Af[k][j]; r[k * 4 + j] -= Bf[i][k]
                rows.append(r)
    return 16 - x_rank7(rows)
def x_row(mod, req, res):
    st = field(res, 'Status')[1]; h = head(req)
    if h == 'MinimizeForQueries':
        mach = decl(mod, 'Machine', req[1]); X = x_states(mod, mach); O = {s: x_obs(mod, mach, s) for s in X}; want, used = [], set()
        for s in X:
            if s in used: continue
            b = [t for t in X if t not in used and O[t] == O[s]]; used.update(b); want.append(b)
        part = field(field(field(res, 'Value'), 'Refinement'), 'Partition'); got = [list(b[1:]) for b in part[1:]]
        need(got == want and st == 'Checked', 'partition %s != recomputed %s' % (got, want))
        return 'MinimizeForQueries %s: blocks %s' % (req[1], want)
    if h == 'CheckNow':
        rep = decl(mod, 'Representation', req[1]); mach = decl(mod, 'Machine', field(rep, 'Of')[1]); enc = decl(mod, 'Map', field(rep, 'Encode')[1])
        X = x_states(mod, mach); C = {s: x_apply(mod, enc, s) for s in X}; O = {s: x_obs(mod, mach, s) for s in X}
        want = [[a, b] for i, a in enumerate(X) for b in X[i + 1:] if C[a] == C[b] and O[a] != O[b]]
        w = field(res, 'Evidence'); w = field(w, 'Witnesses') if w else None; got = [list(p[1:]) for p in (w[1:] if w else [])]
        need(got == want and st == ('Refuted' if want else 'Checked'), 'witnesses %s / %s != recomputed %s' % (got, st, want))
        return 'CheckNow %s: %s, merged pairs %s' % (req[1], st, want)
    if h == 'SeekSeparator':
        pr = field(req, 'Pair'); gen = field(decl(mod, 'ObserverFamily', field(req, 'Family')[1]), 'Generate')
        fo, lam = gen[1], gen[2][1]; need(head(fo) == 'For' and fo[2] == ['Elements', 'F7'] and head(lam) == 'Lambda', 'family not a generated F7 Lambda')
        bu = field(req, 'Budget'); budget = int(bu[1][1]) if bu and head(bu[1]) == 'Probes' else 7
        want, found = [], None
        for b in range(min(7, budget)):
            va, vb = [show(x_val(lam[2], {lam[1][0][0]: x_const(mod, c), fo[1]: str(b)})) for c in pr[1:3]]
            want.append((str(b), va, vb))
            if va != vb: found = b; break
        need(found is not None, 'no separator within budget')
        sr = field(field(res, 'Value'), 'SeparatorResult'); tab = field(sr, 'Evaluations')[1]
        got = [(r[1][1], show(r[2][1]), show(r[3][1])) for r in tab[1:]]; inst = field(sr, 'Observer')[1]
        need(got == want and inst[2][1] == str(found) and st == 'Checked', 'separator %s / %s != recomputed b=%d %s' % (show(inst), got, found, want))
        return 'SeekSeparator: first separator b=%d (%s vs %s)' % (found, want[-1][1], want[-1][2])
    if h == 'DecideEquivalence':
        pr = field(req, 'Pair'); flds = [f[0] for f in decl(mod, 'Record', 'MarkedPair')[2:]]
        A, B = [[x_lit(field(x_const(mod, c), f)[1]) for f in flds] for c in pr[1:3]]
        want = {'EndA': x_hom(A, A), 'HomAB': x_hom(A, B), 'EndB': x_hom(B, B)}
        tab = field(field(field(res, 'Value'), 'EquivalenceDecision'), 'HomDimensions')[1]; got = {r[1]: int(r[2]) for r in tab[1:]}
        need(got == want and len(set(want.values())) > 1 and st == 'Refuted', 'hom dims %s != recomputed %s' % (got, want))
        return 'DecideEquivalence: Refuted, hom dims %s' % want
    raise ValueError('unknown M7-Discovery request %s' % h)

def main(fx, out):
    forms = read_all(open(fx, encoding='utf-8').read()); fm = {f[1]: f for f in forms if head(f) == 'DC.Module'}
    bad = rows = 0
    for line in open(out, encoding='utf-8').read().splitlines():
        if ' => ' not in line: continue
        res = read_all(line.split(' => ', 1)[1])[0]; st = field(res, 'Status')[1]
        mod = fm.get(line.split(' ', 1)[0]); sc = field(res, 'Scope'); fr = field(sc, 'Fragment') if sc else None
        if mod is None or st not in ('Checked', 'Refuted'): continue
        req = field(res, 'Claim')[1]
        if fr and fr[1] == 'M7-Availability': fn = lambda: replay_avail(mod, req, res)
        elif fr and fr[1] == 'M7-Patterns': fn = lambda: p_row(mod, req, res)
        elif fr and fr[1] == 'M7-Discovery': fn = lambda: x_row(mod, req, res)
        elif uses(mod, 'Neural') and head(req) in NEURAL: fn = lambda: NEURAL[head(req)](Mod(mod), req, res)
        else: continue
        rows += 1
        try:
            asr = field(res, 'Assurance'); rp = field(asr, 'Replayed') if asr else None
            need(rp and rp[1] == 'True', 'verdict without Replayed True')
            bd = field(res, 'Binding'); dg = field(bd, 'Digest') if bd else None   # review-1 F3: gate 3 in replay itself
            need(dg is not None and hashlib.sha256(show(mod).encode()).hexdigest() in show(dg), 'stale certificate: Binding Digest is not the sha256 of this module')
            print('ACCEPT    %s' % fn())
        except (AssertionError, ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as e:
            bad += 1; print('REJECT    %s: %s' % (line.split(' => ')[0][:80], e))
    print('replay_m7: %d rows, %d not accepted -> %s' % (rows, bad, 'PASS' if rows and not bad else 'FAIL'))
    return 1 if bad or not rows else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1], sys.argv[2]))
