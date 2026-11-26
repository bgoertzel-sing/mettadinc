#!/usr/bin/env python3
"""Replay-side Families elaborator (t-2026-11-24-mettadinc-families, review 1 finding 3).

Shares no code with src/dcalc/families.c: it is the Python design prototype the C port was checked against.
replay.py calls elaborate() on a module that uses Families before handing it to replay_sym.SymM, so witnesses
and reach scopes are replayed on the elaborated module (Parameters, For, Switch with Any, Exists/ForAll unfolded)."""
import re, sys
def parse(t):
    t = re.sub(r';[^\n]*', '', t); toks = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', t); out = []; st = [out]
    for k in toks:
        if k == '(': st.append([])
        elif k == ')': x = st.pop(); st[-1].append(x)
        else: st[-1].append(k)
    return out
def show(x): return x if isinstance(x, str) else '(' + ' '.join(show(y) for y in x) + ')'
def hd(x): return x[0] if isinstance(x, list) and x else None
def fld(d, h):
    for y in d[2:]:
        if hd(y) == h: return y
class Elab:
    def __init__(s, mods, name):
        s.mods = mods; s.m = mods[name]; s.enums = {}; s.tables = {}; s.maps = {}; s.consts = {}; s.mach = {}; s.decls = []
        items = list(s.m[2:]); exp = []
        for d in items:   # Import (Only ...): copy the named declarations of the imported module, in its order
            if hd(d) == 'Import':
                src = mods[d[1]]; only = set(fld(['', ''] + d[2:], 'Only')[1:])
                exp += [e for e in src[2:] if isinstance(e, list) and len(e) > 1 and isinstance(e[1], str) and e[1] in only]
            else: exp.append(d)
        s.items = exp
        for d in exp:
            h = hd(d)
            if h == 'Carrier' and fld(d, 'Of') == ['Of', 'Symbol']: s.enums[d[1]] = fld(d, 'Enum')[1:]
            elif h == 'Map' and fld(d, 'Table') and fld(d, 'From')[1] in s.enums:
                s.tables[d[1]] = {r[0]: r[1] for r in fld(d, 'Table')[1:]}
            elif h == 'Map': s.maps[d[1]] = d
            elif h == 'Const': s.consts[d[1]] = d[3]
    def term(s, t, env):
        if isinstance(t, str):
            if t in env: return env[t]
            if t == 'True': return '1'
            if t == 'False': return '0'
            return s.consts.get(t, t)
        h = t[0]; a = t[1:]
        if h in ('Exists', 'ForAll'):
            v, car, body = a; parts = [s.term(body, dict(env, **{v: e})) for e in s.enums[car]]
            return s.fold('Or' if h == 'Exists' else 'And', parts)
        if h == 'Switch':
            k = s.term(a[0], env)
            arm = next((r for r in a[1:] if r[0] == k), None) or next(r for r in a[1:] if r[0] == 'Any')
            return s.term(arm[1], env)
        if h in s.tables: return s.tables[h][s.term(a[0], env)]
        if h in s.maps:   # inline the call: parameters, then the word argument
            d = s.maps[h]; pr = fld(d, 'Parameters'); ps = [b[0] for b in pr[1:]] if pr else []
            body = fld(d, 'Body'); e2 = {p: s.term(x, env) for p, x in zip(ps, a)}
            e2[body[1][0]] = s.term(a[len(ps)], env); return s.term(body[2], e2)
        a = [s.term(x, env) for x in a]
        if h == 'Add' and all(x.isdigit() for x in a if isinstance(x, str)) and all(isinstance(x, str) for x in a): return str(sum(int(x) for x in a))
        if h == 'Eq' and all(isinstance(x, str) and not x.isdigit() and not x.startswith('$') for x in a): return '1' if a[0] == a[1] else '0'
        if h == 'Not' and a[0] in ('0', '1'): return '1' if a[0] == '0' else '0'
        if h in ('And', 'Or'): return s.fold(h, a)
        if h == 'If' and a[0] in ('0', '1'): return a[1] if a[0] == '1' else a[2]
        return [h] + a
    def fold(s, h, parts):
        unit, zero = ('1', '0') if h == 'And' else ('0', '1')
        if zero in parts: return zero
        parts = [p for p in parts if p != unit]
        if not parts: return unit
        r = parts[0]
        for p in parts[1:]: r = [h, r, p]
        return r
    def ports(s, e, name_env=None):
        """expand one Observe/Action entry with its For fields into (kind name map-instance-name, body) tuples"""
        fors = [f for f in e[3:] if hd(f) == 'For']; envs = [{}]
        for f in fors: envs = [dict(x, **{f[1]: el}) for x in envs for el in s.enums[f[2]]]
        out = []
        for env in envs:
            pn = e[1] if isinstance(e[1], str) else '.'.join(s.term(x, env) for x in e[1])
            mp = e[2] if isinstance(e[2], str) else None
            call = e[2] if isinstance(e[2], list) else [e[2]]
            out.append((e[0], pn, call, env))
        return out
    def run(s):
        o = [s.m[0], s.m[1]]; nm = 0; inst = {}
        o.append(fld(s.m, 'Profile')); o.append(['Use', 'BitVectors', 'Families'])
        o.append(['Carrier', 'Bool', ['Of', 'Nat'], ['Enum', '0', '1']])
        for d in s.items:
            h = hd(d)
            if h in ('Profile', 'Use', 'Const') or (h == 'Carrier' and d[1] in s.enums) or (h == 'Map' and (d[1] in s.tables or fld(d, 'Parameters'))): continue
            if h == 'Carrier': o.append([x if x not in s.consts else s.consts[x] for x in d[:2]] + [s.term(x, {}) for x in d[2:]]); continue
            if h == 'Map':
                b = fld(d, 'Body'); o.append(['Map', d[1], fld(d, 'From'), fld(d, 'To'), ['Body', b[1], s.term(b[2], {})]]); continue
            if h == 'Machine':
                ents = []
                for f in d[2:]:
                    if hd(f) in ('Observe', 'Action'): ents += s.ports(f)
                    elif hd(f) == 'ActionsOf': ents += [p for p in s.mach[f[1]][1] if p[0] == 'Action']
                    elif hd(f) == 'Like': ents += s.mach[f[1]][1]
                st = fld(d, 'States'); s.mach[d[1]] = (st, ents)
                fr = [x for x in s.items if hd(x) == 'Carrier' and x[1] == st[1]][0]
                o2 = ['Machine', d[1], st]
                for k, pn, call, env in ents:
                    key = (show(call), show(sorted(env.items())))
                    if key not in inst:
                        mname = 'f%d' % len(inst); inst[key] = mname
                        tgt = 'Word' if k == 'Action' else 'Bool'
                        base = s.maps[call[0]]; to = fld(base, 'To')[1]
                        body = s.term(call + ['$x'], env)
                        o.append(['Map', mname, ['From', st[1]], ['To', to], ['Body', ['$x'], body]])
                    o2.append([k, pn, inst[key]])
                o.append(o2); continue
            o.append(s.term(d, {}))
        return o
def inline_types(o):
    """(To (BitVector k)) / (From (BitVector k)) inline types -> a synthesized carrier BitVector-k (All), declared once"""
    cars = {d[1] for d in o if hd(d) == 'Carrier'}; add = []
    for d in o:
        if hd(d) != 'Map': continue
        for f in d[2:]:
            if hd(f) in ('From', 'To') and isinstance(f[1], list) and hd(f[1]) == 'BitVector':
                nm = 'BitVector-' + f[1][1]
                if nm not in cars: cars.add(nm); add.append(['Carrier', nm, ['Of', f[1]], ['All']])
                f[1] = nm
    i = max(k for k, d in enumerate(o) if hd(d) == 'Carrier') + 1
    return o[:i] + add + o[i:]

def uses_families(form):
    return any(hd(d) == 'Use' and 'Families' in d[1:] for d in form[2:] if isinstance(d, list))

def elaborate(forms, name):
    """forms: parsed top-level forms; returns the elaborated DC.Module form named name."""
    mods = {d[1]: d for d in forms if hd(d) == 'DC.Module'}
    return inline_types(Elab(mods, name).run())

