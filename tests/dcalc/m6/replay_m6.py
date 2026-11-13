#!/usr/bin/env python3
"""Independent replay of M6 Contracts answers (t-2026-11-13-mettadinc-m6).

usage: replay_m6.py fixture.metta dcalc.out
Own s-expression reader and own rational evaluator (no dcalc code).  Every Checked/Refuted
CheckImplementation or ThenContracts row that claims (Replayed True) is recomputed from the
fixture: the affine bound E(f-hat(xh), f(x)) <= L*D(xh, x) + eta over every ordered audited pair
(spec section 9, OneMinusAbsoluteDifference distances = |a - b|), and Proposition 9.1 for
compositions.  Exit 0 iff every such row is ACCEPTed."""
import sys
from fractions import Fraction as Q

def toks(t):
    i, n = 0, len(t)
    while i < n:
        c = t[i]
        if c.isspace(): i += 1
        elif c == ';':
            while i < n and t[i] != '\n': i += 1
        elif c in '()': yield c; i += 1
        elif c == '"':
            j = i + 1
            while j < n and t[j] != '"': j += 2 if t[j] == '\\' else 1
            yield t[i:j + 1]; i = j + 1
        else:
            j = i
            while j < n and not t[j].isspace() and t[j] not in '()"': j += 1
            yield t[i:j]; i = j
def read_all(text):
    st = [[]]
    for k in toks(text):
        if k == '(': st.append([])
        elif k == ')': x = st.pop(); st[-1].append(x)
        else: st[-1].append(k)
    return st[0]
def head(t): return t[0] if isinstance(t, list) and t and isinstance(t[0], str) else None
def field(t, h):
    for x in (t[1:] if isinstance(t, list) else []):
        if head(x) == h: return x
    return None
def rat(x):
    if isinstance(x, str): return Q(int(x))
    if head(x) == 'Rat' and len(x) == 3: return Q(int(x[1]), int(x[2]))
    raise ValueError('not rational: %r' % (x,))

class Mod:
    def __init__(self, form):
        self.name = form[1]; self.car = {}; self.maps = {}; self.impl = {}; self.derive = {}; self.tol = {}
        for d in form[2:]:
            h = head(d)
            if h == 'Carrier' and head(d[3]) == 'Enum': self.car[d[1]] = [rat(e) for e in d[3][1:]]
            elif h == 'Map' and head(d[4]) == 'Body': self.maps[d[1]] = (field(d, 'From')[1], d[4][1][0], d[4][2])
            elif h == 'Implementation': self.impl[d[1]] = {k: field(d, k)[1] for k in ('Ideal', 'Actual', 'Audit', 'InputDistance', 'OutputDistance')}
            elif h == 'Derive': self.derive[d[1]] = d[2]
            elif h == 'Tolerance': self.tol[d[1]] = d[3]
    def ev(self, b, var, v):
        if b == var: return v
        if isinstance(b, str) or head(b) == 'Rat': return rat(b)
        op = head(b)
        if op in ('Add', 'Sub', 'Mul') and len(b) == 3:
            x, y = self.ev(b[1], var, v), self.ev(b[2], var, v)
            return x + y if op == 'Add' else x - y if op == 'Sub' else x * y
        if op in self.maps and len(b) == 2: return self.app(op, self.ev(b[1], var, v))
        raise ValueError('Body operator %r' % (op,))
    def app(self, f, v):
        frm, var, body = self.maps[f]
        if v not in self.car[frm]: raise ValueError('%s applied outside its From carrier' % f)
        return self.ev(body, var, v)
    def worst(self, name, L, eta):
        """(holds, first violating (xh, x, gap, bound) or None)"""
        I = self.impl[name]
        for t in (I['InputDistance'], I['OutputDistance']):
            if head(self.tol.get(t)) != 'OneMinusAbsoluteDifference': raise ValueError('distance %s not replayable' % t)
        X = self.car[I['Audit']]
        for a in X:
            for b in X:
                gap = abs(self.app(I['Actual'], a) - self.app(I['Ideal'], b)); bound = L * abs(a - b) + eta
                if gap > bound: return False, (a, b, gap, bound)
        return True, None

