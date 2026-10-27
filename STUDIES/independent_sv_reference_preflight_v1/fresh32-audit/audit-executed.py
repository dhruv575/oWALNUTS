from pathlib import Path
import json,hashlib,math,collections
import numpy as np
root=Path('C:/dev/owalnuts-wt/warm-precision/STUDIES/prior_predictive_validation_v1/execution-20261027/evidence/prior-predictive-validation-20261027');c=root/'campaign01/campaign';errors=[]
def check(condition,message):
 if not condition:errors.append(message)
def read(p):return json.loads(p.read_text())
checks=(root/'CHECKSUMS.sha256').read_text().splitlines()
for line in checks:
 digest,name=line.split('  ',1);check(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,'checksum '+name)
pending=read(root/'MANIFEST-PENDING.json');authorized=read(root/'MANIFEST-AUTHORIZED.json');check(authorized['status']=='frozen_authorized','authorization');authorized['status']=pending['status'];check(authorized==pending,'manifest nonstatus change')
ledger=read(c/'ledger.json');check(len(ledger)==1024 and {(r['stream'],r['tick']) for r in ledger}=={(s,t) for s in range(32) for t in range(1,33)},'ledger identities')
for row in ledger:
 check(row['current_index']==249+row['tick'] and row['label_index']==250+row['tick'],'causal ledger indices')
 check(all(row['arms'][a]['status']=='ok' for a in ('candidate','baseline','oracle')),'unreported missing arm')
campaign=read(c/'campaign.json');expected={(kind,i) for kind,n in [('candidate',32),('sides',32),('reference',8),('report',1)] for i in range(n)}
check(len(campaign['jobs'])==73 and {(j['kind'],j['id']) for j in campaign['jobs']}==expected,'job denominator')
for j in campaign['jobs']:
 check(j['exit_code']==0 and j['group_drained'],'job failure '+str((j['kind'],j['id'])))
 record=read(c/'job-records'/f"{j['kind']}-{j['id']:02d}.json");check(record['status']=='complete' and record['postrun_sources_match'],'job record '+str((j['kind'],j['id'])))
raw_count=0
for stream in range(32):
 directory=c/f'stream-{stream:02d}';data=read(directory/'data.json');check(data['stream']==stream,'stream identity')
 for name in ('y','h'):
  a=np.load(directory/data['files'][name]['file'],allow_pickle=False);check(a.shape==(283,) and np.isfinite(a).all(),'generated array')
 record=read(directory/'candidate.json');check(record['status']=='complete' and record['valid_ticks']==32 and record['unattempted_ticks']==[],'candidate completeness')
 check([r['tick'] for r in record['rows']]==list(range(1,33)),'candidate tick order')
 for row in record['rows']:
  a=np.load(directory/row['compact']['file'],allow_pickle=False);check(a.shape==(4,400,4) and a.dtype==np.float64 and np.isfinite(a).all(),'candidate compact');raw_count+=1
  with np.load(directory/row['score_arrays']['file'],allow_pickle=False) as arrays:
   for key in ('row__forecast__logpdf_by_chain_draw','row__forecast__pit_by_chain_draw'):
    a=arrays[key];check(a.shape==(4,400) and np.isfinite(a).all(),'candidate score shape/finiteness')
refs=[]
for i in range(8):
 directory=c/f'sentinel-{i:02d}';r=read(directory/'reference.json');a=np.load(directory/r['compact']['file'],allow_pickle=False)
 check(a.shape==(4,4000,4) and a.dtype==np.float64 and np.isfinite(a).all(),'reference compact')
 diagnostics=r['diagnostics'];passed=all(np.isfinite(list(d.values())).all() and d['rhat']<=1.01 and d['bulk_ess']>=1000 and d['tail_ess']>=1000 for d in diagnostics.values()) and sum(r['metadata']['divergences'])==0 and r['precision']['pit_mcse']<=.005 and r['precision']['logpdf_delta_mcse']<=.01
 check(passed and r['reference_diagnostics_pass'] and r['candidate_precision']['status']=='available','reference precision pass')
 check(r['metadata']['chain_coordinates']==[0,1,2,3],'reference chain identities')
 refs.append(r)
summary=read(c/'summary.json');supervisor=read(root/'campaign01/external-supervisor.json')
check(supervisor['evidence_complete'] and supervisor['group_drained'] and supervisor['exit_code']==0,'external evidence')
check(summary['qualification'] is None and campaign['qualification'] is None,'unspecified qualification')
allmetrics=[d for r in refs for d in r['diagnostics'].values()]
result=dict(scope='Read-only integrity and already-frozen diagnostic audit; no new scores, bootstrap draws or gates',checksum_files=len(checks),planned_origins=len(ledger),planned_jobs=len(campaign['jobs']),candidate_compact_files=raw_count,reference_compact_files=len(refs),errors=errors,reference_recorded_extrema=dict(max_rhat=max(d['rhat'] for d in allmetrics),min_bulk_ess=min(d['bulk_ess'] for d in allmetrics),min_tail_ess=min(d['tail_ess'] for d in allmetrics),max_pit_mcse=max(r['precision']['pit_mcse'] for r in refs),max_logpdf_delta_mcse=max(r['precision']['logpdf_delta_mcse'] for r in refs),divergences=sum(sum(r['metadata']['divergences']) for r in refs)),reported_pit_envelope_contains_uniform={arm:all(lo<=target<=hi for lo,target,hi in zip(value['pit_ecdf']['lower'],value['pit_ecdf']['uniform_target'],value['pit_ecdf']['upper'])) for arm,value in summary['arms'].items()},frozen_summary_sha256=hashlib.sha256((c/'summary.json').read_bytes()).hexdigest())
out=Path('target/fresh32-independent-audit');out.mkdir(exist_ok=True,parents=True);(out/'audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
