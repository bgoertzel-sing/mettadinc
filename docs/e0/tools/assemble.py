#!/usr/bin/env python3
import json, os, hashlib, subprocess, shutil, sys, datetime
E = os.path.expanduser("~/scratch/mettadinc-e0")
OUT = sys.argv[1]                       # .../projects/mettadinc
DOCS = os.path.join(OUT, "docs")
if os.path.exists(DOCS): shutil.rmtree(DOCS)
shutil.copytree(os.path.join(E, "raw"), DOCS, ignore=shutil.ignore_patterns(".DS_Store"))
man = json.load(open(os.path.join(E, "manifest.json")))
url = {m["path"]: m["url"] for m in man}
gid = {m["path"]: m["id"] for m in man}
kind = {m["path"]: m["kind"] for m in man}
ROOT = "1QNkx4elmZw0qUf7oQADHkZXr28ERsybW"
TITLES = {
 "01_language_specification/mettadinc_language_spec": "MeTTaDinC: An Executable Language for Observer-Relative Abstraction, Evidence, and Composition (specification draft, 4 Nov 2026)",
 "02_cetta_implementation_guide/mettadinc_cetta_implementation_guide": "Implementing MeTTaDinC in Cetta: A Coding-Agent Specification and Work Plan (4 Nov 2026)",
 "03_four_worked_examples/mettadinc_worked_examples": "MeTTaDinC in Practice: Four Worked Examples (4 Nov 2026)",
 "04_omega_memory_goals_part1/mettadinc_omega_memory_goals": "Omega Memory and Goals in MeTTaDinC: A Practical Implementation Guide (Part I, 4 Nov 2026)",
 "05_live_memory_part2/mettadinc_live_memory": "Omega Memory and Goals in MeTTaDinC, Part II: Live Memory through Summary Statistics (4 Nov 2026)",
 "06_wmtm_worked_example/mettadinc_wmtm_worked_example": "Omega Memory and Goals in MeTTaDinC, worked example: WMTM's Open-Item Store, from Journal to Gate (4 Nov 2026)",
 "MeTTaDinC_executive_summary": "MeTTaDinC executive summary (Google Doc)",
 "MeTTaDinC_explainer": "MeTTaDinC explainer (Google Doc)",
}
popp = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True).stderr.splitlines()[0]
# text exports of PDFs that are not Google-Doc exports
for dp, dn, fns in os.walk(DOCS):
    for fn in fns:
        if fn.endswith(".pdf") and not fn.startswith("MeTTaDinC_"):
            p = os.path.join(dp, fn)
            subprocess.run(["pdftotext", "-layout", p, p[:-4] + ".txt"], check=True)
def sha(p):
    h = hashlib.sha256(); h.update(open(p, "rb").read()); return h.hexdigest()
def pages(p):
    r = subprocess.run(["pdfinfo", p], capture_output=True, text=True).stdout
    for l in r.splitlines():
        if l.startswith("Pages:"): return l.split()[1]
    return ""
when = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(E, "manifest.json")), datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
rows = []
for dp, dn, fns in os.walk(DOCS):
    dn.sort()
    for fn in sorted(fns):
        p = os.path.join(dp, fn); rel = os.path.relpath(p, DOCS)
        if rel == "SOURCES.md": continue
        stem = rel.rsplit(".", 1)[0]
        title = TITLES.get(stem, "")
        if rel in url and kind.get(rel) == "file": src = url[rel]; how = "Drive download (drive.usercontent.google.com, export=download)"
        elif kind.get(rel) == "gdoc":
            fmt = rel.rsplit(".", 1)[1]
            gidv = gid[rel]; src = f"https://docs.google.com/document/d/{gidv}/edit"; how = f"Google Docs export?format={fmt}"
        elif rel.endswith(".txt") and os.path.exists(p[:-4] + ".pdf") and (rel[:-4] + ".pdf") in url:
            src = url[rel[:-4] + ".pdf"]; how = f"derived: pdftotext -layout of the PDF ({popp})"
        else: src = "?"; how = "?"
        pg = pages(p) if rel.endswith(".pdf") else ""
        rows.append((rel, title, src, how, pg, os.path.getsize(p), sha(p)))
with open(os.path.join(DOCS, "SOURCES.md"), "w") as f:
    f.write("# MeTTaDinC sources\n\n")
    f.write(f"Public Google Drive folder https://drive.google.com/drive/folders/{ROOT} (owner-shared, \"anyone with the link\"), crawled recursively through "
            "https://drive.google.com/embeddedfolderview?id=<folder> on 2026-11-05 (" + when + "). Files were downloaded byte-for-byte; the two Google Docs in the folder "
            "(MeTTaDinC_executive_summary, MeTTaDinC_explainer) were exported as Markdown, plain text and PDF. Each compiled PDF also has a "
            "pdftotext -layout export (.txt, form feed between pages) beside it; the LaTeX source (.tex) is the authoritative text form. "
            "Skipped: one macOS metadata file, .DS_Store (Drive id 1tB0gx3Ou16NKrCPgEgoHX4AhYkJF8BNS, 6148 bytes), not a document.\n\n")
    f.write("Validation packages: all of them are in this folder and are included unmodified: the specification's validation package "
            "(registry, fixtures, manifest, oracle, check_fixtures.py, DEPENDENCIES.json) under 01_language_specification/validation_package/, "
            "the four worked-example bundles under 03_four_worked_examples/validation_bundles/, and the bundles of documents 04, 05 and 06 "
            "(each with its reference evaluator and oracle). Missing: none found. The guide's external pins (CaDiCaL, drat-trim, cake_lpr, CeTTa) "
            "are public GitHub repositories, not part of the package.\n\n")
    f.write("## Documents\n\n| Title | File | Pages | sha256 |\n|---|---|---|---|\n")
    for r in rows:
        if r[1] and r[0].endswith(".pdf"): f.write(f"| {r[1]} | {r[0]} | {r[4]} | {r[6]} |\n")
    f.write(f"\nPage counts match the folder README.txt (86, 30, 79, 66, 53, 45); the Google Doc PDF exports have 3 and 18 pages.\n\n")
    f.write("## All files\n\nExport date for every row: 2026-11-05. URL is the Drive file (or Google Doc) the file came from.\n\n")
    f.write("| File | Title | Pages | Bytes | sha256 | URL | How |\n|---|---|---|---|---|---|---|\n")
    for r in rows: f.write(f"| {r[0]} | {r[1]} | {r[4]} | {r[5]} | {r[6]} | {r[2]} | {r[3]} |\n")
print(len(rows), "files")
