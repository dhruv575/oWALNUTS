import hashlib,json,sys,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_tail_replay01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
build=json.loads((l/'gp_tail_build01/SUMMARY.json').read_text());assert build['passed'];b=build['rows'][0];assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256'];rows=[]
def summarize(items):
    return dict(n=len(items),mean_calls=float(np.mean([x['calls'] for x in items])),mean_leaves=float(np.mean([x['leaves'] for x in items])),mean_macro_length=float(np.mean([x['macro_length'] for x in items])),fraction_unchanged=float(np.mean([not x['changed'] for x in items])),fraction_refined=float(np.mean([(x['refinement_level'] or 0)>0 for x in items])),reverse_rejections=sum(x['reverse_rejections'] for x in items),stops={stop:sum(x['stop']==stop for x in items) for stop in sorted(set(x['stop'] for x in items))})
for seed in range(946500001,946500009):
    old=l/'gp_wal_selected_validation01'/f'walnuts_dense-{seed}';folder=r/str(seed);folder.mkdir();shutil.copy2(old/'INPUT.json',folder/'INPUT.json');result=execute([b['binary'],str(folder/'INPUT.json'),str(folder/'RAW.json')],str(p),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2));assert result['exit_code']==0 and result['group_drained'];data=json.loads((folder/'RAW.json').read_text());prior=json.loads((old/'RAW.json').read_text())
    assert {k:v for k,v in prior.items() if k!='seconds'}=={k:data[k] for k in prior if k!='seconds'};rho=np.exp(np.asarray(data['draws'])[:,:,0]);threshold=float(np.quantile(rho,.05));chains=[]
    for ci,detail in enumerate(data['chain_details']):
        diagnostics=detail['diagnostics'];assert len(diagnostics)==2000;calls=sum(x['calls'] for x in diagnostics);assert calls==detail['retained_calls'],(seed,ci,calls,detail['retained_calls']);low=[x for i,x in enumerate(diagnostics) if rho[ci,i]<=threshold];rest=[x for i,x in enumerate(diagnostics) if rho[ci,i]>threshold];masses=[x['dense'] for x in detail['mass_updates'] if x['dense'] is not None];mass=np.asarray(masses[-1]).reshape(13,13) if masses else None
        chain=dict(chain=ci,step=detail['step_size'],mass_condition=float(np.linalg.cond(mass)) if mass is not None else None,all=summarize(diagnostics),lower=summarize(low),other=summarize(rest))
        if seed==946500006 and ci==1:chain.update(excursion=summarize(diagnostics[309:468]),complement=summarize(diagnostics[:309]+diagnostics[468:]))
        chains.append(chain)
    rows.append(dict(seed=seed,exact_parity=True,pooled_lower_threshold=threshold,chains=chains));print(json.dumps(dict(seed=seed,exact_parity=True)),flush=True)
(r/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,build=build),indent=2,allow_nan=False)+'\n')
