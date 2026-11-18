#!/usr/bin/env python3
"""Seeded generator for affine implementation contracts (spec 9.3, Prop 9.1).
Ideal f(x) = a x + b, actual f-hat = (a+da) x + (b+db) on a random rational audit set X; second stage g, g-hat on
Y = f(X) u f-hat(X). Requested grades sit exactly at, above or below the tight eta (boundary cases), and the
OneMinusAbsoluteDifference distance clips at 1 whenever values are more than 1 apart (hard path)."""
import random
from fractions import Fraction as F
import gen, oracle

COEF = (F(0), F(1, 2), F(1), F(3, 2), F(2), F(3))
PERT = (F(0), F(1, 10), F(1, 5), F(1, 3), F(1, 2), F(3, 2))


def body(a, b):
    return '(Body ($x) (Add (Mul %s $x) %s))' % (gen.rat(a), gen.rat(b))


def rand_impl(rng):
    a, b = rng.choice(COEF), rng.choice(COEF)
    return (a, b), (a + rng.choice(PERT), b + rng.choice(PERT))


def rand_grade(rng, ideal, actual, audit):
    L = rng.choice((F(0), F(1, 2), F(1), F(2), F(3)))
    eta = oracle.tight_eta(oracle.affine(ideal), oracle.affine(actual), audit, L)
    mode = rng.choice(('tight', 'tight', 'above', 'below'))
    if mode == 'above':
        eta += rng.choice(PERT[1:])
    elif mode == 'below' and eta > 0:
        eta = max(F(0), eta - rng.choice(PERT[1:]))
    return L, eta


def rand_case(rng, name):
    X = sorted(set(F(rng.randint(0, 6), rng.choice((1, 2, 3))) for _ in range(rng.randint(1, 4))))
    (fi, fa), (gi, ga) = rand_impl(rng), rand_impl(rng)
    f, fh = oracle.affine(fi), oracle.affine(fa)
    Y = sorted({f(x) for x in X} | {fh(x) for x in X})
    gr1, gr2 = rand_grade(rng, fi, fa, X), rand_grade(rng, gi, ga, Y)
    T = ['(DC.Module %s' % name, '  (Profile Graded)', '  (Use Contracts)',
         '  (Carrier X (Of Rational) (Enum %s))' % ' '.join(gen.rat(x) for x in X),
         '  (Carrier Y (Of Rational) (Enum %s))' % ' '.join(gen.rat(y) for y in Y),
         '  (Map f (From X) (To Rational) %s)' % body(*fi), '  (Map f-hat (From X) (To Rational) %s)' % body(*fa),
         '  (Map g (From Y) (To Rational) %s)' % body(*gi), '  (Map g-hat (From Y) (To Rational) %s)' % body(*ga),
         '  (Tolerance Gap (On Rational) (OneMinusAbsoluteDifference))',
         '  (Implementation First (Ideal f) (Actual f-hat) (Audit X) (InputDistance Gap) (OutputDistance Gap))',
         '  (Implementation Second (Ideal g) (Actual g-hat) (Audit Y) (InputDistance Gap) (OutputDistance Gap))',
         '  (Derive C1 (CheckImplementation First (Grade %s %s)))' % (gen.rat(gr1[0]), gen.rat(gr1[1])),
         '  (Derive C2 (CheckImplementation Second (Grade %s %s)))' % (gen.rat(gr2[0]), gen.rat(gr2[1])),
         '  (Derive C12 (ThenContracts (Output C1 Value) (Output C2 Value))))']
    txt = '\n'.join(T) + '\n' + ''.join('!(dc.run %s %s)\n' % (name, r) for r in ('C1', 'C2', 'C12'))
    return {'X': X, 'Y': Y, 'f': fi, 'fh': fa, 'g': gi, 'gh': ga, 'gr1': gr1, 'gr2': gr2}, txt
