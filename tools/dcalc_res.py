#!/usr/bin/env python3
"""Review 2 F8: resource record for one dcalc-run-all step.
Usage: dcalc_res.py NAME CMD   (CMD runs under sh -c; its exit code is returned)
Appends one TSV row to build/dcalc-resources.tsv:
step  exit  wall_s  user_s  sys_s  max_rss_kib   (CPU and RSS of all child processes)."""
import os, resource, subprocess, sys, time
name, cmd = sys.argv[1], sys.argv[2]
t0 = time.time(); rc = subprocess.call(['sh', '-c', cmd]); wall = time.time() - t0
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
os.makedirs('build', exist_ok=True)
path = 'build/dcalc-resources.tsv'
new = not os.path.exists(path)
with open(path, 'a') as f:
    if new: f.write('step\texit\twall_s\tuser_s\tsys_s\tmax_rss_kib\n')
    f.write('%s\t%d\t%.1f\t%.1f\t%.1f\t%d\n' % (name, rc, wall, ru.ru_utime, ru.ru_stime, ru.ru_maxrss))
print('resource %s: exit %d, wall %.1f s, user %.1f s, sys %.1f s, max RSS %d KiB' % (name, rc, wall, ru.ru_utime, ru.ru_stime, ru.ru_maxrss))
sys.exit(rc)
