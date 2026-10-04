"""Independent compact evidence audit; never modifies frozen campaign inputs."""
import json,hashlib,math,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STUDY=ROOT/'STUDIES/options_flow_v1'
sys.path.insert(0,str(STUDY))
from asof_rolling_execute import validate_hardware
from continuation_comparison import validate_raw_starts
P=STUDY/'artifacts/fresh-paired-comparison-v1/run-v1'
FUNCTIONS={'beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean'}|{f'{k}_{g}' for k in ('alpha','beta') for g in range(4)}
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def gate(r):
 e=r['evaluation'];fs=e['functionals'];qs=e['canonical_parameter_diagnostics'];fore=e['forecast']['rows']
 assert set(fs)==FUNCTIONS and set(qs)=={f'q_{i}' for i in range(1012)} and {(x['horizon'],x['group']) for x in fore}=={(1,g) for g in range(4)} and len(fore)==4
 healthy=e['chain_count']==4 and r['retained_divergences']==0 and all(all(type(d[k]) in (int,float) and math.isfinite(d[k]) for k in ('rhat','bulk_ess','tail_ess')) and 0<d['rhat']<=1.01 and min(d['bulk_ess'],d['tail_ess'])>=400 for d in [*fs.values(),*qs.values()])
 ratios=[]
 for bounds,mcse in [(x['interval_90'],x['endpoint_mcse']) for x in fs.values()]+[([x['lower'],x['upper']],x['endpoint_mcse']) for x in fore]:
  assert len(bounds)==len(mcse)==2 and all(math.isfinite(x) for x in bounds+mcse) and min(mcse)>=0 and bounds[1]>bounds[0]
  ratios.append(max(mcse)/(bounds[1]-bounds[0]))
 assert r['healthy']==healthy
 return healthy and r['status']=='completed' and max(ratios)<=.02,max(ratios)
