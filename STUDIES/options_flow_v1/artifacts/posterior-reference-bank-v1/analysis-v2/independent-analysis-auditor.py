import json,hashlib,sys,math,zipfile
from pathlib import Path
import numpy as np
D=Path('C:/dev/owalnuts/STUDIES/options_flow_v1/artifacts/posterior-reference-bank-v1/analysis-v2').resolve();O=D/'analysis-output';checks={};errors={}
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ck(k,v):checks[k]=bool(v)
p=load(D/'analysis-plan.json');intent=load(D/'intent.json');s=load(D/'analysis-output-status.json');r=load(O/'analysis-result.json');bank=load(O/'bank-result.json');g=load(O/'common-grid.json')
ck('plan_pin',sha(D/'analysis-plan.json')==s['plan_sha256']=='a4b71c18c195c22095fbf8872529eeced02e0d651e211c5164855424406a69f5')
ck('result_pin',sha(O/'analysis-result.json')==s['result_sha256']);ck('resolved_integrity',s['reference_bank_resolved'] is True and r['integrity_pass'] is True and r['qualified'] is False and bank['qualified'] is False and not bank['reasons'])
for path,h in p['bindings'].items():ck('binding:'+path,sha(path)==h)
sys.path.insert(0,p['study']);from posterior_resource.bank_analysis_preparation import verify_materialized
verify_materialized(p);ck('prefit_intent_materialization',True)
from asof_rolling_execute import validate_hardware
h=load(D/'analysis-output-hardware.json');command=load(D/'analysis-output-launch.json')['command'];validate_hardware(h,command,s['returncode'],float(command[command.index('--timeout')+1]));ck('hardware',True)
ck('cost_identity',s['total_analysis_seconds']==s['additional_outer_seconds']+s['materialization_seconds'] and 0<s['total_analysis_seconds']<=7200)
ck('all64_admitted',bank['expected_fits']==bank['recorded_fits']==r['expected_fits']==64 and len(r['outcomes'])==64 and [x['id'] for x in r['outcomes']]==intent['ordered_ids'])
w=np.load(O/'frozen-weights.npy',mmap_mode='r');ck('frozen_weight_digest',hashlib.sha256(w.tobytes(order='C')).hexdigest()==g['frozen_weights_sha256']==r['weight_sha256']==intent['expected_weight_sha256'])
ck('weight_scope',w.shape==(120004,128) and g['ordered_ids']==intent['grid_columns'] and g['frozen_weight_rows']==len(w))
ck('paired_prefix_weights',np.array_equal(w[0::4,0::2],w[1::4,1::2]) and not w[0::4,1::2].any() and not w[1::4,0::2].any())
rows=[g['rows'][k] for k in g['ordered_ids']];grid=np.asarray(rows[0]['grid']);cdf=np.asarray([x['cdf'] for x in rows]);eps=np.asarray([x['numerical_cdf_error_estimate'] for x in rows]);ck('common_grid',all(x['grid']==grid.tolist() for x in rows) and len(grid)==g['queries']==22)
for i,row in enumerate(rows):
 ladder=row['cdf_by_order'];estimate=max(max(abs(x-y) for x,y in zip(ladder['128'],ladder['64'])),max(abs(x-y) for x,y in zip(ladder['64'],ladder['32'])))
 ck('quadrature:'+str(i),set(ladder)=={'16','32','64','128'} and row['cdf']==ladder['128'] and estimate==eps[i] and eps[i]<=1e-8 and row['error_bound_verified'] is False)
maxwidth=0.;allbrackets=True
for start in range(0,len(w),512):
 weights=np.asarray(w[start:start+512]);weights=weights/weights.sum(axis=1,keepdims=True);low=weights@np.maximum(0,cdf-eps[:,None]);high=weights@np.minimum(1,cdf+eps[:,None])
 for prob in [.05,.95]:
  left=high<prob;right=low>=prob;okay=left.any(axis=1)&right.any(axis=1);allbrackets=allbrackets and bool(okay.all())
  li=np.where(left,np.arange(len(grid)),-1).max(axis=1);ri=np.where(right,np.arange(len(grid)),len(grid)).min(axis=1)
  if okay.any():maxwidth=max(maxwidth,float(np.max(grid[ri[okay]]-grid[li[okay]])))
