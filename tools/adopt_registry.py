#!/usr/bin/env python3
"""Build registry/mettadinc_registry.json: the package registry with every bundle patch adopted (Ben's decision 1).

Usage:  python3 tools/adopt_registry.py [--supersede SECTION.HEAD=PATCH ...] [--check]

Inputs (read-only, from the frozen copy docs/e0/):
  base     docs/e0/docs/01_language_specification/validation_package/registry/mettadinc_registry.json
  patches  ex1 ex2 ex3 ex4 mg ls wx, applied in that order (the order the bundles' own ex_check invocations use;
           ls extends ex4's Stream declaration and wx extends ex4's Detection result type, so ex4 precedes them)

Every same-name copy of a patch under docs/e0/docs/ must be byte-identical; otherwise the script stops.
Merging follows the bundles' ex_check.py apply_patch() for the sections it applies (libraries, add_primitives,
declarations, declaration_fields, requests, result_types, request_args, result_fields) and adds the patch keys
ex_check.py applies outside the registry or not at all:
  add_tolerance_bodies -> registry "body_heads_added": {"tolerance-body": [...]} (ex_check extends the checker's BODY_HEADS)
  witness_types        -> merged into registry "witness_types"
  budget_units         -> registry "budget_units" (base units parsed from argument_types.budget, plus the patch's);
                          argument_types.budget's text lists the same units
  notes                -> registry "notes": {name: {"text": ..., "patch": ...}}
  patch, date          -> registry "adopted_patches" (name, file, sha256, description, date)
add_primitives entries already present are not appended twice.

Conflicts stop the script (exit 1) with the diff, unless a --supersede names which patch's definition wins:
  - two patches define the same head (whole entry) differently;
  - two patches set the same field/argument of a head differently;
  - a patch replaces a whole head to which an earlier patch added fields (the additions would be lost);
  - two patches give the same note different texts.
A patch replacing a base registry head, or a base argument/field, is a revision, which adopting the patch means;
those are listed in the report, not refused.

Outputs: registry/mettadinc_registry.json, registry/DIGEST (sha256 of it), registry/SOURCES.md.
--check rebuilds in memory and exits 1 if the committed files differ.
"""
import copy
import difflib
import hashlib
import json
import os
import re
import sys

BT = chr(96)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs", "e0", "docs")
BASE = "01_language_specification/validation_package/registry/mettadinc_registry.json"
PATCHES = [  # (name, canonical copy: the bundle that introduces the patch)
    ("ex1", "03_four_worked_examples/validation_bundles/ex1_belief_memory/ex1_registry_patch.json"),
    ("ex2", "03_four_worked_examples/validation_bundles/ex2_access_policy/ex2_registry_patch.json"),
    ("ex3", "03_four_worked_examples/validation_bundles/ex3_skill_share/ex3_registry_patch.json"),
    ("ex4", "03_four_worked_examples/validation_bundles/ex4_market_maker/ex4_registry_patch.json"),
    ("mg", "04_omega_memory_goals_part1/validation_bundle/mg_registry_patch.json"),
    ("ls", "05_live_memory_part2/validation_bundle/ls_registry_patch.json"),
    ("wx", "06_wmtm_worked_example/validation_bundle/wx_registry_patch.json"),
]
OUT = os.path.join(REPO, "registry", "mettadinc_registry.json")
DIGEST = os.path.join(REPO, "registry", "DIGEST")
SOURCES = os.path.join(REPO, "registry", "SOURCES.md")
WHOLE = [("libraries", "libraries"), ("declarations", "declarations"), ("requests", "requests"),
         ("result_types", "result_types"), ("witness_types", "witness_types")]
FIELDS = [("declaration_fields", "declarations", "fields"), ("request_args", "requests", "args"),
          ("result_fields", "result_types", "fields")]
KNOWN = ({"patch", "date", "add_primitives", "add_tolerance_bodies", "budget_units", "notes"}
         | {s for s, _ in WHOLE} | {s for s, _, _ in FIELDS})


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def js(x):
    return json.dumps(x, sort_keys=True)


