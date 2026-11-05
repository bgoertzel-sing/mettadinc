
import json,os
A='/home/openclaw/scratch/mettadinc-e0/raw'; B='/home/openclaw/scratch/mettadinc-e0/runs/oracles/pkg'
fs=['03_four_worked_examples/validation_bundles/ex1_belief_memory/ex1_results.json','03_four_worked_examples/validation_bundles/ex2_access_policy/ex2_results.json','03_four_worked_examples/validation_bundles/ex3_skill_share/ex3_results.json','03_four_worked_examples/validation_bundles/ex4_market_maker/ex4_results.json','04_omega_memory_goals_part1/validation_bundle/mg_results.json','05_live_memory_part2/validation_bundle/ls_results.json','06_wmtm_worked_example/validation_bundle/wx_results.json']
def walk(a,b,path,out):
    if type(a)!=type(b): out.append((path,repr(a)[:80],repr(b)[:80])); return
    if isinstance(a,dict):
        for k in set(a)|set(b):
            if k not in a or k not in b: out.append((path+'/'+k,'missing' if k not in a else 'present','missing' if k not in b else 'present'))
            else: walk(a[k],b[k],path+'/'+str(k),out)
    elif isinstance(a,list):
        if len(a)!=len(b): out.append((path,'len %d'%len(a),'len %d'%len(b))); return
        for i,(x,y) in enumerate(zip(a,b)): walk(x,y,path+'[%d]'%i,out)
    elif a!=b: out.append((path,repr(a)[:80],repr(b)[:80]))
for f in fs:
    out=[]; walk(json.load(open(os.path.join(A,f))),json.load(open(os.path.join(B,f))),'',out)
    print(f.split('/')[-1], len(out), 'diffs')
    for d in out[:4]: print('   ',d)
