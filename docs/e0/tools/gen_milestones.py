#!/usr/bin/env python3
"""Generate projects/mettadinc/MILESTONES.md from the Cetta implementation guide (tex + pdf),
the claims manifest and the fixture files. Quotes are mechanical conversions of the guide's LaTeX
source; page numbers are found by searching the PDF text. Mappings marked [assigned] are this
generator's, not the guide's."""
import json, re, subprocess, sys, collections
BT = chr(96); BT3 = BT * 3
def cs(x): return BT + x + BT
D = sys.argv[1]; OUT = sys.argv[2]
G = f"{D}/02_cetta_implementation_guide/mettadinc_cetta_implementation_guide"
VP = f"{D}/01_language_specification/validation_package"
tex = open(G + ".tex").read().split("\n")

pages = subprocess.run(["pdftotext", "-layout", G + ".pdf", "-"], capture_output=True, text=True).stdout.split("\f")
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
npages = [norm(p) for p in pages]
def page_of(snippet, start=1):
    k = norm(snippet)
    for i in range(start - 1, len(npages)):
        if k and k in npages[i]: return i + 1
    return None
def pref(pg): return f"p. {pg-1} (PDF p. {pg})" if pg else "p. ?"

secs = []; s = ss = 0
for i, l in enumerate(tex):
    m = re.match(r"\\(section|subsection)(\*?)\{(.*?)\}(\\label\{(.*?)\})?", l)
    if not m or m.group(2): continue
    if m.group(1) == "section": s += 1; ss = 0; num = f"{s}"
    else: ss += 1; num = f"{s}.{ss}"
    secs.append((i + 1, m.group(1), num, m.group(3), m.group(5)))
labels = {x[4]: x[2] for x in secs if x[4]}
labels.update({"tab:certs": "Table 1", "tab:manifest": "Table 2"})
def section_range(prefix):
    for k, x in enumerate(secs):
        if x[3].startswith(prefix):
            end = secs[k + 1][0] - 1 if k + 1 < len(secs) else len(tex)
            return x, x[0], end
    raise KeyError(prefix)

def brace_sub(s, cmd, fn):
    out, i = "", 0; pat = "\\" + cmd + "{"
    while True:
        j = s.find(pat, i)
        if j < 0: return out + s[i:]
        k, depth = j + len(pat), 1
        while depth and k < len(s):
            depth += {"{": 1, "}": -1}.get(s[k], 0); k += 1
        out += s[i:j] + fn(s[j + len(pat):k - 1]); i = k
def inline(s):
    s = s.replace("\\allowbreak{}", "").replace("\\textasciicircum{}", "^").replace("\\textasciitilde{}", "~")
    s = s.replace("\\L{}", "Ł").replace("\\ss{}", "ß").replace('\\"o', "ö").replace("\\par", "")
    for c in ("code", "fpath", "nolinkurl"):
        s = brace_sub(s, c, lambda x: cs(x.replace("\\_", "_")))
    s = brace_sub(s, "emph", lambda x: "*" + x + "*")
    s = brace_sub(s, "textbf", lambda x: "**" + x + "**")
    s = brace_sub(s, "url", lambda x: x)
    s = brace_sub(s, "cite", lambda x: "[" + x + "]")
    s = re.sub(r"Section~\\ref\{(.*?)\}", lambda m: "§" + labels.get(m.group(1), m.group(1)), s)
    s = re.sub(r"Table~\\ref\{(.*?)\}", lambda m: labels.get(m.group(1), m.group(1)), s)
    s = brace_sub(s, "ref", lambda x: labels.get(x, x))
    s = s.replace("\\_", "_").replace("~", " ").replace("---", "—").replace("--", "–").replace("\\%", "%")
    s = s.replace("{\\raggedright", "").replace("\\smallskip", "").replace("\\\\", "")
    return s