def diff(a, b, la, lb):
    A = json.dumps(a, indent=1, sort_keys=True, ensure_ascii=False).splitlines()
    B = json.dumps(b, indent=1, sort_keys=True, ensure_ascii=False).splitlines()
    return "\n".join(difflib.unified_diff(A, B, la, lb, lineterm="", n=1))


def copies():
    """name -> [(relpath, sha256)] for every *_registry_patch.json under docs/e0/docs."""
    out = {}
    for d, _, fs in os.walk(DOCS):
        for f in fs:
            m = re.fullmatch(r"(.+)_registry_patch\.json", f)
            if m:
                p = os.path.join(d, f)
                out.setdefault(m.group(1), []).append((os.path.relpath(p, REPO), sha(p)))
    for v in out.values():
        v.sort()
    return out


def build(supersede):
    base = json.load(open(os.path.join(DOCS, BASE)))
    reg = copy.deepcopy(base)
    patches = [(n, p, json.load(open(os.path.join(DOCS, p)))) for n, p in PATCHES]
    conflicts, revisions, resolved, notes_out = [], [], [], {}
    owner_whole, owner_field, fields_added = {}, {}, {}
    for name, path, pt in patches:
        unknown = set(pt) - KNOWN
        if unknown:
            conflicts.append(f"{name}: patch keys this script does not know how to adopt: {sorted(unknown)}")
        for sec, rsec in WHOLE:
            for head, spec in pt.get(sec, {}).items():
                key = f"{sec}.{head}"
                prev = owner_whole.get(key)
                if prev is not None and js(prev[1]) != js(spec):
                    d = diff(prev[1], spec, f"{prev[0]}:{key}", f"{name}:{key}")
                    if supersede.get(key) == name:
                        resolved.append((key, prev[0], name, d))
                    else:
                        conflicts.append(f"{key} is defined differently by {prev[0]} and {name}:\n{d}")
                elif prev is None and head in base.get(rsec, {}) and js(base[rsec][head]) != js(spec):
                    revisions.append((key, name, diff(base[rsec][head], spec, f"base:{key}", f"{name}:{key}")))
                for who, fld in sorted(fields_added.get((rsec, head), set())):
                    if who != name:
                        conflicts.append(f"{name} replaces {key}, to which {who} added {fld}")
                owner_whole[key] = (name, spec)
                reg.setdefault(rsec, {})[head] = copy.deepcopy(spec)
        for fsec, rsec, sub in FIELDS:
            for head, fields in pt.get(fsec, {}).items():
                if head not in reg.get(rsec, {}):
                    conflicts.append(f"{name}: {fsec} for {head}, which no earlier input defines")
                    continue
                for fld, spec in fields.items():
                    key = f"{rsec}.{head}.{sub}.{fld}"
                    prev = owner_field.get(key)
                    if prev is not None and js(prev[1]) != js(spec):
                        d = diff(prev[1], spec, f"{prev[0]}:{key}", f"{name}:{key}")
                        if supersede.get(key) == name:
                            resolved.append((key, prev[0], name, d))
                        else:
                            conflicts.append(f"{key} is set differently by {prev[0]} and {name}:\n{d}")
                    old = reg[rsec][head].setdefault(sub, {}).get(fld)
                    if prev is None and old is not None and js(old) != js(spec):
                        revisions.append((key, name, diff(old, spec, f"base:{key}", f"{name}:{key}")))
                    owner_field[key] = (name, spec)
                    fields_added.setdefault((rsec, head), set()).add((name, f"{sub}.{fld}"))
                    reg[rsec][head][sub][fld] = copy.deepcopy(spec)
        for lib, prims in pt.get("add_primitives", {}).items():
            have = reg["libraries"][lib].setdefault("primitives", [])
            for p in prims:
                if p not in have:
                    have.append(p)
        for b in pt.get("add_tolerance_bodies", []):
            lst = reg.setdefault("body_heads_added", {}).setdefault("tolerance-body", [])
            if b not in lst:
                lst.append(b)
        if pt.get("budget_units"):
            units = reg.get("budget_units")
            if units is None:
                m = re.search(r"registered work unit: (.*)$", reg["argument_types"]["budget"])
                units = [u.strip() for u in m.group(1).split(",")]
            for u in pt["budget_units"]:
                if u not in units:
                    units.append(u)
            reg["budget_units"] = units
            reg["argument_types"]["budget"] = "(Unit k) with a registered work unit: " + ", ".join(units)
        for k, text in pt.get("notes", {}).items():
            if k in notes_out and notes_out[k]["text"] != text:
                conflicts.append(f"note {k}: {notes_out[k]['patch']} and {name} differ")
            notes_out[k] = {"text": text, "patch": name}
        reg.setdefault("adopted_patches", []).append(
            {"name": name, "file": "docs/e0/docs/" + path, "sha256": sha(os.path.join(DOCS, path)),
             "patch": pt.get("patch"), "date": pt.get("date")})
    if notes_out:
        reg["notes"] = notes_out
    reg["registry"] = base["registry"] + ", with the bundle patches ex1, ex2, ex3, ex4, mg, ls and wx adopted"
    reg["date"] = "2026-11-05"
    return base, reg, conflicts, revisions, resolved


