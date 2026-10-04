"""Independent vectorized arithmetic and streaming postfit artifact audit."""
import json,hashlib,math,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'STUDIES/options_flow_v1/artifacts/fresh-paired-comparison-v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main(out):
 checks=[]
 def check(name,predicate,detail=None):checks.append(dict(name=name,passed=bool(predicate),detail=detail))
 pin=read(BASE/'postfit-analysis-v1/analysis-pin.json');result=read(BASE/'postfit-analysis-v1/decision-result.json')
 hashed_bytes=0
 for p,h in pin['bindings'].items():
  check('immutable_artifact:'+p,sha(p)==h);hashed_bytes+=Path(p).stat().st_size
 plan=read(pin['plan']);terminal=read(pin['terminal']);cost=read(pin['terminal_cost']);pairs=read(pin['pair_map']);bp=read(pin['bank_pin']);bank=read(bp['bank'])
 for p,h in bp['bindings'].items():check('immutable_bank:'+p,sha(p)==h)
 rows={r['controller']['id']:r for r in terminal['outcomes']};names=list(bank['endpoints'])
 counts=np.load(pin['counts'],allow_pickle=False).astype(float);indices=np.load(pin['bank_indices'],allow_pickle=False)
 vectors=np.array([[v[n] for n in names] for v in bank['joint_bootstrap_endpoints']])[indices]
 widths=np.array([bank['endpoints'][n]['W_low'] for n in names]);eps=np.array([bank['endpoints'][n]['numerical_half_width'] for n in names])/widths
 overhead=(cost['total_seconds_including_terminal_serialization']-sum(r['full_cell_seconds'] for r in rows.values()))/72
 check('cost_overhead',overhead>=0 and math.isclose(result['cost_reconciliation']['shared_overhead_seconds'],72*overhead,abs_tol=1e-10))
 costs=[];accuracy={}
 for arm in ('public','reference'):
  ordered=[rows[p[arm]] for p in pairs];check('all36usable:'+arm,len(ordered)==36 and all(r['normalized']['outcome']=='usable' for r in ordered))
  y=np.array([[r['normalized']['endpoints'][n]['estimate'] for n in names] for r in ordered]);c=np.array([r['full_cell_seconds']+overhead for r in ordered]);costs.append(counts@c/36)
  # E[(Y-B)^2] identity uses the same one bank vector per resample.
  mean=(counts@y/36-vectors)/widths
  squared=(counts@(y*y)/36-2*vectors*(counts@y/36)+vectors*vectors)/(widths*widths)
  check('nonnegative_second_moments:'+arm,float(squared.min())>=-1e-12)
  rms=np.sqrt(np.maximum(0,squared));details={}
  for k,n in enumerate(names):
   interval=np.quantile(mean[:,k],[.05/96,1-.05/96])+[-eps[k],eps[k]]
   upper=float(np.quantile(rms[:,k],1-.05/48))+eps[k];actual=result['accuracy'][arm]['checks'][n]
   passed=bool(interval[0]>=-.02 and interval[1]<=.02 and upper<=.04)
   check('accuracy_arithmetic:'+arm+':'+n,np.allclose(interval,actual['mean_interval'],rtol=1e-10,atol=1e-12) and math.isclose(upper,actual['rms_upper'],rel_tol=1e-9,abs_tol=1e-11) and passed==actual['pass_gate'])
   details[n]=dict(mean_interval=interval.tolist(),rms_upper=upper,pass_gate=passed)
  accuracy[arm]=details
  reliability=result['reliability'][arm]
  check('exact_reliability:'+arm,reliability['successes']==reliability['intended']==36 and math.isclose(reliability['lower97_5'],.025**(1/36),rel_tol=1e-12) and reliability['pass_gate']==(.025**(1/36)>.9))
  check('all_attempt_cost:'+arm,math.isclose(reliability['total_cost'],float(c.sum()),rel_tol=1e-12))
 ratio_interval=np.quantile(costs[1]/costs[0],[.025,.975])
 check('paired_runtime_interval',np.allclose(ratio_interval,result['runtime_ratio_interval'],rtol=1e-12,atol=1e-12))
 expected_speed=bool(ratio_interval[0]>1.25 and all(v['pass_gate'] for d in accuracy.values() for v in d.values()) and not result['unresolved_reasons'])
 check('predeclared_speed_verdict',result['speed_gate']==expected_speed)
 check('no_overclaim',result['qualified'] is False and result['policy']['overall_joint95_claim'] is False and result['policy']['replicates']==40000 and result['policy']['mean_tail']==.05/96 and result['policy']['rms_tail']==.05/48)
 output=dict(integrity_pass=all(c['passed'] for c in checks),checks=checks,hashed_input_bytes=hashed_bytes,accuracy=accuracy,runtime_ratio_interval=ratio_interval.tolist(),speed_gate=expected_speed,reliability_lower=.025**(1/36),qualified=False,scope='Independent arithmetic for this realized all-usable cohort; shared approximate bank and estimated numerical envelope, separate families, no calibrated coverage or overall joint95 guarantee.',auditor_sha256=sha(__file__),result_sha256=sha(BASE/'postfit-analysis-v1/decision-result.json'))
 with Path(out).open('x') as f:json.dump(output,f,indent=2,allow_nan=False)
 print(json.dumps({k:output[k] for k in ('integrity_pass','runtime_ratio_interval','speed_gate','reliability_lower','hashed_input_bytes')}));print('FAILED',[c for c in checks if not c['passed']])
if __name__=='__main__':main(sys.argv[1])
