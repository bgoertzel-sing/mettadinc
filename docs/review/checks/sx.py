# Own minimal s-expression reader for dcalc envelopes (independent of repo code).
import re
TOK = re.compile(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+')
def parse_all(s):
    toks = TOK.findall(s); i = 0; out = []
    def rd():
        nonlocal i
        t = toks[i]; i += 1
        if t == '(':
            l = []
            while toks[i] != ')': l.append(rd())
            i += 1; return l
        return t
    while i < len(toks): out.append(rd())
    return out
def find(x, head):
    """first sublist whose head == head (depth-first)"""
    if isinstance(x, list):
        if x and x[0] == head: return x
        for y in x:
            r = find(y, head)
            if r is not None: return r
    return None
def findall(x, head, acc=None):
    acc = [] if acc is None else acc
    if isinstance(x, list):
        if x and x[0] == head: acc.append(x)
        for y in x: findall(y, head, acc)
    return acc
def envelopes(path, module):
    res = []
    for line in open(path):
        if line.startswith(module + ' ') and ' => ' in line:
            req, env = line.split(' => ', 1)
            res.append((req[len(module)+1:].strip(), parse_all(env)[0]))
    return res
