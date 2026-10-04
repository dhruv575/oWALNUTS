"""Prospective28-cell resource study. No default seeds; no automatic freeze.

Worker reuses allocation.cell_worker (memory cap, same generator/bootstrap) and
hardware_control containment. New data are not posterior fits. Prefix estimates
are descriptive and cannot select a different primaryN8192.
"""
import argparse,hashlib,json,os,subprocess,sys,time,importlib.metadata,math
from pathlib import Path

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
def make_plan(seeds,study,python,seed_audit):
 if len(seeds)!=3612 or len(set(seeds))!=3612 or any(type(s)!=int or not 0<=s<2**32 for s in seeds):raise ValueError('Explicit3612unique uint32 seeds required; audit separately before freeze')
 study=Path(study).resolve();cells=[];cursor=0
 configs=[('sentinel',r,s,i) for i,(r,s) in enumerate([(0.,0.),(.9,0.),(.9,.1),(.9,.5)])]+[('main',r,s,i) for r,s,count in [(.9,0.,12),(0.,0.,4),(.9,.1,4),(.9,.5,4)] for i in range(count)]
 for phase,rho,shift,index in configs:
  ss=seeds[cursor:cursor+129];cursor+=129;cells.append(dict(id=f'{phase}-rho{rho}-shift{shift}-{index}',phase=phase,fits_per_backend=32,lengths=[4096,8192],rho=rho,backend_b_shift=shift,fit_seeds=ss[:64],init_seeds=ss[64:128],bootstrap_seed=ss[-1]))
 source={f.name:sha(f) for f in study.glob('*.py')}
 return dict(frozen=False,qualified=False,cells=cells,expected=28,implementation='vectorized',study=str(study),python=str(Path(python).resolve()),python_sha256=sha(python),runtime={n:importlib.metadata.version(n) for n in ['numpy','scipy']},source=source,seed_audit=dict(path=str(Path(seed_audit).resolve()),sha256=sha(seed_audit)),own_source={str(Path(__file__).with_name(n).resolve()):sha(Path(__file__).with_name(n)) for n in ['correlated_reference_study.py','gaussian_ar_indicator.py']},wall_seconds=3600,cleanup_reserve_seconds=15,memory_bytes=2*1024**3,bootstrap_replicates=30000,minimum_tail_count=20,alpha=.05,relative_half_width=.1,backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1,prefixes=[1024,4096,8192],progression=dict(correlated_null=dict(intended=12,minimum_resolved=9,minimum_both_covered=11,maximum_resolved_miss=0),iid_null=dict(intended=4,minimum_resolved=3,minimum_both_covered=4,maximum_resolved_miss=0),shift_01=dict(intended=4,maximum_resolved=0),shift_05=dict(intended=4,maximum_resolved=0)),projection='Maximum four sentinel fullworker costs times24times4; failclosed if exceeds remaining-minus15',limitation='Exploratory progression only; fixed primary8192. Analytic covariance exact forGaussianAR indicators, delta quantilevariance approximate. Nextstage one actualposteriorbank with achieveduncertainty, not another automaticanalyticexpansion.')