def convert(lines):
    out, inlist, code = [], [], False
    for l in lines:
        st = l.strip()
        if st.startswith("\\begin{lstlisting}"): out.append(BT3); code = True; continue
        if st.startswith("\\end{lstlisting}"): out.append(BT3); code = False; continue
        if code: out.append(l); continue
        if re.match(r"\\(sub)?section", st): continue
        if st.startswith("\\begin{enumerate}"): inlist.append([0]); continue
        if st.startswith("\\begin{itemize}"): inlist.append(None); continue
        if st.startswith("\\end{enumerate}") or st.startswith("\\end{itemize}"):
            if inlist: inlist.pop()
            out.append(""); continue
        if st.startswith("\\item"):
            body = inline(st[5:].strip())
            if inlist and inlist[-1] is not None:
                inlist[-1][0] += 1; out.append(f"{inlist[-1][0]}. {body}")
            else: out.append(f"- {body}")
            continue
        if re.match(r"\\(begin|end)\{|\\(toprule|midrule|bottomrule|endhead|caption|label)", st): continue
        if inlist and st and out: out[-1] = out[-1] + " " + inline(st)
        else: out.append(inline(st))
    txt = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", txt)
def quote(md): return "\n".join(("> " + l) if l.strip() else ">" for l in md.strip().split("\n"))
def tex_lines(a, b): return tex[a - 1:b]
def find_line(pat, start=1):
    for i in range(start - 1, len(tex)):
        if pat in tex[i]: return i + 1
    raise KeyError(pat)

man = json.load(open(f"{VP}/manifest.json")); claims = man["claims"]
reg = json.load(open(f"{VP}/registry/mettadinc_registry.json"))
byid = {c["id"]: c for c in claims}
fixcache = {}
def fixture_loc(c):
    fn = c["fixture"]
    if fn not in fixcache: fixcache[fn] = open(f"{VP}/fixtures/{fn}").read()
    t = fixcache[fn]
    mm = re.search(r"\(DC\.Module\s+" + re.escape(c["module"]) + r"\b", t)
    modline = t[:mm.start()].count("\n") + 1 if mm else None
    want = re.sub(r"\s+", " ", f"(dc.run {c['module']} {c['request']})")
    for m in re.finditer(r"!\(dc\.run", t):
        k = m.start() + 1; depth = 0
        for j in range(k, len(t)):
            depth += {"(": 1, ")": -1}.get(t[j], 0)
            if depth == 0: break
        expr = re.sub(r"\s+", " ", t[k:j + 1])
        if expr == want: return fn, modline, t[:m.start()].count("\n") + 1
    return fn, modline, None

def expand(spec):
    out = []
    for part in re.split(r",\s*", spec):
        m = re.match(r"([A-Z])(\d\d)(?:-([A-Z])?(\d\d))?$", part.strip())
        a, b = int(m.group(2)), int(m.group(4) or m.group(2))
        out += [f"{m.group(1)}{n:02d}" for n in range(a, b + 1)]
    return out
PLAN_CLAIMS = {
 "M0": "E05, E08, E09, H08, H10, H12, C01-C03",
 "M2": "E01-E09, P01-P11, H01-H12, G01-G04",
 "M3": "F01-F06",
 "M4": "S01-S07, L01-L03, V01-V04, R01-R06, O01-O04, U01-U04",
 "M5": "H13-H14, Y01-Y04, D01-D04",
 "M6": "K01-K14, T01-T04, P12-P13, A01-A03",
 "M7": "W01-W02, Q01-Q02, X01-X04, N01-N06, M01, Z01, F07",
}
plan_ids = {m: expand(v) for m, v in PLAN_CLAIMS.items()}
MS = [("M0", "M0: strict certificate boundaries"), ("M1", "M1: registry, syntax, staging and result plumbing"),
      ("M2", "M2: the graded deterministic core on tables"), ("M3", "M3: symbolic carriers and incrementality"),
      ("M4", "M4: stochastic dynamics, linear realizations and estimates"), ("M5", "M5: nondeterminism and simulation"),
      ("M6", "M6: composition kernel, hives, merges, graded kernels and contracts"),
      ("M7", "M7: Hyperseed, observer discovery and integration")]
first_ms = {}
for m, _ in MS:
    for c in plan_ids.get(m, []): first_ms.setdefault(c, m)

a0 = find_line("\\begin{longtable}", find_line("\\label{sec:replay}")); a1 = find_line("\\label{tab:certs}")
cert_rows = []; buf = ""
for l in tex_lines(a0, a1):
    st = l.strip()
    if re.match(r"\\(begin|end|toprule|midrule|bottomrule|endhead|caption)", st): continue
    buf += " " + st
    if st.endswith("\\\\"):
        cells = [inline(x.strip()) for x in buf.strip()[:-2].split("&")]
        if cells[0] != "Claim": cert_rows.append(cells)
        buf = ""
