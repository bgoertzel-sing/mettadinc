#!/usr/bin/env python3
"""M1 acceptance 3: admission agrees with check_fixtures.py on a mutation set.

Each mutation is one textual edit of one package fixture (applied to a copy
under build/mutations/).  For each, validation/check_fixtures.py runs on the
mutated package (MDINC_PACKAGE_DATA) and `dcalc --admit` runs on all of its
fixture files.  A row passes when both reject and both diagnostics name the
expected class (so they do not agree only because both skip a construct); the
unmutated package must be accepted by both.  Prints a table; exit 1 on any
disagreement.
"""
import os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PKG = os.path.join(ROOT, "docs/e0/docs/01_language_specification/validation_package")
CHECKER = os.path.join(ROOT, "validation/check_fixtures.py")
DCALC = os.path.join(ROOT, "build/dcalc/dcalc")
WORK = os.path.join(ROOT, "build/mutations")
A, E, C = "affine_contracts.metta", "eight_state.metta", "certificate_limits.metta"

# (id, verdict class, file, old text, new text, substring expected in both diagnostics)
MUTATIONS = [
    ("undeclared-name", "InvalidInput", A, "(Ideal f)  (Actual f-hat)", "(Ideal nosuch)  (Actual f-hat)", "undeclared name nosuch"),
    ("unknown-argument", "InvalidInput", A, "(CheckImplementation First  (Grade 2 (Rat 1 10)))",
     "(CheckImplementation First  (Grade 2 (Rat 1 10)) (Bogus 1))", "unknown argument (Bogus 1)"),
    ("wrong-reference-kind", "InvalidInput", E, "(Representation KeepA  (Of Concrete)", "(Representation KeepA  (Of Bit)", "Bit is a Carrier"),
    ("missing-required-argument", "InvalidInput", A, "(CheckImplementation First  (Grade 2 (Rat 1 10)))",
     "(CheckImplementation First)", "missing required argument Grade"),
    ("out-of-range-rational", "InvalidInput", C, "(Within (Rat 99 100))", "(Within (Rat 101 100))", "expected a rational in [0,1]"),
    ("unbound-variable", "InvalidInput", A, "(Body ($x) (Mul 2 $x)))", "(Body ($x) (Mul 2 $z)))", "unbound variable $z"),
    ("unknown-result-field", "InvalidInput", A, "(Output FirstChecked Value)", "(Output FirstChecked Nonsense)", "has no field Nonsense"),
    ("unimported-library", "InvalidInput", A, "  (Use Contracts)\n", "", "not imported by AffineContracts"),
    ("duplicate-name", "rejected", A, "(Map g     (From Y)", "(Map f     (From Y)", "duplicate declaration f"),
    ("duplicate-keyed-field", "rejected", A, "(Implementation First   (Ideal f)", "(Implementation First   (Ideal f) (Ideal f)", "duplicate field Ideal"),
    ("duplicate-keyed-argument", "rejected", A, "(CheckImplementation First  (Grade 2 (Rat 1 10)))",
     "(CheckImplementation First  (Grade 2 (Rat 1 10)) (Grade 2 (Rat 1 10)))", "duplicate argument Grade"),
    ("nonlinear-pattern", "rejected", E, "(Cases ((Tuple $a $b $c) $a)))", "(Cases ((Tuple $a $a $c) $a)))", "nonlinear pattern"),
    ("nonlinear-body-binders", "rejected", A, "(Body ($x) (Mul 2 $x)))", "(Body ($x $x) (Mul 2 $x)))", "nonlinear Body binders"),
    ("map-call-cycle", "rejected", A, "(Map f     (From X) (To Rational) (Body ($x) (Mul 2 $x)))",
     "(Map f     (From X) (To Rational) (Body ($x) (gf $x)))", "map-call cycle"),
    ("map-self-call", "rejected", A, "(Body ($x) (Mul 2 $x)))", "(Body ($x) (f $x)))", "map-call cycle f -> f"),
    ("derivation-cycle", "rejected", A, "(ThenContracts (Output FirstChecked Value)", "(ThenContracts (Output Composite Value)", "derivation cycle"),
    ("enum-element-wrong-constant", "rejected", A, "(Carrier X (Of Rational) (Enum 0 1))", "(Carrier X (Of Rational) (Enum 0 foo))", "Enum element foo"),
    ("enum-element-nat-negative", "rejected", E, "(Carrier Bit   (Of Nat) (Enum 0 1))", "(Carrier Bit   (Of Nat) (Enum 0 -1))", "Enum element -1"),
]


def run(pkg):
    env = dict(os.environ, MDINC_PACKAGE_DATA=pkg)
    ck = subprocess.run([sys.executable, CHECKER, "--quiet"], env=env, capture_output=True, text=True, timeout=120)
    fx = sorted(os.path.join(pkg, "fixtures", f) for f in os.listdir(os.path.join(pkg, "fixtures")) if f.endswith(".metta"))
    dc = subprocess.run([DCALC, "--admit"] + fx, capture_output=True, text=True, timeout=60)
    return ck.returncode, ck.stdout + ck.stderr, dc.returncode, dc.stdout + dc.stderr


def verdict(rc): return "accept" if rc == 0 else ("reject" if rc == 1 else "error rc=%d" % rc)


def main():
    shutil.rmtree(WORK, True); os.makedirs(WORK)
    rows, bad = [], 0
    crc, cout, drc, dout = run(PKG)
    ok = crc == 0 and drc == 0
    bad += not ok
    rows.append(("(unmutated package)", "admitted", "-", verdict(crc), verdict(drc), "PASS" if ok else "FAIL"))
    for mid, cls, f, old, new, want in MUTATIONS:
        d = os.path.join(WORK, mid); shutil.copytree(PKG, d)
        p = os.path.join(d, "fixtures", f); s = open(p).read()
        if s.count(old) != 1:
            rows.append((mid, cls, f, "-", "-", "FAIL (edit site not unique)")); bad += 1; continue
        open(p, "w").write(s.replace(old, new))
        crc, cout, drc, dout = run(d)
        open(d + ".checker.txt", "w").write(cout); open(d + ".dcalc.txt", "w").write(dout)
        ok = crc == 1 and drc == 1 and want in cout and want in dout
        why = "" if ok else " (%s)" % ("verdicts differ" if crc != drc else "both accept" if crc == 0 else "diagnostic lacks '%s'" % want)
        rows.append((mid, cls, f, verdict(crc), verdict(drc), ("PASS" if ok else "FAIL") + why)); bad += not ok
    print("| mutation | class | fixture | check_fixtures.py | dcalc --admit | result |")
    print("|---|---|---|---|---|---|")
    for r in rows: print("| " + " | ".join(r) + " |")
    print("mutations: %d rows, %s" % (len(rows), "PASS" if not bad else "FAIL (%d)" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
