from pathlib import Path
import json,hashlib,random,zipfile
import numpy as np
D=Path('C:/dev/owalnuts/target/posterior-bank-analysis-design/grid-probe-v1');r=json.loads((D/'result.json').read_text());c=json.loads((D/'config.json').read_text());checks={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for p,h in c['bindings'].items():checks['binding:'+p]=sha(p)==h
checks['config_hash']=sha(D/'config.json')==r['config_sha256'];checks['weights_hash']=sha(D/'frozen-weights.npy')==r['weights_sha256']
w=np.load(D/'frozen-weights.npy');rng=random.Random(731);expected=[]
for _ in range(30000):
 k=sum(rng.randrange(2)==0 for j in range(2));expected.extend([[k,0,2-k,0],[0,k,0,2-k]])
expected.extend([[1,0,1,0],[0,1,0,1],*np.eye(4,dtype=int).tolist()]);checks['exact_fixed_paired_weights']=np.array_equal(w,expected)
rows=list(r['rows'].values());grid=np.array(rows[0]['grid']);checks['common20grid']=len(grid)==20 and all(x['grid']==grid.tolist() for x in rows)
checks['estimated_not_verified']=all(x['error_bound_verified'] is False for x in rows) and r['all_weight_vectors_verified'] is False
unique=np.unique(w/w.sum(axis=1,keepdims=True),axis=0);intervals=[]
for weight in unique:
 f=sum(v*np.array(row['cdf']) for v,row in zip(weight,rows));err=sum(v*row['numerical_cdf_error_estimate'] for v,row in zip(weight,rows))
 for p in [.05,.95]:
  lo=np.flatnonzero(f+err<p);hi=np.flatnonzero(f-err>=p);assert len(lo) and len(hi)
  lower=float(grid[lo[-1]]);upper=float(grid[hi[0]]);intervals.append(dict(weights=weight.tolist(),probability=p,bracket=[lower,upper],width=upper-lower))
checks['all_actual_weight_brackets']=all(0<=x['width']<=.01 for x in intervals)
checks['declared_resolution']=r['declared_weight_brackets_resolved'] is True and r['orders']==[16,32,64,128]
h=json.loads((D/'hardware.json').read_text());checks['contained_cpu0_exit']=h['returncode']==0 and h['status']=='completed' and h['realized_cpus']==[0] and h['job_active_processes_after_cleanup']==0 and h['containment']['assigned_before_worker_execution']
out=dict(integrity_pass=all(checks.values()),checks=checks,unique_counts=len(np.unique(w,axis=0)),unique_normalized_weights=len(unique),all60006_rows_checked_via_exact_duplicate_reduction=True,brackets=intervals,max_bracket_width=max(x['width'] for x in intervals),seconds=r['seconds'],wrapper_seconds=h['elapsed_seconds'],limitations=['Two reference fits only, paired4000/8000 prefixes; no posterior sampling or accuracy claim.','Full16/32/64/128 evaluations established by pinned executed source, but saved output retains only order128 CDF rows and aggregate final-two-difference estimates. Earlier-order values were not archived, so the tiny error estimates cannot be independently recomputed from this artifact.','No certified quadrature error bound; .01 raw-unit grid width applies only to these actual frozen weights. Larger-bank cost/generalization unproven.'])
with (D/'independent-audit.json').open('x') as f:json.dump(out,f,indent=2)
with zipfile.ZipFile(D/'independent-source.zip','x',zipfile.ZIP_DEFLATED) as z:
 for p in c['bindings']:
  if p.endswith('.py'):z.write(p,Path(p).name)
print(json.dumps(dict(pass_=out['integrity_pass'],maxwidth=out['max_bracket_width'],unique=out['unique_normalized_weights'],checks=len(checks))))