CERT_MS = {"Current or update failure": "M0", "Behavioral failure, deterministic": "M2",
 "Behavioral failure, stochastic or nondeterministic": "M4", "Trace failure, fixed words": "M4",
 "Trace failure, observation-based policies (stochastic)": "M4",
 "Literal-congruence failure (" + cs("InduceExact") + ")": "M0",
 "Graded upper bound, deterministic or stochastic": "M2", "Graded upper bound, nondeterministic": "M5",
 "Graded upper bound at horizon $h$": "M2", "Graded lower bound, stochastic, discount below one": "M4",
 "Exact value (" + cs("Precision 0") + ")": "M0", "Stable partition, enumerated": "M2", "Symbolic partition": "M3",
 "Coarsest partition": "M2", "Linear arrow": "M4", "Signed minimum": "M4", "Positive dimension": "M4",
 "Simulation": "M5", "Transfer": "M6", "Transfer hive": "M6", "Kernel hive": "M6",
 "Least coherent refinement, optimality": "M6", "Affine contract": "M6", "Observer invariance": "M7",
 "Module isomorphism": "M7", "Estimated claim": "M4",
 "Derived result (" + cs("Then") + ", lift, safety transfer, rebuild, gate)": "M0",
 "Claim about a system from an estimated kernel": "M4", "Backend verdict without a replayed proof": "M0"}
_, alg0, alg1 = section_range("Default algorithms and their scope")
alg_full = []; cur = False
for l in tex_lines(alg0, alg1):
    st = l.strip()
    if st.startswith("\\item"): alg_full.append(st[5:].strip()); cur = True; continue
    if st.startswith("\\end{itemize}"): cur = False; continue
    if cur and st: alg_full[-1] += " " + st
ALG_MS = {"Crisp current and update checks": ["M0", "M2"], "Behavioral partition": ["M2"],
          "Crisp behavioral check": ["M2"], "Stochastic lumping": ["M4"], "Graded distances": ["M2", "M4", "M5"],
          "Trace equivalence and linear realizations": ["M4"], "Nondeterminism": ["M5"],
          "Symbolic refinement": ["M3"], "Closure": ["M2"], "Frontier search": ["M2"]}

o = []; w = o.append
gpdf = "docs/02_cetta_implementation_guide/mettadinc_cetta_implementation_guide.pdf"
w("# MeTTaDinC milestones (M0–M7), generated from the Cetta work plan\n")
w("Source: *Implementing MeTTaDinC in Cetta: A Coding-Agent Specification and Work Plan* (4 November 2026), "
  + cs(gpdf) + " and its LaTeX source in the same folder. Page references give the printed page number with the PDF page "
  "in brackets (the unnumbered title page is PDF p. 1). Block quotes are mechanical conversions of the guide's LaTeX "
  "source, not paraphrases; § numbers are the guide's. Claim data come from "
  + cs("docs/01_language_specification/validation_package/manifest.json") + " (123 claims). A fixture location is "
  "file:line of the module declaration and of the " + cs("!(dc.run ...)") + " request the manifest names, in "
  + cs("docs/01_language_specification/validation_package/fixtures/") + ". Anything marked **[assigned]** is this "
  "file's own mapping where the guide gives none; everything else is stated in the guide.\n")
w("Generated by " + cs("tools/gen_milestones.py") + " (rerun: " + cs("python3 tools/gen_milestones.py docs MILESTONES.md") + ").\n")

x, s0, _ = section_range("Milestones, fixtures and acceptance evidence")
w(f"## Overview (§{x[2]}, {pref(page_of('Milestones describe capability and evidence'))})\n")
w(quote(convert(tex_lines(s0 + 1, find_line('\\subsection{M0', s0) - 1))) + "\n")
c0 = find_line("\\subsection*{Coding-agent entry checklist}")
w(f"Coding-agent entry checklist (Purpose and use, {pref(page_of('Coding-agent entry checklist'))}):\n")
w(quote(convert(tex_lines(c0 + 1, find_line("\\tableofcontents") - 1))) + "\n")

