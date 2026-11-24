#!/usr/bin/env python3
"""Which gaps still block doc04 AnchorMigration (rows 43-44) and TaskResume (rows 45-49) once If/Eq/And/Or/Not are
lowered (t-2026-11-23-mettadinc-m0-cases-logic).  Starts from doc04's text (memory_goals.metta excerpts) and applies
every subset of the rewrites that tests/dcalc/m0_cases_logic/make_doc04_logic.py uses, then runs dcalc (release mode).
Usage: ablation.py DCALC"""
import itertools, os, re, subprocess, sys, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SRC = os.path.join(ROOT, 'docs', 'e0', 'docs', '04_omega_memory_goals_part1', 'validation_bundle', 'memory_goals.metta')
DC = sys.argv[1]
text = open(SRC).read()
ex = lambda n: re.search(r';; @excerpt %s\n(.*?);; @end' % re.escape(n), text, re.S).group(1)
def sub(s, old, new):
    assert s.count(old) == 1, old
    return s.replace(old, new)
am, tr = ex('anchor-migration'), ex('task-resume')
ports = ' '.join(re.search(r'\(Machine Restart \(States Task\)(.*?)\)\n  \(Carrier Live', tr, re.S).group(1).split())
AM = {'bool-observe map with type-form From (live-old/live-new -> From OldAll/NewAll)':
          [('(Map live-old (From (Tuple Symbol Symbol)) (To Bool)', '(Map live-old (From OldAll) (To Bool)'),
           ('(Map live-new (From (Tuple Symbol Symbol)) (To Bool)', '(Map live-new (From NewAll) (To Bool)')],
      '(f) Body map lesion -> Cases': [('(Body ($x) (Tuple absent none))', '(Cases ((Tuple $g $l) (Tuple absent none)))')]}
TR = {'(d) Machine Like -> ports copied': [('(Machine Resume (States Live) (Like Restart))', '(Machine Resume (States Live) %s)' % ports)],
      '(f) Body map checkpoint-with-reads -> Cases': [('(Body ($x) $x)', '(Cases ((Tuple $v1 $v2 $r $f) (Tuple $v1 $v2 $r $f)))')]}
def run(src, reqs):
    t = tempfile.NamedTemporaryFile('w', suffix='.metta', delete=False); t.write(src + '\n'.join(reqs) + '\n'); t.close()
    o = subprocess.run([DC, t.name], capture_output=True, text=True, timeout=300).stdout; os.unlink(t.name)
    res = []
    for l in o.splitlines():
        if ' => ' not in l: continue
        st = re.search(r'\(Status ([A-Za-z]+)\)', l).group(1); rs = re.search(r'\(Reason "([^"]*)"', l)
        res.append('%s %s%s' % (l.split(' => ')[0].split(' ', 1)[1], st, (' -- ' + rs.group(1)) if rs else ''))
    return res
for name, body, fixes in (('AnchorMigration', am, AM), ('TaskResume', tr, TR)):
    reqs = [l for l in ex(name.replace('AnchorMigration', 'anchor-migration').replace('TaskResume', 'task-resume') + '-requests').splitlines() if l.startswith('!(dc.run')]
    keys = list(fixes)
    for k in range(len(keys) + 1):
        for chosen in itertools.combinations(keys, k):
            s = body
            for c in chosen:
                for old, new in fixes[c]: s = sub(s, old, new)
            print('== %s, rewritten: %s' % (name, '; '.join(chosen) if chosen else 'nothing (doc04 as written)'))
            for line in run(s, reqs): print('   ' + line)