def validate(p):
 configurations=[('sentinel',r,s,i) for i,(r,s) in enumerate([(0.,0.),(.9,0.),(.9,.1),(.9,.5)])]+[('main',r,s,i) for r,s,count in [(.9,0.,12),(0.,0.,4),(.9,.1,4),(.9,.5,4)] for i in range(count)]
 if p['expected']!=28 or len(p['cells'])!=28:raise ValueError('Exact28cell denominator required')
 streams=[]
 for c,(phase,rho,shift,index) in zip(p['cells'],configurations):
  if c['id']!=f'{phase}-rho{rho}-shift{shift}-{index}' or c['phase']!=phase or c['rho']!=rho or c['backend_b_shift']!=shift or c['fits_per_backend']!=32 or c['lengths']!=[4096,8192] or len(c['fit_seeds'])!=64 or len(c['init_seeds'])!=64:raise ValueError('Exact fixed schedule/shape required')
  streams+=c['fit_seeds']+c['init_seeds']+[c['bootstrap_seed']]
 if len(streams)!=3612 or len(set(streams))!=3612 or any(type(x)!=int or not 0<=x<2**32 for x in streams):raise ValueError('Invalid seed roles')
 for k,v in dict(wall_seconds=3600,cleanup_reserve_seconds=15,memory_bytes=2*1024**3,bootstrap_replicates=30000,minimum_tail_count=20,alpha=.05,relative_half_width=.1,backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1,prefixes=[1024,4096,8192],implementation='vectorized').items():
  if p[k]!=v:raise ValueError('Frozen statistical/resource policy differs: '+k)
 expected_progression=dict(correlated_null=dict(intended=12,minimum_resolved=9,minimum_both_covered=11,maximum_resolved_miss=0),iid_null=dict(intended=4,minimum_resolved=3,minimum_both_covered=4,maximum_resolved_miss=0),shift_01=dict(intended=4,maximum_resolved=0),shift_05=dict(intended=4,maximum_resolved=0))
 if p['progression']!=expected_progression:raise ValueError('Progression changed')
 evidence=p['seed_audit'];audit=load(evidence['path'])
 if sha(evidence['path'])!=evidence['sha256'] or audit.get('status') not in ['complete','passed'] or not audit.get('inventory_files') or not audit.get('auditor') or not (audit.get('search_scope') or audit.get('scope')):raise ValueError('Reviewed seed inventory required')
 if set(streams)&set(audit['reserved_seeds']):raise ValueError('Historical seed collision')
 if any(sha(f)!=h for f,h in audit['inventory_files'].items()):raise ValueError('Historical evidence drift')
 if set(p['own_source'])!={str(Path(__file__).with_name(n).resolve()) for n in ['correlated_reference_study.py','gaussian_ar_indicator.py']}:raise ValueError('Exact prototype source set required')
 if set(p['source'])!={f.name for f in Path(p['study']).glob('*.py')}:raise ValueError('Study source inventory drift')
def freeze(draft):
 draft=Path(draft).resolve();p=load(draft)
 if p.get('frozen') is not False:raise ValueError('Unfrozen reviewed draft required')
 validate(p);verify(p,require_frozen=False);p.update(frozen=True,reviewed_draft_sha256=sha(draft),reviewed_draft_path=str(draft));target=draft.with_name('plan.json');save(target,p)
 with target.with_suffix('.sha256').open('x') as f:f.write(sha(target))
def read_frozen(path):
 path=Path(path);p=load(path)
 if path.with_suffix('.sha256').read_text().strip()!=sha(path) or sha(p['reviewed_draft_path'])!=p['reviewed_draft_sha256']:raise ValueError('Frozen plan/draft sidecar drift')
 validate(p);verify(p);return p
def verify(p,require_frozen=True):
 if (require_frozen and not p['frozen']) or len(p['cells'])!=28 or p['expected']!=28:raise ValueError('Reviewed frozen28cellplan required')
 if sha(p['python'])!=p['python_sha256'] or p['runtime']!={n:importlib.metadata.version(n) for n in ['numpy','scipy']}:raise ValueError('Runtime drift')
 for n,h in p['source'].items():
  if sha(Path(p['study'])/n)!=h:raise ValueError('Study source drift')
 for n,h in p['own_source'].items():
  if sha(n)!=h:raise ValueError('Study prototype source drift')