r1 = [c for c in claims if c["release1"] == "Supported"]; un = [c for c in claims if c["release1"] != "Supported"]
w("## First-release capability manifest\n")
w(f"manifest.json: {len(claims)} claims; {len(r1)} Supported in the first release, {len(un)} Unsupported. "
  f"Title page: \"Acceptance: the negative acceptance suite, the $45$ first-release claims of the manifest, and "
  f"Unsupported for the other $78$\" ({pref(1+1) if False else 'title page, PDF p. 1'}).\n")
w("Registry " + cs("first_release") + " block (verbatim from " + cs("registry/mettadinc_registry.json") + "):\n")
w(BT3 + "json\n" + json.dumps(reg["first_release"], indent=1, ensure_ascii=False) + "\n" + BT3 + "\n")
x2, rs, re_ = section_range("Registry-driven handoff")
w(f"Guide text on the manifest (§{x2[2]}, {pref(page_of('The first-release manifest covers deterministic dynamics'))}):\n")
w(quote(convert(tex_lines(find_line("The first-release manifest covers", rs) , re_))) + "\n")
w("Claims by milestone. *Plan list* is the claim list the guide gives in that milestone's text; claims are counted at the "
  "earliest milestone whose list contains them (M0's computational list E05, E08, E09, H08, H10, H12 is repeated in M2's).\n")
w("| Milestone | Plan list (verbatim) | Claims (first listed here) | R1 Supported | R1 Unsupported |")
w("|---|---|---|---|---|")
tot = collections.Counter()
for m, _ in MS:
    ids = [c for c in plan_ids.get(m, []) if first_ms.get(c) == m]
    sup = sum(byid[c]["release1"] == "Supported" for c in ids)
    tot["n"] += len(ids); tot["s"] += sup; tot["u"] += len(ids) - sup
    w(f"| {m} | {PLAN_CLAIMS.get(m, '(none: evidence is the Unsupported answers for the 78)')} | {len(ids)} | {sup} | {len(ids)-sup} |")
w(f"| total | | {tot['n']} | {tot['s']} | {tot['u']} |\n")
missing = [c["id"] for c in claims if c["id"] not in first_ms]
extra = [c for c in first_ms if c not in byid]
w(f"Cross-check: manifest claims in no milestone list: {missing or 'none'}; listed ids not in the manifest: {extra or 'none'}. "
  "Supported claims outside M0–M3: " + (", ".join(c["id"] for c in r1 if first_ms[c["id"]] not in ("M0", "M1", "M2", "M3")) or "none") +
  ". Unsupported claims inside M0–M3: " + (", ".join(c["id"] for c in un if first_ms[c["id"]] in ("M0", "M1", "M2", "M3")) or "none") + ".\n")
w("**The 45 first-release claims:** " + ", ".join(c["id"] for c in r1) + ".\n")
w("**The 78 that must answer Unsupported in the first release:** " + ", ".join(c["id"] for c in un) + ".\n")
w("Unsupported claims with an " + cs("until") + " entry (a replay capability their status needs, and the statuses to return meanwhile):\n")
for c in claims:
    if "until" in c: w(f"- {c['id']}: {cs(c['until']['capability'])} — {', '.join(c['until']['statuses'])}")
w("")
req_r1 = sorted(set(re.match(r"\(?(\w+)", c["request"]).group(1) for c in r1))
w("Request or derivation heads used by the 45 Supported claims: " + ", ".join(cs(r) for r in req_r1) +
  ". Heads that are derivation names (defined by " + cs("Derive") + " in the fixture) resolve to one of the 24 first-release requests.\n")

x, s1, e1 = section_range("Semantic invariants")
w(f"## Semantic invariants (§{x[2]}, {pref(page_of('Types and result schemas must keep the following distinctions visible'))}–{pref(page_of('Fifth, for the first stochastic milestone'))})\n")
w("These hold in every milestone (§3.1: \"Every later milestone keeps them, and keeps the suite below passing\"). The five regression cases at the end name their claims.\n")
w(quote(convert(tex_lines(s1 + 1, e1))) + "\n")

def claims_table(ids):
    w("| ID | Module | Request (manifest) | Status | R1 | Statement | Fixture: module line, request line | Oracle keys |")
    w("|---|---|---|---|---|---|---|---|")
    for cid in ids:
        c = byid[cid]; f, ml, rl = fixture_loc(c)
        ok = "; ".join(f"{e['key']}={json.dumps(e['value'])}" for e in c.get("oracle", []))
        if len(ok) > 240: ok = ok[:240] + " …"
        until = f" (until {c['until']['capability']}: {'/'.join(c['until']['statuses'])})" if "until" in c else ""
        w(f"| {cid} | {c['module']} | {cs(c['request'])} | {c['status']}{until} | {'yes' if c['release1']=='Supported' else 'no'} | {c['statement']} | {cs(f)}:{ml}, :{rl or 'NOT FOUND'} | {ok.replace('|','/') or '–'} |")
    w("")

