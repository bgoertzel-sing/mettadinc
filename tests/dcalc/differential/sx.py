"""Minimal s-expression reader for dcalc answer lines (text only; no repo code)."""
from fractions import Fraction as F


def tokens(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c in '()':
            yield c; i += 1
        elif c == '"':
            j = i + 1
            while j < n and s[j] != '"':
                j += 2 if s[j] == '\\' else 1
            yield s[i:j + 1]; i = j + 1
        else:
            j = i
            while j < n and not s[j].isspace() and s[j] not in '()':
                j += 1
            yield s[i:j]; i = j


def parse(s):
    st = [[]]
    for t in tokens(s):
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop(); st[-1].append(x)
        else:
            st[-1].append(t)
    return st[0]


def find(x, head):
    """First sub-list whose head is `head` (depth-first)."""
    if isinstance(x, list):
        if x and x[0] == head:
            return x
        for y in x:
            r = find(y, head)
            if r is not None:
                return r
    return None


def num(x):
    """'3', '3/5', '-1' or ['Rat', a, b] -> Fraction."""
    if isinstance(x, list):
        assert x[0] == 'Rat', x
        return F(int(x[1]), int(x[2]))
    return F(x)


def answers(text):
    """dcalc stdout -> list of (request_text, result_sexp)."""
    out = []
    for line in text.splitlines():
        if ' => (Result ' not in line:
            continue
        req, res = line.split(' => ', 1)
        out.append((req.strip(), parse(res)[0]))
    return out


def status(res):
    s = find(res, 'Status')
    return s[1] if s else None
