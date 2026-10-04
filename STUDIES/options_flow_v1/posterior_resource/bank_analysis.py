"""Prospective actual-posterior bank analysis; no sampling API."""
import argparse,hashlib,json,random,sys,time
from pathlib import Path
START=time.perf_counter();CPU=time.process_time()
LENGTHS=(4000,8000)

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()

def save(path,value):
 from run import clean
 with Path(path).open('x') as f:json.dump(clean(value),f,indent=2,allow_nan=False)

def frozen_counts(fits,seed,repeats):
 from reference_bank import resample_fits
 rng=random.Random(seed)
 return [resample_fits(fits,rng) for _ in range(repeats)]

def weight_contract(fits,counts):
 import numpy as np
 ids=[f['id'] for f in fits];backends=sorted({f['backend'] for f in fits});columns=[f'{k}@{n}' for k in ids for n in LENGTHS]
 groups=[(ids,8000),(ids,4000)]+[([f['id'] for f in fits if f['backend']==b],8000) for b in backends]
 matrix=np.zeros((4*(len(counts)+1),len(columns)),dtype='<f8')
 for replicate,c in enumerate([dict.fromkeys(ids,1),*counts]):
  for gi,(members,n) in enumerate(groups):
   row=matrix[replicate*4+gi]
   for k in members:row[columns.index(f'{k}@{n}')]=c.get(k,0)
   row/=row.sum()
 return columns,matrix,hashlib.sha256(matrix.tobytes(order='C')).hexdigest()

def validate_policy(p):
 required=dict(timeout_seconds=7200,cleanup_reserve_seconds=15,memory_bytes=8*1024**3,cpus=[0],bootstrap_replicates=30000,minimum_tail_count=20,alpha=.05,relative_half_width=.1,backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1,max_queries=64,max_rounds=32,absolute_width=.01,cdf_tolerance=1e-8)
 if any(p.get(k)!=v for k,v in required.items()) or p['orders']!=[16,32,64,128]:raise ValueError('Exact prospective analysis policy differs')
 if type(p['bootstrap_seed']) is not int or not 0<=p['bootstrap_seed']<2**32:raise ValueError('Explicit audited bootstrap seed required')
 if p['initial_grid']!=[-4.,4.]:raise ValueError('Fixed initial grid required')

def verify(p):
 if any(sha(path)!=h for path,h in p['bindings'].items()):raise ValueError('Analysis source/input binding changed')

