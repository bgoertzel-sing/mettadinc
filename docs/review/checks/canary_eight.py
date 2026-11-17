# Sanity-gate canary: my checker must REFUSE a tampered envelope (drop one kernel entry, flip a defect).
import re, subprocess, sys, shutil
SRC='/hive/protomega/work/cetta-src/mettadinc/build/dcalc/out/eight_state.out'
lines=open(SRC).read().split('\n')
i=[k for k,l in enumerate(lines) if l.startswith('EightState (Defects KeepA) =>')][0]
muts={'drop_entry': lambda l: l.replace('(Entry (Tuple 1 0 1) (Tuple 1 1 1) 1)','',1),
      'flip_update': lambda l: l.replace('(Update (Interval 1 1))','(Update (Interval 0 0))',1),
      'bad_witness': lambda l: l.replace('(UpdateWitness (Pair (Tuple 0 0 0) (Tuple 0 1 0))','(UpdateWitness (Pair (Tuple 0 0 0) (Tuple 0 0 1))',1)}
bad=0
for name,f in muts.items():
    L=list(lines); L[i]=f(L[i]); assert L[i]!=lines[i], name
    open('/tmp_eight.out' if False else 'mut_eight.out','w').write('\n'.join(L))
    r=subprocess.run([sys.executable,'check_eight.py','mut_eight.out'],capture_output=True,text=True)
    print(name,'checker exit',r.returncode,'(must be 1)'); bad += r.returncode!=1
print('CANARY', 'PASS' if not bad else 'FAIL'); sys.exit(bad)
