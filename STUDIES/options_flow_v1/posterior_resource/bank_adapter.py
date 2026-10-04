"""Prototype compact-bank admission; no sampling, bootstrap or qualification.
Predictive arrays are inputs, NOT an admitted common-grid CDF cache.
"""
import hashlib,json,math
from pathlib import Path
PARAMETERS=('beta_bar','tau','mu_h','sigma_h','h_terminal')
FUNCTIONALS=PARAMETERS+('h_mean',)+tuple(p+str(g) for g in range(4) for p in ('alpha_','beta_'))
ENDPOINTS={f'{name}_{p}':dict(distribution_id=name,probability=p,kind='predictive' if name=='observed_group0_h1' else 'parameter') for name in (*PARAMETERS,'observed_group0_h1') for p in (.05,.95)}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def load(path):return json.loads(Path(path).read_text())
def manifest_check(m):
 if m.get('qualified') is not False or m.get('phase')!='prospective_reference_bank':raise ValueError('Prospective nonqualified bank required')
 rows=m['fits'];ids=[r['id'] for r in rows]
 if len(ids)!=len(set(ids)) or len(rows) not in (32,64):raise ValueError('16 or32 independent fits per backend required')
 if any(sum(r['backend']==b for r in rows)!=len(rows)//2 for b in ('public','reference')):raise ValueError('Balanced backend family required')
 streams=[r[k] for r in rows for k in ('sampler_seed','initialization_seed')]+[r['sampler_seed']+130000 for r in rows]
 if len(set(streams))!=len(streams) or any(type(s)!=int or not 0<=s<2**32 for s in streams):raise ValueError('Distinct fit streams required')
 if not m.get('excluded_resource_pilot_ids') or set(ids)&set(m['excluded_resource_pilot_ids']):raise ValueError('Resource pilot must be explicitly excluded')
 pilot=load(m['excluded_pilot_manifest'])
 if sha(m['excluded_pilot_manifest'])!=m['excluded_pilot_manifest_sha256']:raise ValueError('Pilot exclusion manifest changed')
 pilot_streams={c[k] for c in pilot['cells'] for k in ('seed','init_seed','predictive_seed')}
 if set(streams)&pilot_streams or any(r['sampler_seed']+130000 in pilot_streams for r in rows):raise ValueError('Renamed pilot stream reuse')
 if not {c['id'] for c in pilot['cells']}.issubset(set(m['excluded_resource_pilot_ids'])):raise ValueError('Actual pilot IDs must all be excluded')
 if m['endpoints']!=ENDPOINTS:raise ValueError('Exact12 endpoint family required')

def checkpoint_check(c,draws):
 ev=c['evaluation']
 if c['status']!='completed' or c['draws']!=draws:raise ValueError('Checkpoint status/length mismatch')
 if c['retained_divergences']!=0 or ev['chain_count']!=4 or set(ev['canonical_parameter_diagnostics'])!={f'q_{i}' for i in range(1012)} or set(ev['functionals'])!=set(FUNCTIONALS):raise ValueError('Full canonical health family missing')
 forecast=ev['forecast']['rows']
 if len(forecast)!=4 or {(v['horizon'],v['group']) for v in forecast}!={(1,g) for g in range(4)}:raise ValueError('Full forecast family missing')
 for bounds,errors in [(d['interval_90'],d['endpoint_mcse']) for d in ev['functionals'].values()]+[([v['lower'],v['upper']],v['endpoint_mcse']) for v in forecast]:
  if len(bounds)!=2 or len(errors)!=2 or not all(math.isfinite(x) for x in bounds+errors) or bounds[1]<=bounds[0] or min(errors)<0 or max(errors)>.02*(bounds[1]-bounds[0]):raise ValueError('Full precision gate failed')
 for d in [*ev['canonical_parameter_diagnostics'].values(),*ev['functionals'].values()]:
  if not all(math.isfinite(d[k]) for k in ('rhat','bulk_ess','tail_ess')) or not 0<d['rhat']<=1.01 or min(d['bulk_ess'],d['tail_ess'])<400:raise ValueError('Unhealthy reference checkpoint')

def admit_fit(spec,target):
 import numpy as np
 root=Path(spec['directory']);r=load(root/'resource-result.json')
 for key,file in [('result_sha256','resource-result.json'),('compact_sha256','extracted/compact.npz')]:
  if sha(root/file)!=spec[key]:raise ValueError('Manifest artifact hash mismatch')
 if r['status']!='resource_completed' or r['cell_id']!=spec['id'] or r['backend']!=spec['backend'] or r['posterior_sha256']!=target:raise ValueError('Fit/target identity mismatch')
 worker_path=Path(spec['worker_report']);fixture_path=Path(spec['fixture'])
 if sha(worker_path)!=r['worker_report_sha256'] or sha(worker_path)!=spec['worker_report_sha256'] or sha(fixture_path)!=spec['fixture_sha256']:raise ValueError('Worker/fixture provenance mismatch')
 worker=load(worker_path);fixture=load(fixture_path)
 if worker['seed']!=spec['sampler_seed'] or worker['predictive_seed']!=spec['sampler_seed']+130000 or worker['initial_positions']!=fixture['data']['initial_positions']:raise ValueError('Stream/start binding mismatch')
 import sys
 helper=Path(spec['study'])/'masked_market_comparison_plan.py'
 if sha(helper)!=spec['initialization_helper_sha256']:raise ValueError('Initialization helper changed')
 sys.path.insert(0,spec['study'])
 from masked_market_comparison_plan import dispersed_starts
 from .controller import posterior
 if posterior(fixture)!=target:raise ValueError('Actual fixture posterior mismatch')
 if fixture['data']['initial_positions']!=dispersed_starts(1000,4,fixture['data']['rho'],spec['initialization_seed']):raise ValueError('Initialization stream does not reproduce starts')
 if worker['bindings']!=spec['worker_bindings']:raise ValueError('Worker source/runtime bindings mismatch')
 resource_plan=load(spec['resource_plan'])
 if sha(spec['resource_plan'])!=spec['resource_plan_sha256']:raise ValueError('Resource plan changed')
 cells=[c for c in resource_plan['cells'] if c['id']==spec['id']]
 if len(cells)!=1 or cells[0]['seed']!=spec['sampler_seed'] or cells[0]['init_seed']!=spec['initialization_seed'] or cells[0]['fixture_sha256']!=spec['fixture_sha256']:raise ValueError('Original resource stream/fixture differs')
 from .resource_worker import validate_report
 validate_report(worker,cells[0],fixture,resource_plan,Path(spec['raw']))
 e=r['extraction']
 if e['raw_sha256']!=spec['raw_sha256'] or sha(spec['raw'])!=spec['raw_sha256'] or Path(spec['raw']).stat().st_size!=e['raw_bytes']:raise ValueError('Original raw extraction agreement failed')
 if e['compact_sha256']!=spec['compact_sha256'] or e['shape']!=[4,8000,1012] or not e['chain_order_preserved'] or not e['draw_order_preserved']:raise ValueError('Compact extraction mismatch')
 if e['predictive_contract']!=spec['predictive_contract']:raise ValueError('Predictive scenario mismatch')
 if sha(root/'extracted/canonical.npy')!=e['canonical_sha256']:raise ValueError('Canonical artifact changed')
 cps=r['checkpoints']
 if [v['draws'] for v in cps]!=[4000,8000]:raise ValueError('Paired prefix family missing')
 for cp in cps:
  path=root/f"checkpoint-{cp['draws']}.json"
  if sha(path)!=cp['checkpoint_sha256']:raise ValueError('Checkpoint digest mismatch')
  c=load(path);ev=c['evaluation']
  checkpoint_check(c,cp['draws'])
  cdf_path=root/f"predictive-cdf-{cp['draws']}.json"
  if sha(cdf_path)!=cp['predictive_cdf_sha256']:raise ValueError('Predictive CDF hash mismatch')
  cdf=load(cdf_path)
  if cdf['status']!='quadrature_converged' or cdf['probabilities']!=[.05,.95] or cdf['orders']!=[16,32,64,128] or cdf['metadata']['x_next']!=fixture['holdout']['x'][0][0]:raise ValueError('Predictive quadrature unresolved or scenario changed')
 with np.load(root/'extracted/compact.npz',allow_pickle=False) as f:
  arrays={name:f[name].copy() for name in (*FUNCTIONALS,'cdf_location','cdf_future_mean','cdf_future_sd')}
 if any(v.shape!=(4,8000) or not np.isfinite(v).all() for v in arrays.values()) or (arrays['cdf_future_sd']<=0).any():raise ValueError('Invalid compact array')
 return dict(id=spec['id'],backend=spec['backend'],parameters={str(n):{k:arrays[k][:,:n] for k in PARAMETERS} for n in (4000,8000)},predictive_inputs={str(n):{k:arrays[k][:,:n] for k in ('cdf_location','cdf_future_mean','cdf_future_sd')} for n in (4000,8000)},predictive_cache_admitted=False,qualified=False)

def collect(manifest):
 manifest_check(manifest);outcomes=[];admitted=[]
 for spec in manifest['fits']:
  try:
   fit=admit_fit(spec,manifest['posterior_sha256']);admitted.append(fit);outcomes.append(dict(id=spec['id'],status='compact_admitted_predictive_cache_pending'))
  except Exception as exc:outcomes.append(dict(id=spec['id'],status='invalid_or_missing',error=f'{type(exc).__name__}: {exc}'))
 return dict(expected=len(manifest['fits']),outcomes=outcomes,admitted=admitted,reference_bank_resolved=False,qualified=False)