def main(out):
 checks=[];rows=[];inventory={}
 def check(name,condition):checks.append(dict(name=name,passed=bool(condition)))
 def bind(p,h=None):
  actual=sha(p);inventory[str(Path(p).resolve())]=dict(sha256=actual,bytes=Path(p).stat().st_size)
  if h is not None:check('hash:'+str(p),actual==h)
 plan=read(P/'plan.json');terminal=read(P/'terminal.json');cost=read(P/'terminal-cost.json')
 for name in ('plan.json','terminal.json','terminal-cost.json','execution-started.json'):bind(P/name)
 check('frozen_plan',sha(P/'plan.json')==Path(P/'plan.sha256').read_text().strip()==terminal['plan_sha256']=='f0274c78c6fec67dd00a8b82764fad174c68075697c077867752143690d45cfb')
 for section in ('sources','bindings'):
  for p,h in plan[section].items():bind(p,h)
 check('all72ordered',terminal['expected']==72 and [x['controller']['id'] for x in terminal['outcomes']]==[c['id'] for c in plan['cells']] and len(terminal['outcomes'])==72)
 for c,o in zip(plan['cells'],terminal['outcomes']):
  try:
   status=read(c['controller_status']);h=read(c['hardware']);r=read(c['report']);fixture=read(c['fixture']);started=read(c['started']);ex=read(c['exit'])
   for k in ('controller_status','hardware','report','fixture','started','exit'):bind(c[k])
   check(c['id']+':terminal_identity',status==o['controller'] and status['status']=='completed' and status['success'] is True and status['returncode']==ex['returncode']==0 and h['status']=='completed')
   validate_hardware(h,c['command'],status['returncode'],1800)
   check(c['id']+':hardware',True)
   check(c['id']+':started',started==dict(id=c['id'],plan_sha256=sha(P/'plan.json'),command=c['command']))
   check(c['id']+':bindings',r['bindings']==c['worker_bindings'])
   check(c['id']+':physical_starts',r['initial_positions']==fixture['data']['initial_positions'])
   check(c['id']+':streams',r['seed']==c['sampler_seed'] and r['predictive_seed']==c['prediction_seed'])
   check(c['id']+':parity',r['parity']['passed'] is True and r['hardware_control']['realized_cpus']==[0])
   attempts=r['attempts'];tiers=[a['draws'] for a in attempts]
   check(c['id']+':prefix_tiers',tiers==[1000,2000,4000,8000][:len(tiers)])
   outcomes=[]
   for a in attempts:
    base=Path(c['worker_directory']);tier=a['draws']
    fp=base/f'draws-{tier}'/'fit-report.json' if c['backend']=='public' else base/f'draws-{tier}-report.json'
    raw=base/f'draws-{tier}'/'python-pymc-flow-raw.json' if c['backend']=='public' else base/f'draws-{tier}-raw.json'
    fit=read(fp);bind(fp);passed,ratio=gate(fit);outcomes.append(passed)
    validate_raw_starts(raw,fixture['data']['initial_positions'])
    check(c['id']+f':tier_{tier}',passed==a['screen']['pass'] and math.isclose(ratio,a['screen']['max_endpoint_mcse_over_width'],rel_tol=1e-12) and fit['draws']==tier)
   final,ratio=gate(r)
   check(c['id']+':first_pass',outcomes==[False]*(len(outcomes)-1)+[True] and final and r['precision_pass'] and r['draws']==tiers[-1])
   check(c['id']+':selected_report',r['evaluation']==fit['evaluation'] and r['retained_divergences']==fit['retained_divergences'])
   norm=o['normalized'];check(c['id']+':normalization',norm['outcome']=='usable' and norm['selected_tier']==r['draws'] and norm['healthy'] and norm['precision_pass'])
   for name,ep in norm['endpoints'].items():
    source=next(x for x in r['evaluation']['forecast']['rows'] if x['group']==0) if ep['distribution_id']=='observed_group0_h1' else r['evaluation']['functionals'][ep['distribution_id']]
    bounds=[source['lower'],source['upper']] if 'lower' in source else source['interval_90'];j=0 if ep['probability']==.05 else 1
    check(c['id']+':endpoint:'+name,ep['estimate']==bounds[j] and ep['mcse']==source['endpoint_mcse'][j])
   check(c['id']+':cost_enclosure',all(math.isfinite(o[k]) and o[k]>=0 for k in ('full_cell_seconds','postprocessing_seconds','worker_wrapper_and_preflight_seconds')) and math.isclose(o['full_cell_seconds'],o['postprocessing_seconds']+o['worker_wrapper_and_preflight_seconds'],abs_tol=1e-8) and o['worker_wrapper_and_preflight_seconds']>=r['end_to_end_seconds'])
   rows.append(dict(id=c['id'],backend=c['backend'],draws=r['draws'],full_seconds=o['full_cell_seconds'],max_endpoint_mcse_over_width=ratio,usable=norm['outcome']=='usable'))
  except Exception as e:checks.append(dict(name=c['id']+':complete_evidence',passed=False,error=f'{type(e).__name__}: {e}'));rows.append(dict(id=c['id'],error=str(e)))
 total=cost['total_seconds_including_terminal_serialization'];sumcost=sum(o['full_cell_seconds'] for o in terminal['outcomes'])
 check('full_budget',sumcost<=terminal['elapsed_seconds']<=total<=21600 and cost['total_budget_unresolved'] is False and terminal['budget_status']=='within_admission_budget')
 summaries={a:dict(intended=36,usable=sum(r.get('usable',False) for r in rows if r.get('backend')==a),full_cell_seconds=sum(r.get('full_seconds',0) for r in rows if r.get('backend')==a),tier_counts=dict(collections.Counter(r['draws'] for r in rows if r.get('backend')==a))) for a in ('public','reference')}
 result=dict(integrity_pass=all(c['passed'] for c in checks),checks=checks,rows=rows,arms=summaries,total_seconds=total,shared_overhead_seconds=total-sumcost,inventory=inventory,qualified=False,scope='Independent compact full-gate/endpoint/cost check. Raw physical starts checked from bounded tails; complete raw hashes and frozen adapter revalidation are separate postfit analysis evidence.')
 with Path(out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
 print(json.dumps({k:result[k] for k in ('integrity_pass','arms','total_seconds','shared_overhead_seconds')}));print('FAILED',[c for c in checks if not c['passed']])
if __name__=='__main__':main(sys.argv[1])
