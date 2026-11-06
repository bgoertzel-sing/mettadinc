#!/usr/bin/env python3
"""Static check of example module files against the registry plus proposed patches.

Usage: python3 ex_check.py PATCH.json [PATCH.json ...] -- FILE.metta [FILE.metta ...]
       python3 ex_check.py PATCH.json FILE.metta [FILE.metta ...]

The validation package directory (it holds check_fixtures.py) is found through MDINC_PACKAGE,
next to this file, or two levels up.  The package checker does the parsing, name resolution
and argument checking; the patches are applied in memory.  Afterwards the same files are
checked against the unpatched registry, and every diagnostic of that second pass is listed,
so the forms that depend on proposed additions are explicit.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = (os.environ.get("MDINC_PACKAGE", ""), os.path.join(HERE, "package"),
              os.path.join(HERE, "..", "package"), os.path.join(HERE, "..", "..", "package"))
PKG = next((d for d in CANDIDATES if d and os.path.exists(os.path.join(d, "check_fixtures.py"))), None)
if PKG is None:
    sys.exit("set MDINC_PACKAGE to the directory of the validation package (it holds check_fixtures.py)")
sys.path.insert(0, PKG)
import check_fixtures as cf  # noqa: E402

BASE = copy.deepcopy(cf.REG)
ORIG = {name: getattr(cf, name) for name in ("kind_ok", "check_value", "bound_vars", "check_machine_items",
                                             "collect_names")}
BASE_TOL = set(cf.BODY_HEADS["tolerance-body"])


def apply_patch(reg, patch):
    reg = copy.deepcopy(reg)
    for lib, spec in patch.get("libraries", {}).items():
        reg["libraries"][lib] = spec
    for lib, prims in patch.get("add_primitives", {}).items():
        reg["libraries"][lib].setdefault("primitives", [])
        reg["libraries"][lib]["primitives"] += prims
    for name, spec in patch.get("declarations", {}).items():
        reg["declarations"][name] = spec
    for decl, fields in patch.get("declaration_fields", {}).items():
        reg["declarations"][decl]["fields"].update(fields)
    for req, spec in patch.get("requests", {}).items():
        reg["requests"][req] = spec
    for rt, spec in patch.get("result_types", {}).items():
        reg["result_types"][rt] = spec
    for req, args in patch.get("request_args", {}).items():
        reg["requests"][req]["args"].update(args)
    for rt, fields in patch.get("result_fields", {}).items():
        reg["result_types"][rt]["fields"].update(fields)
    return reg


def install(patches):
    reg = BASE
    for p in patches:
        reg = apply_patch(reg, p)
    cf.REG = reg
    cf.BODY_HEADS["tolerance-body"] = BASE_TOL | {h for p in patches for h in p.get("add_tolerance_bodies", [])}
    binders = {b for p in patches for lib in p.get("libraries", {}).values() for b in lib.get("binders", [])}

    def kind_ok(kinds, decl_kind=None, field_t=None):
        if decl_kind in cf.REG["declarations"]:
            declared = cf.REG["declarations"][decl_kind].get("declares", decl_kind)
            if ORIG["kind_ok"](kinds, decl_kind=declared, field_t=field_t):
                return True
        return ORIG["kind_ok"](kinds, decl_kind=decl_kind, field_t=field_t)

    def check_value(val, typ, ctx, what):
        if typ == "stable-or-horizon":
            if val == "Stable":
                return
            return ORIG["check_value"](val, "horizon", ctx, what)
        return ORIG["check_value"](val, typ, ctx, what)

    def bound_vars(x, out):
        if (isinstance(x, list) and x and isinstance(x[0], str) and x[0] in binders and len(x) > 1
                and isinstance(x[1], str)):
            out.add(x[1])
        ORIG["bound_vars"](x, out)

    def collect_names(mod, head, item):
        # family entries have compound labels such as (assign $u $r): record the label head
        if head in ("Machine", "MethodSystem"):
            for x in item[2:]:
                if (isinstance(x, list) and x and x[0] in ("Observe", "Action", "Merge") and len(x) > 1
                        and isinstance(x[1], list) and x[1] and isinstance(x[1][0], str)):
                    mod.labels.add(x[1][0])
            item = [y if not (isinstance(y, list) and y and y[0] in ("Observe", "Action", "Merge")
                              and len(y) > 1 and isinstance(y[1], list)) else [y[0], "_family"] + y[2:]
                    for y in item]
        ORIG["collect_names"](mod, head, item)

    def map_instance_ok(mp, ctx):
        if isinstance(mp, str):
            cf.check_ref(mp, "Map|TransitionKernel", ctx)
            return
        if isinstance(mp, list) and mp and isinstance(mp[0], str):
            d = ctx.mod.decls.get(mp[0])
            if d and d[0] == "Map" and any(isinstance(f, list) and f and f[0] == "Parameters" for f in d[1]):
                for a in mp[1:]:
                    cf.check_expr(a, ctx)
                return
        cf.err(ctx.where, f"expected a map or an instance of a parameterized map, found {cf.show(mp)[:60]}")

    def check_machine_items(item, ctx):
        for x in item[2:]:
            if not (isinstance(x, list) and x) or x[0] not in ("Observe", "Action", "Merge", "Available"):
                continue
            rest = x[1:]
            fors = [y for y in rest if isinstance(y, list) and y and y[0] == "For"]
            opts = [y for y in rest if isinstance(y, list) and y and y[0] == "Values"]
            core = [y for y in rest if not any(y is z for z in fors + opts)]
            if x[0] == "Available":
                for y in core:
                    cf.check_expr(y, ctx)
                continue
            if len(core) != 2:
                cf.err(ctx.where, f"{x[0]} needs a label and a map: {cf.show(x)[:60]}")
                continue
            label, mp = core
            for f in fors:
                if not (len(f) == 3 and isinstance(f[1], str) and f[1].startswith("$")):
                    cf.err(ctx.where, f"For needs a variable and a carrier: {cf.show(f)}")
                elif ctx.mod.decls.get(f[2], (None,))[0] != "Carrier":
                    cf.err(ctx.where, f"For ranges over an undeclared carrier {f[2]}")
            if fors and not binders:
                cf.err(ctx.where, "For on a machine entry needs the Families library")
            if isinstance(label, list):
                for a in label[1:]:
                    cf.check_expr(a, ctx)
            map_instance_ok(mp, ctx)
            for o in opts:
                cf.check_ref(o[1], "Tolerance", ctx)

    cf.kind_ok, cf.check_value, cf.bound_vars = kind_ok, check_value, bound_vars
    cf.check_machine_items, cf.collect_names = check_machine_items, collect_names


def uninstall():
    cf.REG = BASE
    cf.BODY_HEADS["tolerance-body"] = set(BASE_TOL)
    for name, fn in ORIG.items():
        setattr(cf, name, fn)

    def collect_names(mod, head, item):
        # the current registry has no compound labels: report them instead of failing
        if head in ("Machine", "MethodSystem"):
            for x in item[2:]:
                if (isinstance(x, list) and x and x[0] in ("Observe", "Action", "Merge") and len(x) > 1
                        and isinstance(x[1], list)):
                    cf.err(mod.fname, f"{mod.name}: compound label {cf.show(x[1])} needs the Families library")
            item = [y if not (isinstance(y, list) and y and y[0] in ("Observe", "Action", "Merge")
                              and len(y) > 1 and isinstance(y[1], list)) else [y[0], "_family"] + y[2:]
                    for y in item]
        ORIG["collect_names"](mod, head, item)
    cf.collect_names = collect_names


def check_files(files):
    cf.ERRORS.clear()
    modules, parsed = {}, {}
    for f in files:
        forms = cf.read_forms(open(f).read(), os.path.basename(f))
        parsed[f] = forms
        for kind, form in forms:
            if kind == "form":
                modules[form[1]] = cf.Module(form[1], form, os.path.basename(f))
    for m in modules.values():
        cf.scan_module(m)
    for m in modules.values():
        cf.resolve_imports(m, modules)
    ndecl = 0
    for m in modules.values():
        for name, (kind, item) in list(m.decls.items()):
            if item in m.form[2:]:
                try:
                    cf.check_declaration(m, name, kind, item)
                except KeyError as e:
                    cf.err(f"{m.name}.{name}", f"unregistered declaration head {e}")
                ndecl += 1
    nruns = 0
    for f, forms in parsed.items():
        for kind, form in forms:
            if kind == "run":
                cf.check_run(form, modules, os.path.basename(f))
                nruns += 1
    return len(modules), ndecl, nruns, list(cf.ERRORS)


def main():
    args = sys.argv[1:]
    if "--" in args:
        k = args.index("--")
        patch_files, files = args[:k], args[k + 1:]
    else:
        patch_files, files = args[:1], args[1:]
    patches = [json.load(open(p)) for p in patch_files]
    install(patches)
    nmod, ndecl, nruns, patched_errors = check_files(files)
    uninstall()
    _, _, _, base_errors = check_files(files)
    base_errors = sorted(set(base_errors))
    print(f"{len(files)} file(s), {nmod} modules, {ndecl} declarations, {nruns} run requests")
    if patched_errors:
        print(f"{len(patched_errors)} error(s) against registry + patch:")
        for e in patched_errors:
            print("  " + e)
        return 1
    print("All forms conform to the registry with the proposed patch.")
    print(f"{len(base_errors)} diagnostic(s) against the current registry (forms that need the patch):")
    for e in base_errors:
        print("  " + e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
