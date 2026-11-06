#!/usr/bin/env python3
"""Registry and manifest checker for the MeTTaDinC validation package.

It parses every fixture module, checks each declaration and request against
registry/mettadinc_registry.json (heads, fields, argument names and kinds,
required arguments, defaults, profiles), resolves every name, and checks that
every claim in manifest.json names an existing fixture form and agrees with the
oracle results in oracle/mettadinc_oracle_results.json.  It also derives, for
each claim, whether the first release must answer it or return Unsupported, and
checks that a claim's optional "until" entry names a registered witness type or
certificate kind and registered statuses.

It is a static checker.  It does not evaluate MeTTaDinC and it does not replace
the replay checker of an implementation.

Usage:  python3 check_fixtures.py [--quiet]

MeTTaDinC repository working copy (hive task t-2026-11-05-mettadinc-m0-prep).  The original is
docs/e0/docs/01_language_specification/validation_package/check_fixtures.py, which stays frozen.  Changes,
all marked "M0-prep":
  - the registry is registry/mettadinc_registry.json at the repository root (MDINC_REGISTRY overrides);
  - fixtures, manifest.json and the oracle results are read from the frozen package (MDINC_PACKAGE_DATA
    overrides), because adopting the patches changes none of them;
  - the checker extensions that the bundles' ex_check.py installed next to their patches are native here,
    driven by the adopted registry: declarations that "declares" another kind, the stable-or-horizon
    argument type, binders of libraries (For), compound family labels on Machine/MethodSystem entries,
    Observe/Action/Merge/Available items with For and Values options and instances of parameterized maps,
    and the extra body heads in "body_heads_added" (the tolerance body Meet).
They are the same code as ex_check.py's install(), so bundle files check the same way as with their patches.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
# M0-prep: one registry for the repository; the package data stays in the frozen copy.
REGISTRY_PATH = os.environ.get("MDINC_REGISTRY") or os.path.join(REPO, "registry", "mettadinc_registry.json")
ROOT = os.environ.get("MDINC_PACKAGE_DATA") or os.path.join(
    REPO, "docs", "e0", "docs", "01_language_specification", "validation_package")
REG = json.load(open(REGISTRY_PATH))
FIXDIR = os.path.join(ROOT, "fixtures")

ERRORS = []


def err(where, msg):
    ERRORS.append(f"{where}: {msg}")


# ---------------------------------------------------------------- reader

TOKEN = re.compile(r'\s*(?:(;[^\n]*)|("(?:[^"\\]|\\.)*")|([()])|(!)|([^\s()";!]+))')


def read_forms(text, fname):
    pos, stack, top = 0, [[]], []
    line = 1
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            err(fname, f"cannot tokenize near line {line}")
            return []
        line += text[pos:m.end()].count("\n")
        pos = m.end()
        comment, string, paren, bang, atom = m.groups()
        if comment is not None:
            continue
        if paren == "(":
            stack.append([])
        elif paren == ")":
            if len(stack) == 1:
                err(fname, f"unbalanced ')' near line {line}")
                return []
            done = stack.pop()
            stack[-1].append(done)
        elif bang:
            stack[-1].append("!")
        elif string is not None:
            stack[-1].append(string)
        elif atom is not None:
            stack[-1].append(atom)
    if len(stack) != 1:
        err(fname, "unbalanced '(' at end of file")
        return []
    forms, items, i = [], stack[0], 0
    while i < len(items):
        if items[i] == "!" and i + 1 < len(items):
            forms.append(("run", items[i + 1]))
            i += 2
        else:
            forms.append(("form", items[i]))
            i += 1
    return forms


def is_num(a):
    return isinstance(a, str) and re.fullmatch(r"-?\d+", a) is not None


def show(x):
    if isinstance(x, list):
        return "(" + " ".join(show(y) for y in x) + ")"
    return x


# ---------------------------------------------------------------- modules

class Module:
    def __init__(self, name, form, fname):
        self.name, self.form, self.fname = name, form, fname
        self.decls = {}        # name -> (kind, form)
        self.elements = set()
        self.labels = set()    # observation and action labels, block, member and description labels
        self.fields = set()    # record field names
        self.libraries = {"Core"}
        self.dynamics = None
        self.values = None
        self.carriers = None
        self.imports = []


def lib_names(libs, key):
    out = set()
    for lib in libs:
        out |= set(REG["libraries"].get(lib, {}).get(key, []))
    return out


def scan_module(mod):
    body = mod.form[2:]
    for item in body:
        if not isinstance(item, list) or not item:
            err(mod.fname, f"module {mod.name}: stray atom {show(item)}")
            continue
        head = item[0]
        if head == "Profile":
            parse_profile(mod, item)
        elif head == "Use":
            for lib in item[1:]:
                if lib not in REG["libraries"]:
                    err(mod.fname, f"module {mod.name}: unknown library {lib}")
                mod.libraries.add(lib)
        elif head == "Import":
            mod.imports.append(item)
        elif head in REG["declarations"]:
            if len(item) < 2 or not isinstance(item[1], str):
                err(mod.fname, f"{head} without a name")
                continue
            name = item[1]
            if name in mod.decls:
                err(mod.fname, f"duplicate declaration {name}")
            mod.decls[name] = (head, item)
            collect_names(mod, head, item)
        else:
            err(mod.fname, f"module {mod.name}: unknown declaration head {head}")
    if mod.dynamics is None:
        err(mod.fname, f"module {mod.name}: missing Profile")


def parse_profile(mod, item):
    sh = REG["profiles"]["shorthands"]
    if len(item) == 2 and isinstance(item[1], str):
        if item[1] not in sh:
            err(mod.fname, f"unknown profile shorthand {item[1]}")
            return
        mod.dynamics, mod.values, mod.carriers = sh[item[1]]
        return
    kv = {x[0]: x[1] for x in item[1:] if isinstance(x, list) and len(x) == 2}
    mod.dynamics = kv.get("Dynamics")
    mod.values = kv.get("Values")
    mod.carriers = kv.get("Carriers")
    P = REG["profiles"]
    if mod.dynamics not in P["dynamics"] or mod.values not in P["values"] or mod.carriers not in P["carriers"]:
        err(mod.fname, f"bad profile {show(item)}")


def collect_names(mod, head, item):
    def walk_elements(body):
        if isinstance(body, list) and body and body[0] == "Enum":
            for e in body[1:]:
                mod.elements.add(e if isinstance(e, str) else show(e))
    if head == "Carrier":
        for x in item[2:]:
            walk_elements(x)
    elif head == "Record":
        for f in item[2:]:
            if isinstance(f, list) and f:
                mod.fields.add(f[0])
    elif head in ("Machine", "MethodSystem"):
        for x in item[2:]:
            if isinstance(x, list) and x and x[0] in ("Observe", "Action", "Merge") and len(x) > 1:
                # M0-prep (ex_check.py install): a family entry has a compound label such as (assign $u $r);
                # record the label head
                if isinstance(x[1], list):
                    if x[1] and isinstance(x[1][0], str):
                        mod.labels.add(x[1][0])
                else:
                    mod.labels.add(x[1])
    elif head == "BlockPartition":
        for x in item[2:]:
            if isinstance(x, list) and x and x[0] == "Block" and len(x) > 1:
                mod.labels.add(x[1])
    elif head == "KernelHive":
        for x in item[2:]:
            if isinstance(x, list) and x and x[0] == "Member" and len(x) > 1:
                mod.labels.add(x[1])
    elif head == "DescriptionSystem":
        for x in item[2:]:
            if isinstance(x, list) and x and x[0] == "Description" and len(x) > 1:
                mod.labels.add(x[1])


def resolve_imports(mod, modules):
    for imp in mod.imports:
        if len(imp) < 3 or not isinstance(imp[2], list) or imp[2][0] != "Only":
            err(mod.fname, f"Import must name its declarations with (Only ...): {show(imp)}")
            continue
        src = modules.get(imp[1])
        if src is None:
            err(mod.fname, f"Import of unknown module {imp[1]}")
            continue
        for nm in imp[2][1:]:
            if nm not in src.decls:
                err(mod.fname, f"Import: {imp[1]} has no declaration {nm}")
                continue
            mod.decls[nm] = src.decls[nm]
            collect_names(mod, src.decls[nm][0], src.decls[nm][1])
        mod.elements |= src.elements
        mod.libraries |= src.libraries


# ---------------------------------------------------------------- names and kinds

ARROW_TYPES = {"CheckedAbstractionMap", "CheckedGradedArrow", "CheckedLinearArrow", "CheckedSimulation",
               "ComposedArrow", "CheckedTransfer"}


def field_type(result, field):
    if field == "Value":
        return result
    t = REG["result_types"].get(result, {}).get("fields", {}).get(field)
    return t.rstrip("?") if t else None


def kind_ok(kinds, decl_kind=None, field_t=None):
    # M0-prep (ex_check.py install): a declaration head may declare another kind, e.g. a ParallelMachine is a Machine
    if decl_kind in REG["declarations"]:
        declared = REG["declarations"][decl_kind].get("declares")
        if declared and declared != decl_kind and _kind_ok(kinds, decl_kind=declared, field_t=field_t):
            return True
    return _kind_ok(kinds, decl_kind=decl_kind, field_t=field_t)


def _kind_ok(kinds, decl_kind=None, field_t=None):
    for k in kinds:
        if decl_kind == k or field_t == k:
            return True
        if k == "Arrow" and (field_t in ARROW_TYPES or decl_kind in ("AbstractionMap", "LinearArrow", "Simulation", "Transfer")):
            return True
        if k == "Machine" and decl_kind == "Machine":
            return True
    return False


class Ctx:
    def __init__(self, mod, where):
        self.mod, self.where = mod, where
        self.results = {}      # LetResult variables -> result type
        self.bound = set()


def result_type_of_derivation(mod, name):
    kind, form = mod.decls.get(name, (None, None))
    if kind != "Derive" or len(form) < 3:
        return None
    return request_result(mod, form[2])


def request_result(mod, rq):
    if not isinstance(rq, list) or not rq:
        return None
    head = rq[0]
    if head in REG["requests"]:
        return REG["requests"][head]["result"]
    if mod.decls.get(head, (None,))[0] == "Method":
        ret = [x for x in mod.decls[head][1] if isinstance(x, list) and x and x[0] == "Returns"]
        return ret[0][1] if ret else None
    return None


def check_ref(val, kinds, ctx):
    mod = ctx.mod
    kinds = kinds.split("|")
    if isinstance(val, str):
        if val.startswith("$"):
            return  # parameter of a schema or method; checked at invocation
        d = mod.decls.get(val)
        if d is None:
            err(ctx.where, f"undeclared name {val} (expected {'|'.join(kinds)})")
            return
        if d[0] == "Derive":
            rt = result_type_of_derivation(mod, val)
            if not kind_ok(kinds, field_t=rt):
                err(ctx.where, f"{val} is a derivation of type {rt}, expected {'|'.join(kinds)}")
            return
        if not kind_ok(kinds, decl_kind=d[0]):
            err(ctx.where, f"{val} is a {d[0]}, expected {'|'.join(kinds)}")
        return
    if isinstance(val, list) and val and val[0] == "Output":
        if len(val) != 3:
            err(ctx.where, f"Output needs a source and a field: {show(val)}")
            return
        src, fld = val[1], val[2]
        if src.startswith("$"):
            rt = ctx.results.get(src)
            if rt is None:
                err(ctx.where, f"Output from unbound result variable {src}")
                return
        else:
            if mod.decls.get(src, (None,))[0] != "Derive":
                err(ctx.where, f"Output from {src}, which is not a derivation")
                return
            rt = result_type_of_derivation(mod, src)
        ft = field_type(rt, fld)
        if ft is None:
            avail = ", ".join(sorted(REG["result_types"].get(rt, {}).get("fields", {})))
            err(ctx.where, f"result {rt} has no field {fld} (available: Value, {avail})")
            return
        if not kind_ok(kinds, field_t=ft):
            err(ctx.where, f"(Output {src} {fld}) has type {ft}, expected {'|'.join(kinds)}")
        return
    err(ctx.where, f"expected a reference to {'|'.join(kinds)}, found {show(val)}")


def rational(val):
    if is_num(val):
        return int(val), 1
    if isinstance(val, list) and len(val) == 3 and val[0] == "Rat" and is_num(val[1]) and is_num(val[2]):
        return int(val[1]), int(val[2])
    return None


def check_value(val, typ, ctx, what):
    if typ == "stable-or-horizon":  # M0-prep (ex1 patch: Refine Until)
        if val == "Stable":
            return
        typ = "horizon"
    if typ == "rat01":
        r = rational(val)
        if r is None or r[1] <= 0 or not (0 <= r[0] <= r[1]):
            err(ctx.where, f"{what}: expected a rational in [0,1], found {show(val)}")
    elif typ == "discount":
        r = rational(val)
        if r is None or r[1] <= 0 or not (0 < r[0] <= r[1]):
            err(ctx.where, f"{what}: expected a discount in (0,1], found {show(val)}")
    elif typ == "rat":
        if rational(val) is None:
            err(ctx.where, f"{what}: expected a rational, found {show(val)}")
    elif typ == "nat":
        if not (is_num(val) and int(val) >= 0):
            err(ctx.where, f"{what}: expected a natural number, found {show(val)}")
    elif typ == "horizon":
        ok = val == "AllFiniteWords" or (isinstance(val, list) and len(val) == 2 and val[0] == "Steps" and is_num(val[1]))
        if not ok:
            err(ctx.where, f"{what}: expected AllFiniteWords or (Steps k), found {show(val)}")
    elif typ == "budget":
        if not (isinstance(val, list) and len(val) == 2 and is_num(val[1])):
            err(ctx.where, f"{what}: expected (Unit k), found {show(val)}")
    elif typ == "selector":
        if val in ("Center", "First"):
            return
        if isinstance(val, list) and len(val) == 2 and val[0] == "Choose":
            check_ref(val[1], "Map", ctx)
            return
        err(ctx.where, f"{what}: expected Center, First or (Choose map), found {show(val)}")
    elif typ.startswith("enum:"):
        if val not in typ[5:].split("|"):
            err(ctx.where, f"{what}: expected one of {typ[5:]}, found {show(val)}")
    elif typ.startswith("ref:"):
        check_ref(val, typ[4:], ctx)
    elif typ == "word":
        if not (isinstance(val, list) and val and val[0] == "Do"):
            err(ctx.where, f"{what}: expected (Do a ...), found {show(val)}")
        else:
            for a in val[1:]:
                if a not in ctx.mod.labels:
                    err(ctx.where, f"{what}: unknown action label {a}")
    elif typ == "pair":
        if not (isinstance(val, list) and len(val) == 3 and val[0] == "Pair"):
            err(ctx.where, f"{what}: expected (Pair a b), found {show(val)}")
        else:
            check_expr(val, ctx)
    elif typ == "grade":
        if not (isinstance(val, list) and len(val) == 3 and val[0] == "Grade" and rational(val[1]) and rational(val[2])):
            err(ctx.where, f"{what}: expected (Grade L eta), found {show(val)}")
    elif typ == "element":
        if not (isinstance(val, str) and (val in ctx.mod.elements or is_num(val))):
            err(ctx.where, f"{what}: {show(val)} is not a declared element")
    elif typ == "name":
        if not isinstance(val, str):
            err(ctx.where, f"{what}: expected a name, found {show(val)}")
    elif typ in ("expr", "predicate", "names", "request", "property"):
        check_expr(val, ctx)
    else:
        err(ctx.where, f"{what}: unknown registry type {typ}")


def known_atom(a, ctx):
    mod = ctx.mod
    if is_num(a) or a.startswith('"'):
        return True
    if a.startswith("$"):
        return True
    if a in mod.decls or a in mod.elements or a in mod.labels or a in mod.fields:
        return True
    libs = mod.libraries
    for key in ("constants", "builtin_types", "primitives", "type_constructors"):
        if a in lib_names(libs, key):
            return True
    if a in REG["requests"] or a in REG["declarations"] or a in REG["result_types"]:
        return True
    return False


def known_head(h, ctx):
    if isinstance(h, list):
        return True
    if known_atom(h, ctx):
        return True
    return False


QUOTING = {"Tokens", "Query", "Digest"}


def check_expr(x, ctx):
    if isinstance(x, str):
        if not known_atom(x, ctx):
            err(ctx.where, f"undeclared name {x}")
        return
    if not x:
        return
    head = x[0]
    if isinstance(head, str) and head in QUOTING:
        if head == "Query" and len(x) > 1:
            check_expr(x[1], ctx)
        return
    if isinstance(head, str) and head == "Output":
        check_ref(x, "Machine|Representation|Arrow|Tolerance|Relation|KernelHive|Transfer|Map|Scalar|"
                     "CheckedImplementationContract|Certificate|DefectMeasurement|PolicyValue|AveragedModel|"
                     "InvarianceResult|ExactAbstraction|Refinement|Partition|Rational", ctx)
        return
    if isinstance(head, str) and (head in REG["requests"] or ctx.mod.decls.get(head, (None,))[0] == "Method"):
        check_request(x, ctx)
        return
    if isinstance(head, str) and head in REG["declarations"] and head not in REG["requests"]:
        dfields = REG["declarations"][head]["fields"]
        for y in x[1:]:
            if isinstance(y, list) and y and y[0] in dfields:
                for z in y[1:]:
                    check_expr(z, ctx)
            else:
                check_expr(y, ctx)
        return
    if isinstance(head, str) and head == "LetResult":
        if len(x) != 4 or not isinstance(x[1], str) or not x[1].startswith("$"):
            err(ctx.where, f"LetResult needs $var, request and body: {show(x)}")
            return
        check_request(x[2], ctx)
        ctx.results[x[1]] = request_result(ctx.mod, x[2])
        check_expr(x[3], ctx)
        return
    if not known_head(head, ctx):
        err(ctx.where, f"unknown head {head} in {show(x)[:60]}")
    for y in x[1:]:
        check_expr(y, ctx)


def check_request(rq, ctx):
    head = rq[0]
    if head in REG["requests"]:
        spec = REG["requests"][head]
    elif ctx.mod.decls.get(head, (None,))[0] == "Method":
        params = [x for x in ctx.mod.decls[head][1] if isinstance(x, list) and x and x[0] == "Parameters"]
        n = len(params[0]) - 1 if params else 0
        if len(rq) - 1 != n:
            err(ctx.where, f"method {head} takes {n} argument(s)")
        for a in rq[1:]:
            check_expr(a, ctx)
        return
    else:
        err(ctx.where, f"unregistered request {head}")
        return
    mod = ctx.mod
    if spec["library"] not in mod.libraries:
        err(ctx.where, f"{head} belongs to library {spec['library']}, not imported by {mod.name}")
    if mod.dynamics not in spec["profiles"]:
        err(ctx.where, f"{head} does not support {mod.dynamics} dynamics")
    if mod.carriers not in spec["carriers"]:
        err(ctx.where, f"{head} does not support {mod.carriers} carriers")
    args = rq[1:]
    pos_spec = spec["positional"]
    variadic = bool(pos_spec) and len(pos_spec[-1]) > 2 and pos_spec[-1][2] == "variadic"
    keyed_names = set(spec["args"])
    positional = []
    i = 0
    while i < len(args) and not (isinstance(args[i], list) and args[i] and args[i][0] in keyed_names
                                 and (len(positional) >= len(pos_spec) or not variadic)):
        if not variadic and len(positional) == len(pos_spec):
            break
        positional.append(args[i])
        i += 1
    if variadic:
        if len(positional) < 1:
            err(ctx.where, f"{head} needs at least one {pos_spec[-1][0]}")
        for p in positional:
            check_value(p, pos_spec[-1][1], ctx, f"{head} {pos_spec[-1][0]}")
    else:
        if len(positional) != len(pos_spec):
            err(ctx.where, f"{head} expects {len(pos_spec)} positional argument(s), found {len(positional)}")
        for p, (pname, ptype, *_) in zip(positional, pos_spec):
            check_value(p, ptype, ctx, f"{head} {pname}")
    seen = set()
    for a in args[i:]:
        if not (isinstance(a, list) and a and a[0] in keyed_names):
            err(ctx.where, f"{head}: unknown argument {show(a)[:50]} (registered: {', '.join(sorted(keyed_names)) or 'none'})")
            continue
        if a[0] in seen:
            err(ctx.where, f"{head}: duplicate argument {a[0]}")
        seen.add(a[0])
        if spec["args"][a[0]]["type"] in ("grade", "pair"):
            check_value(a, spec["args"][a[0]]["type"], ctx, f"{head} {a[0]}")
            continue
        if len(a) != 2:
            if spec["args"][a[0]]["type"] in ("names",):
                for y in a[1:]:
                    check_expr(y, ctx)
                continue
            err(ctx.where, f"{head}: argument {a[0]} takes one value")
            continue
        check_value(a[1], spec["args"][a[0]]["type"], ctx, f"{head} {a[0]}")
    for name, aspec in spec["args"].items():
        if aspec.get("required") and name not in seen:
            err(ctx.where, f"{head}: missing required argument {name}")


def binders():
    """M0-prep: binder heads declared by registered libraries (the Families library's For)."""
    return {b for lib in REG["libraries"].values() for b in lib.get("binders", [])}


def bound_vars(x, out):
    if (isinstance(x, list) and x and isinstance(x[0], str) and x[0] in binders() and len(x) > 1
            and isinstance(x[1], str)):
        out.add(x[1])
    if isinstance(x, list):
        if x and x[0] in ("Body",) and len(x) >= 2 and isinstance(x[1], list):
            out |= {v for v in x[1] if isinstance(v, str) and v.startswith("$")}
        if x and x[0] == "Cases":
            for case in x[1:]:
                if isinstance(case, list) and case:
                    collect_vars(case[0], out)
        if x and x[0] in ("For", "LetResult") and len(x) > 1 and isinstance(x[1], str):
            out.add(x[1])
        if x and x[0] in ("Parameters", "Lambda"):
            for b in x[1:]:
                if isinstance(b, list) and b and isinstance(b[0], str) and b[0].startswith("$"):
                    out.add(b[0])
                if isinstance(b, list):
                    for bb in b:
                        if isinstance(bb, list) and bb and isinstance(bb[0], str) and bb[0].startswith("$"):
                            out.add(bb[0])
        if x and x[0] == "Query" and len(x) > 2:
            collect_vars(x[2], out)
        for y in x:
            bound_vars(y, out)


def collect_vars(x, out):
    if isinstance(x, str) and x.startswith("$"):
        out.add(x)
    elif isinstance(x, list):
        for y in x:
            collect_vars(y, out)


def check_hygiene(item, ctx):
    bound, used = set(), set()
    bound_vars(item, bound)
    collect_vars(item, used)
    for v in sorted(used - bound):
        err(ctx.where, f"unbound variable {v}")


def check_declaration(mod, name, kind, item):
    spec = REG["declarations"][kind]
    ctx = Ctx(mod, f"{mod.fname}:{mod.name}.{name}")
    check_hygiene(item, ctx)
    pos = spec["positional"]
    rest = item[1 + len(pos):]
    for (pname, ptype), val in zip(pos[1:], item[2:2 + len(pos) - 1]):
        if ptype == "request":
            if not isinstance(val, list) or not val:
                err(ctx.where, "Derive needs a request")
            else:
                check_request(val, ctx)
        elif ptype not in ("name",):
            check_value(val, ptype, ctx, f"{kind} {pname}")
    fields = spec["fields"]
    seen = {}
    body_seen = False
    for x in rest:
        if isinstance(x, list) and x and x[0] in fields:
            f = fields[x[0]]
            seen[x[0]] = seen.get(x[0], 0) + 1
            if seen[x[0]] > 1 and not f.get("repeatable"):
                err(ctx.where, f"duplicate field {x[0]}")
            vals = x[1:]
            if f["type"] in ("expr", "names", "predicate"):
                for v in vals:
                    check_expr(v, ctx)
            elif len(vals) == 1:
                check_value(vals[0], f["type"], ctx, f"{kind} {x[0]}")
            else:
                err(ctx.where, f"field {x[0]} takes one value")
        elif spec["body"] and (not body_seen or spec["body"] == "fields"):
            body_seen = True
            check_body(spec["body"], x, ctx)
        else:
            err(ctx.where, f"unknown field {show(x)[:50]} for {kind}")
    for fname, f in fields.items():
        if f.get("required") and fname not in seen:
            err(ctx.where, f"missing required field {fname}")
    if spec["body"] and spec["body"] != "fields" and not body_seen:
        err(ctx.where, f"{kind} needs a {spec['body']}")
    if kind in ("Machine", "MethodSystem"):
        check_machine_items(item, ctx)


BODY_HEADS = {
    "carrier-expr": {"Enum", "Product", "All", "Subset", "Reach", "Query"},
    "map-body": {"Cases", "Body", "Table", "Choice", "Query"},
    "tolerance-body": {"SymmetricTable", "DirectedTable", "Pullback", "OneMinusAbsoluteDifference", "Discrete", "Trivial"},
    "measure-body": {"Uniform", "Masses", "Product"},
}
for _kind, _heads in REG.get("body_heads_added", {}).items():  # M0-prep: e.g. the ex1 patch's tolerance body Meet
    BODY_HEADS.setdefault(_kind, set()).update(_heads)


def check_body(kind, x, ctx):
    if kind == "fields":
        if not (isinstance(x, list) and len(x) == 2):
            err(ctx.where, f"record field must be (name type): {show(x)}")
        return
    if not (isinstance(x, list) and x and x[0] in BODY_HEADS[kind]):
        err(ctx.where, f"expected a {kind}, found {show(x)[:50]}")
        return
    if x[0] == "Reach":
        if len(x) < 3 or ctx.mod.decls.get(x[1], (None,))[0] != "Machine":
            err(ctx.where, f"Reach needs a declared machine: {show(x)}")
        frm = [y for y in x[2:] if isinstance(y, list) and y and y[0] == "From"]
        if not frm:
            err(ctx.where, "Reach needs (From e+)")
        return
    if x[0] == "Enum":
        return
    check_expr(x, ctx)


def map_instance_ok(mp, ctx):
    # M0-prep (ex_check.py install): a map, or an instance of a parameterized map
    if isinstance(mp, str):
        check_ref(mp, "Map|TransitionKernel", ctx)
        return
    if isinstance(mp, list) and mp and isinstance(mp[0], str):
        d = ctx.mod.decls.get(mp[0])
        if d and d[0] == "Map" and any(isinstance(f, list) and f and f[0] == "Parameters" for f in d[1]):
            for a in mp[1:]:
                check_expr(a, ctx)
            return
    err(ctx.where, f"expected a map or an instance of a parameterized map, found {show(mp)[:60]}")


def check_machine_items(item, ctx):
    # M0-prep: the ex_check.py install() version (For and Values options, compound labels, Available, map instances)
    have_binders = bool(binders())
    for x in item[2:]:
        if not (isinstance(x, list) and x) or x[0] not in ("Observe", "Action", "Merge", "Available"):
            continue
        rest = x[1:]
        fors = [y for y in rest if isinstance(y, list) and y and y[0] == "For"]
        opts = [y for y in rest if isinstance(y, list) and y and y[0] == "Values"]
        core = [y for y in rest if not any(y is z for z in fors + opts)]
        if x[0] == "Available":
            for y in core:
                check_expr(y, ctx)
            continue
        if len(core) != 2:
            err(ctx.where, f"{x[0]} needs a label and a map: {show(x)[:60]}")
            continue
        label, mp = core
        for f in fors:
            if not (len(f) == 3 and isinstance(f[1], str) and f[1].startswith("$")):
                err(ctx.where, f"For needs a variable and a carrier: {show(f)}")
            elif ctx.mod.decls.get(f[2], (None,))[0] != "Carrier":
                err(ctx.where, f"For ranges over an undeclared carrier {f[2]}")
        if fors and not have_binders:
            err(ctx.where, "For on a machine entry needs the Families library")
        if isinstance(label, list):
            for a in label[1:]:
                check_expr(a, ctx)
        map_instance_ok(mp, ctx)
        for o in opts:
            check_ref(o[1], "Tolerance", ctx)


def check_run(form, modules, fname):
    if not (isinstance(form, list) and form and form[0] == "dc.run" and len(form) == 3):
        err(fname, f"run form must be !(dc.run Module request): {show(form)[:60]}")
        return None
    mod = modules.get(form[1])
    if mod is None:
        err(fname, f"run of unknown module {form[1]}")
        return None
    ctx = Ctx(mod, f"{fname}:run {show(form[2])[:40]}")
    rq = form[2]
    if isinstance(rq, str):
        if mod.decls.get(rq, (None,))[0] != "Derive":
            err(ctx.where, f"{rq} is not a derivation of {mod.name}")
        return mod
    check_request(rq, ctx)
    return mod


# ---------------------------------------------------------------- release status

def release1_supported(mod, request_head):
    fr = REG["first_release"]
    spec = REG["requests"].get(request_head)
    if spec is None:
        return False
    return (mod.dynamics in spec["first_release"] and mod.values in fr["values"]
            and mod.carriers in fr["carriers"] and all(l in fr["libraries"] for l in mod.libraries))


def head_of(mod, target):
    if isinstance(target, list):
        return target[0]
    d = mod.decls.get(target)
    if d and d[0] == "Derive":
        return d[1][2][0]
    return None


# ---------------------------------------------------------------- manifest

def norm(s):
    return " ".join(s.replace("(", " ( ").replace(")", " ) ").split())


def lookup(results, path):
    cur = results
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return KeyError
    return cur


def check_manifest(modules, runs):
    man = json.load(open(os.path.join(ROOT, "manifest.json")))
    res = json.load(open(os.path.join(ROOT, "oracle", "mettadinc_oracle_results.json")))
    ids = set()
    rows = []
    for c in man["claims"]:
        cid = c["id"]
        where = f"manifest {cid}"
        if cid in ids:
            err(where, "duplicate claim id")
        ids.add(cid)
        mod = modules.get(c["module"])
        if mod is None or os.path.basename(mod.fname) != c["fixture"]:
            err(where, f"module {c['module']} not found in {c['fixture']}")
            continue
        target = c["request"]
        if target.startswith("("):
            if norm(target) not in runs.get(mod.name, set()):
                err(where, f"request {target} is not run in {c['fixture']}")
            parsed = read_forms(target, where)[0][1]
            head = parsed[0]
        else:
            if mod.decls.get(target, (None,))[0] != "Derive":
                err(where, f"{target} is not a derivation in {mod.name}")
            head = head_of(mod, target)
        if c["status"] not in REG["statuses"]:
            err(where, f"unknown status {c['status']}")
        spec = REG["requests"].get(head)
        if spec is not None and c["status"] not in spec["statuses"] + REG["base_statuses"]:
            err(where, f"status {c['status']} is not registered for {head}")
        for o in c.get("oracle", []):
            got = lookup(res, o["key"])
            if got is KeyError:
                err(where, f"oracle key {o['key']} missing")
            elif got != o["value"]:
                err(where, f"oracle {o['key']} = {json.dumps(got)}, manifest says {json.dumps(o['value'])}")
        until = c.get("until")
        if until is not None:
            caps = set(REG.get("witness_types", {})) | {k for k, v in REG.get("certificate_kinds", {}).items()
                                                       if isinstance(v, dict)}
            if until.get("capability") not in caps:
                err(where, f"until names {until.get('capability')}, which is neither a witness type nor a certificate kind")
            for st in until.get("statuses", []):
                if st not in REG["statuses"]:
                    err(where, f"until lists the unknown status {st}")
        r1 = "Supported" if (spec is not None and release1_supported(mod, head)) else "Unsupported"
        if c.get("release1") != r1:
            err(where, f"release1 should be {r1}")
        rows.append((cid, c["module"], head, c["status"], r1))
    return rows


# ---------------------------------------------------------------- main

def main():
    quiet = "--quiet" in sys.argv
    modules, runs, files = {}, {}, sorted(f for f in os.listdir(FIXDIR) if f.endswith(".metta"))
    parsed = {}
    for f in files:
        text = open(os.path.join(FIXDIR, f)).read()
        forms = read_forms(text, f)
        parsed[f] = forms
        for kind, form in forms:
            if kind == "form":
                if not (isinstance(form, list) and form and form[0] == "DC.Module" and len(form) >= 3):
                    err(f, f"top-level form is not a module: {show(form)[:50]}")
                    continue
                if form[1] in modules:
                    err(f, f"duplicate module {form[1]}")
                modules[form[1]] = Module(form[1], form, f)
    for m in modules.values():
        scan_module(m)
    for m in modules.values():
        resolve_imports(m, modules)
    for m in modules.values():
        for name, (kind, item) in list(m.decls.items()):
            if item in m.form[2:]:
                check_declaration(m, name, kind, item)
    nruns = 0
    for f, forms in parsed.items():
        for kind, form in forms:
            if kind == "run":
                mod = check_run(form, modules, f)
                nruns += 1
                if mod is not None:
                    runs.setdefault(mod.name, set()).add(norm(show(form[2])))
    rows = check_manifest(modules, runs)
    ndecl = sum(len([1 for (k, it) in m.decls.values() if it in m.form[2:]]) for m in modules.values())
    if not quiet:
        print(f"{len(files)} fixture files, {len(modules)} modules, {ndecl} declarations, {nruns} run requests")
        print(f"{len(rows)} manifest claims; first release must answer "
              f"{sum(1 for r in rows if r[4] == 'Supported')} and return Unsupported for "
              f"{sum(1 for r in rows if r[4] == 'Unsupported')}")
    if ERRORS:
        print(f"{len(ERRORS)} error(s):")
        for e in ERRORS:
            print("  " + e)
        return 1
    print("All fixtures conform to the registry; the manifest agrees with the oracle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