ck('every_declared_weight_error_bracket',allbrackets and maxwidth<=.01 and g['declared_weight_brackets_resolved'] is True)
draws=bank['joint_bootstrap_endpoints'];names=list(intent['endpoints']);ck('joint30000x12',len(draws)==30000 and all(set(x)==set(names) for x in draws))
tail=.05/(6*12);ck('tail_count',30000*tail>=20);metrics={}
for name,b in bank['endpoints'].items():
 values=np.array([x[name] for x in draws]);quant=np.quantile(values,[tail,1-tail],method='linear');err=b['numerical_half_width'];ck('endpoint_interval:'+name,math.isclose(b['lower'],float(quant[0])-err,rel_tol=1e-12,abs_tol=1e-14) and math.isclose(b['upper'],float(quant[1])+err,rel_tol=1e-12,abs_tol=1e-14))
 stem=name.rsplit('_',1)[0];lo=bank['endpoints'][stem+'_0.05'];hi=bank['endpoints'][stem+'_0.95'];width=hi['estimate']-lo['estimate'];wlow=hi['lower']-lo['upper']
 ck('endpoint_gate:'+name,width>0 and wlow>0 and b['W_low']==wlow and b['half_width']<=.1*width and max(map(abs,b['backend_difference_interval']))<=.02*width and max(map(abs,b['paired_length_difference_interval']))<=.1*width)
 metrics[name]=dict(estimate=b['estimate'],interval=[b['lower'],b['upper']],halfwidth_over_width=b['half_width']/width,numerical_halfwidth=b['numerical_half_width'],backend_max_over_width=max(map(abs,b['backend_difference_interval']))/width,length_max_over_width=max(map(abs,b['paired_length_difference_interval']))/width)
inventory={str(f):dict(bytes=f.stat().st_size,sha256=sha(f)) for f in O.iterdir() if f.is_file()}
out=dict(integrity_pass=all(checks.values()),checks=checks,failed=[k for k,v in checks.items() if not v],metrics=metrics,max_declared_weight_bracket_width=maxwidth,max_quadrature_error_estimate=float(eps.max()),costs={k:s[k] for k in ['materialization_seconds','additional_outer_seconds','total_analysis_seconds']},grid_seconds=r['grid_seconds'],bootstrap_seconds=r['bootstrap_seconds'],resources=r['resources'],inventory=inventory,qualified=False,limitations=['All64fits admitted, whole-fit bootstrap is finite-bank approximation; neither backend agreement nor these gates establishes posterior truth/calibrated coverage.','Quadrature ladder differences are estimated, not certified integration bounds.','Saved joint endpoint draws allow independent endpoint interval reconstruction; full backend/length bootstrap vectors were not saved, so their interval construction is supported by pinned executed source, not independently recomputed here.','Predictive grid midpoint/error may dominate apparent predictive uncertainty; raw-unit .01 grid is not .001W qualification.'])
with (D/'independent-analysis-audit.json').open('x') as f:json.dump(out,f,indent=2)
copy=D/'independent-analysis-auditor.py'
with copy.open('xb') as f:f.write(Path(__file__).read_bytes())
with zipfile.ZipFile(D/'independent-analysis-source.zip','x',zipfile.ZIP_DEFLATED) as z:
 for path in intent['analysis_source_inventory']:z.write(path,'posterior_resource/'+str(Path(path).relative_to(intent['analysis_source_directory'])))
 for path in intent['bindings']:
  if Path(path).parent==Path(p['study']) and path.endswith('.py'):z.write(path,'study/'+Path(path).name)
with (D/'independent-analysis-provenance.json').open('x') as f:json.dump(dict(auditor_sha256=sha(copy),audit_sha256=sha(D/'independent-analysis-audit.json'),source_zip_sha256=sha(D/'independent-analysis-source.zip'),analysis_plan_sha256=sha(D/'analysis-plan.json')),f,indent=2)
print(json.dumps(dict(integrity_pass=out['integrity_pass'],checks=len(checks),failed=out['failed'],maxwidth=maxwidth,maxerror=float(eps.max()))))