NEG_POINTERS = {
 1: "docs/05_live_memory_part2/validation_bundle/live_memory.metta:101 (EngineIndex with View EngineTime), :103 (EngineAsItems), :114 (CheckStatistic EngineIndex). Also copied into the 06 bundle.",
 2: "docs/05_live_memory_part2/validation_bundle/live_memory.metta:326 (RealWeighted), :330 (RealNormFirst); NormFirst at docs/04_omega_memory_goals_part1/validation_bundle/memory_goals.metta:647. ls_oracle.py runs the two negative InvalidInput fixtures (README).",
 3: "docs/06_wmtm_worked_example/validation_bundle/wmtm_example.metta:255 (Stream RepliesGate); wx_oracle.py checks that a copy with all stale labels set to 0 under the declared digest is refused with InvalidInput (bundle README); ls_oracle.py does the same for the live-memory stream.",
 4: "docs/03_four_worked_examples/validation_bundles/ex2_access_policy/access_policy.metta:23 (approver rule reads the auditor session); breach (assign bob auditor), (assign bob approver) checked at ex2_oracle.py:180; restored-bug mutations from ex2_oracle.py:680.",
 5: "docs/04_omega_memory_goals_part1/validation_bundle/memory_goals.metta:526 (AntiAsNag), :528 (NagForAntiNag), :576 (CheckNow AntiAsNag); CheckInterpretation is defined only in mg_registry_patch.json.",
 6: "docs/06_wmtm_worked_example/validation_bundle/wx_oracle.py:299 (A7: E2 does not transport to a policy that withholds first proposals); same counterexample in the spec oracle verify_mettadinc.py:1955-1960 (section 29 of its report).",
 7: "docs/04_omega_memory_goals_part1/validation_bundle/memory_goals.metta:39-41 (Consumer that Accepts Checked (Conditional (TrustedBackend cvc5))); Conditional verdicts with agreed_by Z3 in docs/05_live_memory_part2/validation_bundle/ls_results.json and docs/06_wmtm_worked_example/validation_bundle/wx_results.json.",
 8: "hypotheses.metta:64 (module LiteralCongruence), requests :75–77: claims C01–C03 in the table above.",
 9: "certificate_limits.metta:6 (AdaptiveProbe), requests :32–36: claims O01–O04 (M4 table).",
 10: "certificate_limits.metta:40 (UnattainedSupremum), requests :54–57: claims U01–U04 (M4 table).",
}
DEPS = {
 "M0": "None. Host: CeTTa 12da03b4 (§2.1). Every later milestone depends on M0 (\"Every later milestone keeps them, and keeps the suite below passing\").",
 "M1": "M0 (stated: \"The frontend of M0 extended to every declaration head, request and library of the registry\").",
 "M2": "M0, M1 **[assigned from the order of work in 'Purpose and use']**. " + cs("CheckInterpretation") + " waits for adoption of the Omega memory and goals registry patch (stated in M0 item 4 and in M2).",
 "M3": "M2 **[assigned]**; M0 fixed the obligation generator's interface (\"The generator itself is built in M3, with the symbolic backend, and the access-policy mutation becomes a gate there\"). Pin before start (§2.5): \"a decision-diagram package (CUDD or Sylvan, or a small in-tree implementation) behind a narrow interface (M3)\". Already pinned: CaDiCaL rel-3.0.1, drat-trim 2e3b2dc, cake_lpr 033aad5.",
 "M4": "M2 **[assigned]**; M0 fixed the Estimate records (\"M0 fixes these records, and the estimators come in M4\") and the PolicyTreeWitness format. Pins before start (§2.5): exact LP for couplings, the finite OmegaPLN reference interpreter (differential oracle), the MeTTaProN shared kernel IR (kernel import).",
 "M5": "M2 **[assigned]**; M0 makes a wrong-target safety transfer InvalidInput \"from M0 on\". Host reuse: " + cs("scripts/rhocalc_bounded_bisimulation.py") + " through the WeakBarbed adapter only.",
 "M6": "M2 and M4 (laws, kernels, transfers of laws) **[assigned]**. No external pin named.",
 "M7": "M2–M6 **[assigned]**. Pins before the parts that use them (§2.5): MORK and PathMap snapshot interfaces beyond the bridges in the pinned commit, the ωPLN adapter target, the Hyperseed proof-plan registry; also the OmegaPLN interpreter and MeTTaProN IR (\"each only after its dependency is pinned\").",
}

