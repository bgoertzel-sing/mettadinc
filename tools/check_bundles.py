#!/usr/bin/env python3
"""Check every bundle's MeTTaDinC files against the adopted registry alone, with no patch.

Usage:  python3 tools/check_bundles.py [BUNDLE ...]       (default: ex1 ex2 ex3 ex4 mg ls wx)

For each bundle this imports the bundle's own ex_check.py (from the frozen copy docs/e0/, unmodified) with
MDINC_PACKAGE pointing at validation/, so its "import check_fixtures" loads the repository's working checker,
which reads registry/mettadinc_registry.json.  It then calls ex_check.check_files() on the bundle's files without
install(): no patch is applied and no checker function is replaced, so this is ex_check.py's own check against
the adopted registry alone.  (Running "ex_check.py PATCH... -- FILES" cannot show this: its second pass,
uninstall(), hard-codes a diagnostic for every compound family label, whatever the registry says.)

Each bundle runs in its own process.  Exit 0 if every bundle has zero diagnostics.
--registry PATH checks against another registry instead (a canary: the unpatched base registry must give
diagnostics).  --request HEAD also checks, one by one, every run request and every Derive declaration whose request
has that head, and prints each with "admitted" or its diagnostics (e.g. --request Detect).
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(REPO, "docs", "e0", "docs")
BUNDLES = {  # name -> (bundle directory, files), as in the bundles' READMEs and docs/e0/tools/run_oracles.sh
    "ex1": ("03_four_worked_examples/validation_bundles/ex1_belief_memory", ["belief_memory.metta"]),
    "ex2": ("03_four_worked_examples/validation_bundles/ex2_access_policy", ["access_policy.metta"]),
    "ex3": ("03_four_worked_examples/validation_bundles/ex3_skill_share", ["skill_share.metta"]),
    "ex4": ("03_four_worked_examples/validation_bundles/ex4_market_maker", ["market_maker.metta"]),
    "mg": ("04_omega_memory_goals_part1/validation_bundle", ["memory_goals.metta"]),
    "ls": ("05_live_memory_part2/validation_bundle", ["memory_goals.metta", "live_memory.metta"]),
    "wx": ("06_wmtm_worked_example/validation_bundle", ["memory_goals.metta", "live_memory.metta", "wmtm_example.metta"]),
}

CHILD = r'''
import importlib.util, os, sys
bdir, files = sys.argv[1], sys.argv[2:]
spec = importlib.util.spec_from_file_location("ex_check", os.path.join(bdir, "ex_check.py"))
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)
assert os.path.realpath(os.path.dirname(ex.cf.__file__)) == os.path.realpath(os.environ["MDINC_PACKAGE"]), ex.cf.__file__
print("checker:", os.path.relpath(ex.cf.__file__), "registry:", os.path.relpath(ex.cf.REGISTRY_PATH))
nmod, ndecl, nruns, errors = ex.check_files([os.path.join(bdir, f) for f in files])
print(f"{len(files)} file(s), {nmod} modules, {ndecl} declarations, {nruns} run requests")
print(f"{len(errors)} diagnostic(s) against {os.path.relpath(ex.cf.REGISTRY_PATH)}, no patch")
for e in errors:
    print("  " + e)
H = os.environ.get("MDINC_SHOW_REQUEST")
bad = 0
if H:
    cf = ex.cf
    modules, parsed = {}, {}
    for f in files:
        forms = cf.read_forms(open(os.path.join(bdir, f)).read(), f)
        parsed[f] = forms
        for kind, form in forms:
            if kind == "form":
                modules[form[1]] = cf.Module(form[1], form, f)
    for m in modules.values():
        cf.scan_module(m)
    for m in modules.values():
        cf.resolve_imports(m, modules)
    n = 0
    for f, forms in parsed.items():
        for kind, form in forms:
            if kind == "run" and isinstance(form, list) and len(form) == 3 and isinstance(form[2], list) \
                    and form[2] and form[2][0] == H:
                cf.ERRORS.clear()
                cf.check_run(form, modules, f)
                n += 1
                bad += bool(cf.ERRORS)
                print(f"  {H} run {f}: !(dc.run {form[1]} {cf.show(form[2])}): "
                      + ("admitted" if not cf.ERRORS else "; ".join(cf.ERRORS)))
    for m in modules.values():
        for name, (kind, item) in m.decls.items():
            if kind == "Derive" and item in m.form[2:] and len(item) > 2 and isinstance(item[2], list) \
                    and item[2] and item[2][0] == H:
                cf.ERRORS.clear()
                cf.check_declaration(m, name, kind, item)
                n += 1
                bad += bool(cf.ERRORS)
                print(f"  {H} derivation {m.fname}: {m.name}.{name} = {cf.show(item[2])}: "
                      + ("admitted" if not cf.ERRORS else "; ".join(cf.ERRORS)))
    print(f"{n} {H} request(s), {n - bad} admitted, {bad} with diagnostics")
sys.exit(1 if errors or bad else 0)
'''


def main(argv):
    # no __pycache__ may be written into the frozen docs/e0/
    env = dict(os.environ, MDINC_PACKAGE=os.path.join(REPO, "validation"), PYTHONDONTWRITEBYTECODE="1")
    env.pop("MDINC_REGISTRY", None)
    while argv[:1] in (["--registry"], ["--request"]):
        if argv[0] == "--registry":
            env["MDINC_REGISTRY"] = os.path.abspath(argv[1])
        else:
            env["MDINC_SHOW_REQUEST"] = argv[1]
        argv = argv[2:]
    names = argv or list(BUNDLES)
    status = 0
    for n in names:
        bdir, files = BUNDLES[n]
        p = subprocess.run([sys.executable, "-c", CHILD, os.path.join(D, bdir)] + files, env=env,
                           capture_output=True, text=True)
        out = (p.stdout + p.stderr).rstrip()
        print(f"== {n} ({bdir}) exit {p.returncode}")
        print(out)
        status |= p.returncode != 0
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
