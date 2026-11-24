#!/usr/bin/env python3
"""Byte-diff gate for t-2026-11-23-mettadinc-m0-like-machines (acceptance 2).

Runs build/dcalc/dcalc (or $DCALC) on every git-tracked .metta file, alone, from the file's own
directory, in release mode and with --beyond-release, and writes one file per (path, mode) with
stdout, stderr and the exit code into OUTDIR.  'compare A B' lists every (path, mode) whose bytes
differ between two such runs; files present in only one run are listed separately.

    python3 tests/dcalc/m0_like/metta_bytediff.py run OUTDIR
    python3 tests/dcalc/m0_like/metta_bytediff.py compare OUTDIR_BEFORE OUTDIR_AFTER
"""
import hashlib, os, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DC = os.path.abspath(os.environ.get('DCALC', os.path.join(ROOT, 'build', 'dcalc', 'dcalc')))
MODES = (('release', []), ('beyond', ['--beyond-release']))

def run(out):
    os.makedirs(out, exist_ok=True)
    files = subprocess.run(['git', 'ls-files', '*.metta'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for rel in files:
        d, f = os.path.split(os.path.join(ROOT, rel))
        for tag, args in MODES:
            try:
                o = subprocess.run([DC] + args + [f], cwd=d, capture_output=True, timeout=300)
                body = b'EXIT %d\n--stdout--\n' % o.returncode + o.stdout + b'--stderr--\n' + o.stderr
            except subprocess.TimeoutExpired:
                body = b'TIMEOUT\n'
            with open(os.path.join(out, rel.replace('/', '__') + '.' + tag), 'wb') as fh:
                fh.write(body)
    print('ran %d files x %d modes with %s' % (len(files), len(MODES), DC))

def compare(a, b):
    fa, fb = set(os.listdir(a)), set(os.listdir(b))
    changed = []
    for n in sorted(fa & fb):
        if open(os.path.join(a, n), 'rb').read() != open(os.path.join(b, n), 'rb').read():
            changed.append(n)
    for n in changed: print('CHANGED', n)
    for n in sorted(fa - fb): print('ONLY-BEFORE', n)
    for n in sorted(fb - fa): print('ONLY-AFTER', n)
    print('compared %d outputs: %d changed, %d only before, %d only after' % (len(fa & fb), len(changed), len(fa - fb), len(fb - fa)))
    return changed

if __name__ == '__main__':
    if sys.argv[1] == 'run': run(sys.argv[2])
    else: compare(sys.argv[2], sys.argv[3])
