import hashlib,json,re
from pathlib import Path
import numpy as np,bridgestan
root=Path(__file__).resolve().parent;run=root/'run02';old=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/work/reconsider/run01');models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');manifest=json.loads((run/'MANIFEST.json').read_text());final=json.loads((run/'FINAL.json').read_text());assert final['unchanged'];rows=[];inputs={};parity=[]
pattern=re.compile(r'METRIC_AUDIT window=(\d+) transition=(\d+) dim=(\d+) r2=(\[.*?\]) cxx=(\[.*?\]) b=(\[.*?\]) precision=(\[.*?\])')
for job in final['jobs']:assert job['exit_code']==0 and job['group_drained']
for i,j in enumerate(manifest['jobs']):
 folder=run/f'{i:03d}';prior=old/f"{j['original_index']:03d}"/'RESULT.json';current=folder/'RESULT.json';a=json.loads(prior.read_text());b=json.loads(current.read_text());excluded=['wall_seconds'];aa={k:v for k,v in a.items() if k not in excluded};bb={k:v for k,v in b.items() if k not in excluded};same=aa==bb
 parity.append(dict(**j,passed=same,excluded=excluded,keys_compared=sorted(aa)));assert same,(j,[k for k in aa if aa[k]!=bb.get(k)])
 for p in [prior,current,folder/'worker.log']:inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 records=pattern.findall((folder/'worker.log').read_text());assert len(records)==1,(j,len(records))
 window,transition,d,r2,cxx,fit,precision=records[0];d=int(d);r2=np.array(json.loads(r2));P=np.array(json.loads(precision)).reshape(d,d);C=np.array(json.loads(cxx)).reshape(d,d);B=np.array(json.loads(fit)).reshape(d,d)
 model=bridgestan.StanModel(str(models/(j['model']+'_model.so')),data=str(models/(j['model']+'.data.json')),seed=1);names=model.param_unc_names();assert len(names)==d
 eig=np.linalg.eigvalsh(P);good=np.flatnonzero(r2>=.5);block=None
 if len(good)>=2:
  Q=P[np.ix_(good,good)];e=np.linalg.eigvalsh(Q);block=dict(indices=good.tolist(),names=[names[k] for k in good],min_eigenvalue=float(e.min()),positive_definite=bool(e.min()>0))
  if e.min()>0:
   norm=Q/np.sqrt(np.outer(np.diag(Q),np.diag(Q)));en=np.linalg.eigvalsh(norm);block.update(condition=float(e.max()/e.min()),diagonal_normalized_condition=float(en.max()/en.min()))
 rows.append(dict(**j,dimension=d,window=int(window),transition=int(transition),coordinates=names,r2=r2.tolist(),full_precision_eigenvalues=eig.tolist(),position_condition=float(np.linalg.cond(C)),good_block=block,original_decision=b['chains_data'][0]['dense_auto_select'],hypothesis_supported_in_cell=bool(r2.min()<.5 and block and block['positive_definite']),precision=P.tolist(),fit=B.tolist()))
out=root/'analysis02';out.mkdir(exist_ok=False)
for name,data in [('ROWS',rows),('PARITY',parity),('INPUTS',inputs)]: (out/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
summary=dict(cells=len(rows),parity_all=all(p['passed'] for p in parity),seconds=final['seconds'],supporting_cells=[dict(model=r['model'],seed=r['seed'],coordinates=r['coordinates'],r2=r['r2'],good_block=r['good_block']) for r in rows if r['hypothesis_supported_in_cell']],interpretation='Passive exposed-data mechanism audit only; no selection policy or performance claim.')
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
