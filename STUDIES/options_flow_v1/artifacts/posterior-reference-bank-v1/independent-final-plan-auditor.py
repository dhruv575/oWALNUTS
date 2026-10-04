from pathlib import Path
import json,hashlib,sys
S=Path('C:/dev/owalnuts/STUDIES/options_flow_v1').resolve();D=S/'artifacts/posterior-reference-bank-v1';F=D/'run-v2/plan.json';A=D/'analysis-v2/intent-draft.json'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=load(F);a=load(A);checks={}
checks['fitpin']=sha(F)=='0d8b13c4c2defb57fc268cf83e41e4756bab78fb1469a8fcf51dd4b68ae349df'
checks['analysispin']=sha(A)=='a96b4dffc04a83011ca8455bdbe0619c3bb20de47e3730d00811f91ba61c37df'
for kind,obj in [('fit',p),('analysis',a)]:
 for path,h in obj['bindings'].items():checks[kind+':'+path]=sha(path)==h
cells=p['cells'];seeds=[c[k] for c in cells for k in ['init_seed','seed','predictive_seed']]
checks['exact192streams']=len(set(seeds))==192 and set(seeds)==set(range(199010001,199010065))|set(range(199110001,199110065))|set(range(199240001,199240065))
checks['32perbackend']=len(cells)==64 and sum(c['backend']=='public' for c in cells)==32 and sum(c['backend']=='reference' for c in cells)==32
checks['bootstrapdistinct']=a['analysis_policy']['bootstrap_seed']==199370001 and 199370001 not in seeds
checks['weightpin']=a['expected_weight_sha256']=='aa9bf4ecb88432f57cef5cc753fbe27c3add6850d402dcd0d61a207049fe7b21'
checks['fixedorder']=a['ordered_ids']==[c['id'] for c in cells]
checks['targetfamily']=a['posterior_sha256']==p['posterior_sha256'] and a['endpoints']==p['bank_endpoints'] and len(a['endpoints'])==12
checks['analysisunfrozen']=a['frozen'] is False
for version in ['run','run-v2']:
 root=D/version
 checks[version+':no_prior_work']=not(root/'terminal.json').exists() and not list(root.glob('*-started.json')) and not list(root.glob('*-status.json'))
sys.path.insert(0,str(S));from posterior_resource.bank_controller import verify_frozen
from posterior_resource.bank_analysis_preparation import require_unstarted
from posterior_resource.bank_analysis import validate_policy
verify_frozen(F);require_unstarted(F);validate_policy(a['analysis_policy']);checks['production_config_runtime_startreconstruction']=True
for name in ['fit','bootstrap']:
 audit=load(D/f'final-preparation/{name}-seed-audit-v3.json');checks[name+':audit_pass']=audit['status']=='passed' and audit['hits']==[]
 expected=set(seeds) if name=='fit' else {199370001};checks[name+':audit_streams']=set(audit['seeds'])==expected
 for path,h in audit.get('supplemental_evidence',{}).items():checks[name+':supplement:'+path]=sha(path)==h
out=dict(status='GO' if all(checks.values()) else 'BLOCKED',checks=checks,failed=[k for k,v in checks.items() if not v],fitting_plan_sha256=sha(F),analysis_draft_sha256=sha(A),scope=['64 fresh fixed8k fits/32perbackend, exact4000prefix; all failures retained.','Fitting6h/1800sperfit,analysis2h including materialization;8GiBCPU0.','Analysis intent must now freeze and link before execute; no fitting work has started.','193audited distinct streams; prior unlaunched artifacts preserved; no poweredcalibration claim.'])
with (D/'independent-final-plan-review.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(dict(status=out['status'],checks=len(checks),failed=out['failed'])))