def worker(p,c,out):
 sys.path.insert(0,p['study'])
 from reference_bank_allocation import cell_worker,peak_memory
 cell_worker(p,c,out) # Existing2GiB cap and resource finally-record.
 # Reconstruct same paths only for cheap descriptive prefix estimates; no seeds added.
 import numpy as np
 from scipy.signal import lfilter
 from gaussian_ar_indicator import finite_n_covariance
 estimates={str(n):[] for n in p['prefixes']};paths=[]
 for seed,init in zip(c['fit_seeds'],c['init_seeds']):
  z=np.random.default_rng(seed).normal(size=c['lengths'][-1])*np.sqrt(1-c['rho']**2);z[0]=np.random.default_rng(init).normal();paths.append(lfilter([1.],[1.,-c['rho']],z))
 for n in p['prefixes']:
  for backend in [0,1]:estimates[str(n)].append(np.quantile(np.concatenate([x[:n] for x in paths[backend*c['fits_per_backend']:(backend+1)*c['fits_per_backend']]]),[.05,.95],method='inverted_cdf').tolist())
 save(Path(out)/'prefix-diagnostic.json',dict(estimates=estimates,scope='Unshifted basepaths; only nullcells used for scaling, no resource selection',covariance=[finite_n_covariance(n,c['fits_per_backend'],c['rho']) for n in p['prefixes']] if c['backend_b_shift']==0 else None))
def guarded_worker(p,c,out):
 sys.path.insert(0,p['study'])
 from reference_bank_allocation import peak_memory
 cpu_begin=time.process_time()
 try:worker(p,c,out)
 finally:
  resources=peak_memory();resources['wholeworker_cpu_seconds']=time.process_time()-cpu_begin;save(Path(out)/'resources.json',resources)
def validate_outputs(directory,c,p):
 result=load(directory/'result.json');resources=load(directory/'resources.json');bank=load(directory/'bank.json');diagnostic=load(directory/'prefix-diagnostic.json')
 if result.get('status')!='completed' or result.get('cell')!=c or result['bank_status']!=bank['status']:raise ValueError('Worker result identity invalid')
 peak=resources.get('peak_committed_bytes')
 if type(peak) not in (int,float) or not math.isfinite(peak) or not 0<peak<=p['memory_bytes']:raise ValueError('Wholeworker memory evidence invalid')
 if len(bank['joint_bootstrap_endpoints'])!=p['bootstrap_replicates'] or set(bank['endpoints'])!={'lo','hi'}:raise ValueError('Incomplete bank')
 for b in bank['endpoints'].values():
  if not all(type(b[k]) in (int,float) and math.isfinite(b[k]) for k in ['lower','upper','estimate','half_width']) or not b['lower']<=b['upper'] or b['half_width']<0:raise ValueError('Nonfinite bank bound')
 if set(diagnostic['estimates'])!={str(n) for n in p['prefixes']} or any(len(v)!=2 or any(len(a)!=2 or not all(math.isfinite(x) for x in a) for a in v) for v in diagnostic['estimates'].values()):raise ValueError('Prefix evidence missing')
 if not math.isfinite(resources.get('wholeworker_cpu_seconds',float('nan'))) or resources['wholeworker_cpu_seconds']<=0:raise ValueError('Wholeworker CPU missing')
 if c['backend_b_shift']==0:
  covariances=diagnostic.get('covariance')
  if not isinstance(covariances,list) or len(covariances)!=len(p['prefixes']):raise ValueError('Null covariance missing')
  for record,n in zip(covariances,p['prefixes']):
   if record['n']!=n or record['fits']!=c['fits_per_backend'] or record['rho']!=c['rho'] or list(record['probabilities'])!=[.05,.95]:raise ValueError('Covariance configuration mismatch')
   for key in ['cdf_covariance','quantile_delta_covariance','quadrature_error_estimate']:
    matrix=record[key]
    if len(matrix)!=2 or any(len(row)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in row) for row in matrix):raise ValueError('Nonfinite covariance matrix')
    if not math.isclose(matrix[0][1],matrix[1][0],rel_tol=1e-12,abs_tol=1e-15):raise ValueError('Asymmetric covariance')
    if key=='quadrature_error_estimate':
     if min(x for row in matrix for x in row)<0:raise ValueError('Negative quadrature error')
    elif matrix[0][0]<0 or matrix[1][1]<0 or matrix[0][0]*matrix[1][1]-matrix[0][1]*matrix[1][0]<-1e-14*max(matrix[0][0]*matrix[1][1],1e-30):raise ValueError('NonPSD covariance')
  last=diagnostic['estimates'][str(c['lengths'][-1])]
  if any(not math.isclose(last[i][j],bank['backend_point'][backend][endpoint],rel_tol=1e-12,abs_tol=1e-12) for i,backend in enumerate(['a','b']) for j,endpoint in enumerate(['lo','hi'])):raise ValueError('Prefix/backend bank estimates differ')
 elif diagnostic.get('covariance') is not None:raise ValueError('Shifted covariance scope must be explicitnull')