def code(s):
    return BT + s + BT


# What adopting each input changes in the fixtures, the manifest and the checker (MILESTONES.md, entry checklist
# item 3: a registry change updates the registry, the fixtures, the manifest and the checker together).
# Evidence: validation/check_fixtures.py passes on the frozen package fixtures and manifest unchanged (21 files,
# 32 modules, 357 declarations, 125 runs; 123 claims, 45 Supported / 78 Unsupported), and tools/check_bundles.py
# gives 0 diagnostics for every bundle with no patch.  The checker column lists the ex_check.py install() code
# that moved into validation/check_fixtures.py because the input's forms need it.
COORDINATED = [
    ("base registry", "none", "none",
     "the working copy validation/check_fixtures.py reads registry/mettadinc_registry.json (MDINC_REGISTRY overrides) "
     "and the package data from the frozen docs/e0/ copy"),
    ("ex1", "none", "none",
     "declarations that declare another kind (EncodingFamily, ParallelMachine, ProductRepresentation); argument type "
     "stable-or-horizon (Refine Until); the tolerance body Meet (registry body_heads_added)"),
    ("ex2", "none", "none",
     "library binders (Families: Exists, ForAll); For and Values options on Machine/MethodSystem entries; compound "
     "family labels such as (assign $u $r); instances of parameterized maps. budget_units (Unrollings) is recorded; "
     "the checker does not check budget units (it did not before either)"),
    ("ex3", "none", "none", "none (registry data only)"),
    ("ex4", "none", "none",
     "declares (DecisionProcess, Monitor, Stream); library binders (Laws: Image). The four base requests ex4 revises "
     "keep first_release [], so release-1 statuses are unchanged"),
    ("mg", "none", "none",
     "declares (Consumer). witness_types RecordWitness is merged; the checker reads witness types only for a "
     "claim's until entry, and no package claim names it"),
    ("ls", "none", "none", "declares (Statistic, Store, Keyed)"),
    ("wx", "none", "none", "none beyond ex4's (Detect's new arguments are ordinary registry arguments)"),
]