def need(c, msg):
    if not c: raise AssertionError(msg)

def replay(M, req, res):
    st = field(res, 'Status')[1]; h = head(req)
    if h == 'CheckImplementation':
        L, eta = rat(req[2][1]), rat(req[2][2]); ok, w = M.worst(req[1], L, eta)
        if st == 'Checked':
            need(ok, 'Checked but pair %s violates the bound' % (w,))
            g = field(field(res, 'Value'), 'Grade'); need(g and (rat(g[1]), rat(g[2])) == (L, eta), 'Value Grade differs from the request')
            return 'affine bound over %d audited pairs' % len(M.car[M.impl[req[1]]['Audit']]) ** 2
        need(st == 'Refuted' and not ok, 'Refuted but every audited pair meets the bound')
        wit = field(field(field(res, 'Evidence'), 'Witness'), 'Pair'); W = field(field(res, 'Evidence'), 'Witness')
        a, b = rat(field(wit, 'Audited')[1]), rat(field(wit, 'Reference')[1]); I = M.impl[req[1]]
        need(a in M.car[I['Audit']] and b in M.car[I['Audit']], 'witness pair is not audited')
        gap = abs(M.app(I['Actual'], a) - M.app(I['Ideal'], b)); bound = L * abs(a - b) + eta
        need(gap > bound, 'witness pair meets the bound'); need(rat(field(W, 'OutputGap')[1]) == gap and rat(field(W, 'Bound')[1]) == bound, 'witness numbers differ')
        return 'violating pair replayed'
    if h == 'ThenContracts':
        need(st == 'Checked', 'ThenContracts replays Checked rows only')
        prem = []
        for o in req[1:3]:
            need(head(o) == 'Output' and o[2] == 'Value' and o[1] in M.derive, 'premise is not (Output Derive Value)')
            p = M.derive[o[1]]; need(head(p) == 'CheckImplementation', 'premise is not CheckImplementation')
            L, eta = rat(p[2][1]), rat(p[2][2]); ok, w = M.worst(p[1], L, eta); need(ok, 'premise %s does not hold: %s' % (p[1], w)); prem.append((p[1], L, eta))
        (n1, L1, e1), (n2, L2, e2) = prem; I1, I2 = M.impl[n1], M.impl[n2]
        need(I1['OutputDistance'] == I2['InputDistance'], 'distances do not chain')
        for x in M.car[I1['Audit']]:
            for f in (I1['Ideal'], I1['Actual']): need(M.app(f, x) in M.car[I2['Audit']], 'value of %s outside %s audit' % (f, n2))
        g = field(field(res, 'Value'), 'Grade'); need(g and (rat(g[1]), rat(g[2])) == (L2 * L1, L2 * e1 + e2), 'composite Grade is not Proposition 9.1')
        return 'Proposition 9.1 composite grade'
    raise AssertionError('no replay rule for %s' % h)

def main(fx, out):
    forms = read_all(open(fx, encoding='utf-8').read()); mods = {f[1]: Mod(f) for f in forms if head(f) == 'DC.Module'}
    bad = rows = 0
    for line in open(out, encoding='utf-8').read().splitlines():
        if ' => ' not in line: continue
        res = read_all(line.split(' => ', 1)[1])[0]; st = field(res, 'Status')[1]
        asr = field(res, 'Assurance'); rep = field(asr, 'Replayed') if asr else None
        if st not in ('Checked', 'Refuted') or not rep or rep[1] != 'True': continue
        rows += 1; mod = line.split(' ', 1)[0]; req = field(res, 'Claim')[1]
        try: print('ACCEPT    %s' % replay(mods[mod], req, res))
        except (AssertionError, ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as e:
            bad += 1; print('REJECT    %s: %s' % (line.split(' => ')[0][:80], e))
    print('replay_m6: %d rows, %d not accepted -> %s' % (rows, bad, 'PASS' if rows and not bad else 'FAIL'))
    return 1 if bad or not rows else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1], sys.argv[2]))