def execute(path,out):
 p=read_frozen(path);pin=sha(path);out=Path(out);out.mkdir(parents=True,exist_ok=False);save(out/'expected.json',dict(plan_sha256=pin,cells=p['cells']));rows=[];begin=time.monotonic();stop=None
 sys.path.insert(0,p['study']);from hardware_control import wrapper_command
 for i,c in enumerate(p['cells']):
  remaining=3600-(time.monotonic()-begin)
  if i==4:
   projected=max(r['seconds'] for r in rows)*24*4 if all(r['status']=='completed' for r in rows) else None
   save(out/'projection.json',dict(projected_seconds=projected,remaining_seconds=remaining))
   if projected is None or projected>remaining-15:stop='sentinel_resource_or_failure'
  if remaining<=15:stop='budget'
  row=dict(id=c['id'],status='not_started',seconds=0.,reason=stop)
  if not stop:
   directory=out/c['id'];directory.mkdir();tick=time.monotonic()
   try:
    read_frozen(path)
    if sha(path)!=pin:raise ValueError('Plan drift')
    remaining=3600-(time.monotonic()-begin)
    if remaining<=15:stop='budget';raise TimeoutError('Cleanup reserve reached')
    cmd=[p['python'],str(Path(__file__).resolve()),'worker','--plan',str(Path(path).resolve()),'--out',str(directory.resolve()),'--index',str(i)]
    with (directory/'worker.log').open('x') as log:r=subprocess.run(wrapper_command(cmd,[0],directory/'hardware.json',timeout=remaining-15),stdout=log,stderr=subprocess.STDOUT)
    row['returncode']=r.returncode;save(directory/'worker-exit.json',dict(row));read_frozen(path)
    if sha(path)!=pin:raise ValueError('Plan drift')
    h=load(directory/'hardware.json')
    from asof_rolling_execute import validate_hardware
    wrapped=wrapper_command(cmd,[0],directory/'hardware.json',timeout=remaining-15)
    validate_hardware(h,wrapped,r.returncode,remaining-15)
    row['hardware_sha256']=sha(directory/'hardware.json')
    if r.returncode==0:validate_outputs(directory,c,p)
    row['status']='completed' if r.returncode==0 and h['status']=='completed' else 'failed'
   except Exception as exc:
    row.update(status='failed',error=str(exc))
    if isinstance(exc,ValueError):stop='provenance_abort'
   row['seconds']=time.monotonic()-tick
  rows.append(row);save(out/(c['id']+'.json'),row)
 integrity_error=None
 try:read_frozen(path)
 except Exception as exc:integrity_error=str(exc)
 save(out/'summary.json',dict(expected=28,rows=rows,seconds=time.monotonic()-begin,qualified=False,integrity_error=integrity_error))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action',choices=['worker','run','freeze']);a.add_argument('--plan',required=True);a.add_argument('--out',required=True);a.add_argument('--index',type=int);v=a.parse_args()
 if v.action=='worker':p=read_frozen(v.plan);guarded_worker(p,p['cells'][v.index],v.out)
 elif v.action=='freeze':freeze(v.plan)
 else:execute(v.plan,v.out)