def sources_md(base_sha, reg_sha, cps, revisions, resolved):
    L = ["# Sources of registry/mettadinc_registry.json", "",
         "Generated by " + code("tools/adopt_registry.py") + "; do not edit by hand, rerun it. Ben's decision 1: adopt the",
         "bundles' proposed registry patches before M0. All inputs are read from the frozen copy " + code("docs/e0/") + ",",
         "which is not modified.", "",
         "**Registry digest (sha256 of registry/mettadinc_registry.json): " + code(reg_sha) + "** (also in "
         + code("registry/DIGEST") + ").", "",
         "## Inputs", "", "| Input | File | sha256 |", "|---|---|---|",
         f"| base registry | docs/e0/docs/{BASE} | {code(base_sha)} |"]
    names = [x for x, _ in PATCHES]
    for n, p in PATCHES:
        L.append(f"| {n} patch (applied {names.index(n) + 1} of {len(PATCHES)}) | docs/e0/docs/{p} | "
                 f"{code(sha(os.path.join(DOCS, p)))} |")
    L += ["", "## Coordinated change (MILESTONES.md, entry checklist item 3)", "",
          "| Input | Fixtures | Manifest | Checker |", "|---|---|---|---|"]
    for row in COORDINATED:
        L.append("| " + " | ".join(row) + " |")
    L += ["", "## Same-name copies of each patch", "",
          "| Patch | Copies | Byte-identical | Files |", "|---|---|---|---|"]
    for n, _ in PATCHES:
        c = cps.get(n, [])
        same = len({h for _, h in c}) == 1
        L.append(f"| {n} | {len(c)} | {'yes' if same else '**NO**'} | " + "<br>".join(f for f, _ in c) + " |")
    L += ["", "## Resolutions of patch-vs-patch conflicts", ""]
    if resolved:
        for key, a, b, d in resolved:
            L += [f"- {code(key)}: defined by {a} and by {b}; **{b} supersedes {a}** "
                  f"({code('--supersede ' + key + '=' + b)}). Diff:", "", BT * 3 + "diff", d, BT * 3, ""]
    else:
        L.append("None.")
    L += ["", "## Revisions of base registry entries by patches", "",
          "These replace a base head or a base argument; adopting the patch means adopting the revision.", ""]
    for key, n, d in revisions:
        L += [f"- {code(key)} by {n}:", "", BT * 3 + "diff", d, BT * 3, ""]
    return "\n".join(L).rstrip() + "\n"


def main(argv):
    supersede, check = {}, False
    i = 0
    while i < len(argv):
        if argv[i] == "--supersede":
            k, v = argv[i + 1].split("=", 1)
            supersede[k] = v
            i += 2
        elif argv[i] == "--check":
            check = True
            i += 1
        else:
            sys.exit(f"unknown argument {argv[i]}")
    cps = copies()
    bad = False
    for n, _ in PATCHES:
        c = cps.get(n, [])
        hs = sorted({h for _, h in c})
        print(f"{n}: {len(c)} copies, {'byte-identical' if len(hs) == 1 else 'DIFFERENT'} ({', '.join(h[:12] for h in hs)})")
        if len(hs) != 1:
            bad = True
            for f, h in c[1:]:
                if h != c[0][1]:
                    a = open(os.path.join(REPO, c[0][0])).read().splitlines()
                    b = open(os.path.join(REPO, f)).read().splitlines()
                    print("\n".join(difflib.unified_diff(a, b, c[0][0], f, lineterm="")))
    extra = sorted(set(cps) - {n for n, _ in PATCHES})
    if extra:
        print(f"patch files not in the adoption list: {extra}")
        bad = True
    if bad:
        print("STOP: same-name copies differ (or unlisted patches); nothing written")
        return 1
    base, reg, conflicts, revisions, resolved = build(supersede)
    for key, a, b, _ in resolved:
        print(f"resolved: {key}: {b} supersedes {a}")
    for key, n, _ in revisions:
        print(f"revision of base: {key} by {n}")
    if conflicts:
        print(f"STOP: {len(conflicts)} conflict(s); nothing written")
        for c in conflicts:
            print(c)
        return 1
    text = json.dumps(reg, indent=1, ensure_ascii=False) + "\n"
    reg_sha = hashlib.sha256(text.encode()).hexdigest()
    src = sources_md(sha(os.path.join(DOCS, BASE)), reg_sha, cps, revisions, resolved)
    if check:
        same = (os.path.exists(OUT) and open(OUT).read() == text and open(DIGEST).read().split()[0] == reg_sha
                and open(SOURCES).read() == src)
        print(("up to date: " if same else "OUT OF DATE: ") + reg_sha)
        return 0 if same else 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(text)
    open(DIGEST, "w").write(f"{reg_sha}  mettadinc_registry.json\n")
    open(SOURCES, "w").write(src)
    print(f"wrote registry/mettadinc_registry.json sha256 {reg_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