def analyze_plan(path):
 path=Path(path).resolve();p=json.loads(path.read_text());digest=sha(path);out=Path(p['out']);out.mkdir(exist_ok=False);sys.path.insert(0,p['study'])
 from reference_bank_allocation import memory_limit,peak_memory
 result=dict(status='unresolved',qualified=False,reference_bank_resolved=False,expected_fits=64);phase='admission';pt=time.perf_counter();guard=None
 try:
  validate_policy(p);guard=memory_limit(p['memory_bytes']);verify(p)
  if path.with_suffix('.sha256').read_text().strip()!=digest:raise ValueError('Frozen analysis plan required')
  from hardware_control import get_affinity
  if get_affinity()!=[0]:raise ValueError('Required CPU0 not realized')
  import numpy as np
  from posterior_resource.bank_adapter import collect,PARAMETERS
  from posterior_resource.predictive_grid import build
  from predictive_cdf import PredictiveMixture
  from reference_bank import analyze
  from reference_bank_vectorized import batch_cached_parameter
  from .bank_analysis_preparation import verify_materialized
  verify_materialized(p)
  manifest=json.loads(Path(p['admission_manifest']).read_text())
  if any('materialization_error' in row for row in manifest['fits']):
   result['outcomes']=[dict(id=row['id'],status='materialization_failed' if 'materialization_error' in row else 'not_analyzed_due_to_incomplete_bank',error=row.get('materialization_error')) for row in manifest['fits']]
   raise ValueError('Incomplete bank materialization; no successful subset permitted')
  admission=collect(manifest);result['outcomes']=admission['outcomes']
  save(out/'admission.json',{k:v for k,v in admission.items() if k!='admitted'})
  if len(admission['admitted'])!=64:raise ValueError('All64 fresh fits must be admitted; no survivor subset')
  fitted=admission['admitted'];counts=frozen_counts(fitted,p['bootstrap_seed'],30000);columns,weights,weight_sha=weight_contract(fitted,counts)
  if p['expected_weight_sha256']!=weight_sha or p['ordered_ids']!=[f['id'] for f in fitted]:raise ValueError('Frozen bootstrap order/count digest differs')
  np.save(out/'frozen-weights.npy',weights,allow_pickle=False)
  fixture=json.loads(Path(manifest['fits'][0]['fixture']).read_text());mixtures={}
  for fit in fitted:
   for n in LENGTHS:
    x=fit['predictive_inputs'][str(n)];size=4*n
    mixtures[f"{fit['id']}@{n}"]=PredictiveMixture('flow',x['cdf_location'].reshape(-1),x['cdf_future_mean'].reshape(-1),x['cdf_future_sd'].reshape(-1),np.zeros(size),np.full(size,1/size),fixture['data']['nu'],2048,dict(group=0,horizon=1,x_next=fixture['holdout']['x'][0][0]))
  if list(mixtures)!=columns:raise ValueError('Grid column order differs')
  phase='common_grid';pt=time.perf_counter()
  grid=build(mixtures,initial=tuple(p['initial_grid']),probabilities=(.05,.95),max_queries=64,max_rounds=32,absolute_width=.01,cdf_tolerance=1e-8,frozen_weights=weights)
  save(out/'common-grid.json',grid);result['grid_seconds']=time.perf_counter()-pt;result['grid_status']=grid['status']
  if grid['status']!='numerically_resolved_for_declared_scenarios' or grid['frozen_weights_sha256']!=weight_sha or grid['ordered_ids']!=columns or grid['declared_weight_brackets_resolved'] is not True:raise ValueError('Common grid cap or quadrature unresolved')
  records=[];definitions={};pairs=[]
  for name in (*PARAMETERS,'observed_group0_h1'):
   pair=[]
   for probability in (.05,.95):
    key=f'{name}_{probability}';pair.append(key);definitions[key]=dict(kind='predictive' if name=='observed_group0_h1' else 'parameter',probability=probability,scale='native',distribution_id=name)
   pairs.append(pair)
  for fitted_row,spec in zip(fitted,manifest['fits']):
   record=dict(id=fitted_row['id'],backend=fitted_row['backend'],seed=spec['sampler_seed'],initialization_seed=spec['initialization_seed'],fixture_sha256=spec['fixture_sha256'],source_sha256=p['bank_source_sha256'],target_sha256=manifest['posterior_sha256'],levels={})
   for n in LENGTHS:
    rows={}
    for name in (*PARAMETERS,'observed_group0_h1'):
     base=dict(grid['rows'][f"{fitted_row['id']}@{n}"]) if name=='observed_group0_h1' else dict(draws=fitted_row['parameters'][str(n)][name].reshape(-1).tolist())
     base.update(scale='native',distribution_id=name)
     for probability in (.05,.95):rows[f'{name}_{probability}']=base
    record['levels'][str(n)]=dict(status='completed',healthy=True,draws_per_chain=n,endpoints=rows)
   records.append(record)
  spec=dict(fits=[{k:v for k,v in r.items() if k!='levels'} for r in records],source_sha256=p['bank_source_sha256'],target_sha256=manifest['posterior_sha256'],lengths=list(LENGTHS),chains=4,endpoints=definitions,interval_pairs=pairs,numerical_policy='validated_estimate',candidate_streams=[],**{k:p[k] for k in ['bootstrap_replicates','minimum_tail_count','bootstrap_seed','alpha','relative_half_width','backend_equivalence_relative_width','length_equivalence_relative_width']})
  seen=[];callback_calls=0
  def batch(*args):
   nonlocal callback_calls
   callback_calls+=1
   actual=args[-1]
   if not seen:
    if actual!=counts:raise ValueError('Analyzer whole-fit resamples differ from grid weights')
    seen.append(actual)
   elif actual is not seen[0]:raise ValueError('Analyzer discarded shared count object')
   return batch_cached_parameter(*args)
  phase='joint_bootstrap';pt=time.perf_counter();bank=analyze(spec,records,parameter_batch=batch)
  save(out/'bank-result.json',bank)
  if callback_calls!=40:raise ValueError('Expected40 parameter callbacks across12endpoint family')
  result['bootstrap_seconds']=time.perf_counter()-pt
  result.update(status=bank['status'],reference_bank_resolved=bank['status']=='numerically_resolved_under_declared_checks',weight_sha256=weight_sha,finite_bank_limitation='32fits/backend whole-fit bootstrap is approximate; no accuracy/coverage qualification')
  verify(p)
  result['integrity_pass']=True
  if sha(path)!=digest:raise ValueError('Frozen analysis plan changed')
 except Exception as exc:result.update(status='unresolved',reference_bank_resolved=False,integrity_pass=False,error=f'{type(exc).__name__}: {exc}')
 finally:
  result.update(last_phase=phase,last_phase_elapsed_seconds=time.perf_counter()-pt,worker_seconds_before_final_report=time.perf_counter()-START,process_cpu_seconds=time.process_time()-CPU,resources=peak_memory());save(out/'analysis-result.json',result)
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();r=analyze_plan(a.plan);raise SystemExit(0 if r['reference_bank_resolved'] else 2)