FX = "docs/01_language_specification/validation_package/fixtures/"
KEYWORDS = [
 (r"access-policy", cs("docs/03_four_worked_examples/validation_bundles/ex2_access_policy/access_policy.metta") + ":23 and ex2_oracle.py:680 (restored-bug mutations)"),
 (r"clock-rate", cs(FX + "forty_bits.metta") + ":60 (FortyBitsScreens, ZeroRates :65; claim F07)"),
 (r"cone-of-influence|inject|query $x_1$", cs(FX + "forty_bits.metta") + ":4 (FortyBits; inject maps :12, :14)"),
 (r"(?i)seven-state|MergeXY|three-block quotient", cs(FX + "seven_state.metta") + ":5 (SevenState)"),
 (r"Equal expected rewards", cs(FX + "regime_repair.metta") + ":3 (RegimeRepair, R01) and " + cs(FX + "skill_hive.metta") + ":63 (TickLibrary, K13/K14)"),
 (r"transfers field-wise|checked transfer as a tolerance kernel|saturating only the base member|gauges declared", cs(FX + "skill_hive.metta") + ":3 (SkillHive, K04–K09)"),
 (r"unmeasured correspondence", cs(FX + "skill_hive.metta") + ":3 (SkillHive kernel hive) — no dedicated zero-fill fixture found"),
 (r"unmeasured receipt identities", cs(FX + "receipt_packets.metta") + ":38 (PacketMerges, P12/P13)"),
 (r"thresholding treated as equivalence closure", cs(FX + "graded_closure.metta") + ":3 (GradedClosure, G02)"),
 (r"sensitivity certificate", cs(FX + "skill_hive.metta") + ":3 (CheckValuePullback, K02)"),
 (r"affine residuals", cs(FX + "affine_contracts.metta") + ":3 (A03)"),
 (r"unavailable report", cs(FX + "availability.metta") + ":3 (Availability, W01/W02)"),
 (r"script's depth|rho-calculus", cs("repos/cetta/scripts/rhocalc_bounded_bisimulation.py") + " and tests/rhocalc_bisimulation.tsv (CeTTa @12da03b4)"),
]
for mid, title in MS:
    x, a, b = section_range(title)
    p0 = page_of(title.split(":", 1)[1].strip()[:40], 15)
    nxt = MS[[m for m, _ in MS].index(mid) + 1][1].split(":", 1)[1] if mid != "M7" else "Golden results and adversarial mutations"
    p1 = page_of(nxt.strip()[:40], p0 or 15)
    w(f"## {title} (§{x[2]}, {pref(p0)} to {pref(p1)})\n")
    body = tex_lines(a + 1, b)
    w("### Text of the milestone (verbatim)\n")
    w(quote(convert(body)) + "\n")
    w("### Scope\n")
    if mid == "M0":
        w("The six numbered boundaries above, plus: \"On the computational side M0 covers the core requests these boundaries touch, on enumerated deterministic modules: " + ", ".join(cs(r) for r in ["MeasureNow", "CheckNow", "CheckUpdates", "InduceExact", "CheckAbstractionMap"]) + " and " + cs("Then") + " [...] Every other request returns Unsupported or, when a binding rule fails, InvalidInput.\"\n")
    else:
        m = re.search(r"\\emph\{Deliverables\.\}(.*?)(?=\\emph\{(Acceptance|Claims)\.)", "\n".join(body), re.S)
        w(quote(convert(m.group(1).split("\n"))) + "\n")
    w("### Acceptance claims\n")
    if mid == "M1":
        w("No manifest claims of its own. Acceptance is the *Acceptance* paragraph above; its evidence includes \"the Unsupported answers for the $78$ claims outside the first release\" (Appendix A, R1 = no).\n")
    else:
        ids = plan_ids[mid]
        w(f"Plan list: **{PLAN_CLAIMS[mid]}** ({len(ids)} claims, {sum(byid[i]['release1']=='Supported' for i in ids)} of them Supported in release 1).\n")
        claims_table(ids)
    w("### Negative tests\n")
    if mid == "M0":
        w("The negative acceptance suite is M0's acceptance (the ten numbered entries of the text above). Fixture locations, found by search in docs/ **[assigned]**:\n")
        for k, v in NEG_POINTERS.items(): w(f"{k}. {v}")
        w("")
    else:
        m = re.search(r"\\emph\{Negative gates\.\}(.*?)(?=\\emph\{|\Z)", "\n".join(body), re.S)
        if m:
            text = convert(m.group(1).split("\n")).replace("\n", " ")
            sents = [s_.strip() for s_ in re.split(r"(?<=[.)])\s+(?=[A-Z])|;\s+(?=[a-z])", text) if s_.strip()]
            for i, s_ in enumerate(sents, 1):
                ids = [cid for cid in re.findall(r"\b([A-Z]\d\d)\b", s_) if cid in byid]
                rng = re.findall(r"\b([A-Z]\d\d)[–-]([A-Z]\d\d)\b", s_)
                for a_, b_ in rng: ids += expand(f"{a_}-{b_[1:]}")
                ids = list(dict.fromkeys(ids))
                if ids:
                    locs = []
                    for cid in ids:
                        f, ml, rl = fixture_loc(byid[cid]); locs.append(f"{cid} {cs(f)}:{rl}")
                    ptr = " — fixtures: " + ", ".join(locs)
                else:
                    kw = [v for k, v in KEYWORDS if re.search(k, s_)]
                    if kw: ptr = " — fixture **[assigned by keyword]**: " + "; ".join(kw)
                    else: ptr = " — fixture: none named in the plan or the package (a mutation to build under " + cs("tests/dcalc/mutations/") + ")"
                w(f"{i}. \"{s_}\"{ptr}")
            w("")
        else:
            w("No *Negative gates* paragraph. The *Acceptance* paragraph above is the negative test: admission must reject the mutations " + cs("check_fixtures.py") + " rejects.\n")
    w("### Dependencies on earlier milestones and pins\n")
    w(DEPS[mid] + "\n")
    w("### Algorithms (§1.9, verbatim) **[assigned to milestones]**\n")
    hits = [it for it in alg_full if mid in ALG_MS.get((re.match(r"\\emph\{(.*?)\}", it) or [None, ""])[1], [])]
    for it in hits: w("- " + inline(it))
    if not hits: w("- none of the §1.9 bullets is specific to this milestone")
    w("")
    w("### Certificate formats (Table 1, §1.7, verbatim rows) **[assigned to milestones]**\n")
    rows = [r for r in cert_rows if CERT_MS.get(r[0]) == mid]
    if rows:
        w("| Claim | Certificate | Replay |"); w("|---|---|---|")
        for r in rows: w("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |")
    else: w("none")
    w("")

for t in ["Golden results and adversarial mutations", "Handoff and definition of done"]:
    x, a, b = section_range(t)
    if t.startswith("Golden"):
        body = tex_lines(a + 1, find_line("{\\scriptsize", a) - 1) + tex_lines(find_line("\\end{longtable}", a) + 1, b)
    else:
        body = tex_lines(a + 1, find_line("\\begin{thebibliography}", a) - 1)
    w(f"## {t} (§{x[2]}, {pref(page_of(t, 20))})\n")
    if t.startswith("Golden"): w("(The guide's manifest table, Table 2, is omitted here; Appendix A regenerates it from manifest.json with fixture locations.)\n")
    w(quote(convert(body)) + "\n")

unmapped = [r[0] for r in cert_rows if r[0] not in CERT_MS]
w("## Appendix A: the 123 claims\n")
w(f"Certificate rows of Table 1 not assigned to a milestone: {unmapped or 'none'}.\n")
claims_table([c["id"] for c in claims])
nf = [c["id"] for c in claims if not fixture_loc(c)[2]]
w(f"Request lines not found in the fixture: {nf or 'none'}.\n")
open(OUT, "w").write("\n".join(o) + "\n")
print("wrote", OUT, len(o), "lines; cert rows", len(cert_rows), "alg", len(alg_full), "unmapped certs", unmapped, "nf", nf)
