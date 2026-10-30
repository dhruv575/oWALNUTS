import hashlib,json,re,time
from pathlib import Path
import numpy as np,bridgestan
root=Path(__file__).resolve().parent;run=root/'run02';manifest=json.loads((run/'MANIFEST.json').read_text());parity=json.loads((root/'analysis02/PARITY.json').read_text());assert all(p['passed'] for p in parity)
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');pattern=re.compile(r'CURVATURE_SNAPSHOT count=(\d+) position=(\[.*?\]) gradient=(\[.*?\])');rows=[];raw=[];inputs={};start=time.monotonic()
for i,j in enumerate(manifest['jobs']):
 p=run/f'{i:03d}'/'worker.log';inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();snaps=pattern.findall(p.read_text());assert len(snaps)==16,(j,len(snaps));model=bridgestan.StanModel(str(models/(j['model']+'_model.so')),data=str(models/(j['model']+'.data.json')),seed=1);names=model.param_unc_names();d=len(names);calls=0
 def grad(q):
  global calls
  calls+=1;lp,g=model.log_density_gradient(q);assert np.isfinite(lp) and np.isfinite(g).all();return np.asarray(g)
 def jacobian(q,scale):
  H=np.empty((d,d))
  for k in range(d):
   h=scale*(1+abs(q[k]));delta=np.eye(d)[k]*h;H[:,k]=-(grad(q+delta)-grad(q-delta))/(2*h)
  return H
 block=[k for k,n in enumerate(names) if n.startswith('beta.') or n.startswith('f_tilde.')];records=[];block_matrices=[];traces=[];sigmas=[]
 for number,(count,position,gradient) in enumerate(snaps):
  q=np.array(json.loads(position));g=np.array(json.loads(gradient));error=float(np.max(np.abs(grad(q)-g)/(1+np.abs(g))));assert error<1e-10
  H=jacobian(q,1e-4);H2=jacobian(q,5e-5);sym_error=float(np.linalg.norm(H-H.T)/max(np.linalg.norm(H),1e-300));step_error=float(np.linalg.norm(H-H2)/max(np.linalg.norm(H2),1e-300));P=(H2+H2.T)/2;eig=np.linalg.eigvalsh(P)
  r=dict(number=number,window_observation=int(count),position=q.tolist(),recorded_gradient_error=error,hessian=H.tolist(),hessian_half_step=H2.tolist(),symmetry_error=sym_error,step_error=step_error,full_eigenvalues=eig.tolist())
  if len(block)>=2:
   Q=P[np.ix_(block,block)];block_matrices.append(Q);traces.append(float(np.trace(Q)))
   if 'sigma' in names:sigmas.append(float(np.exp(q[names.index('sigma')])))
  records.append(r)
 summary=dict(**j,coordinates=names,snapshots=len(records),offline_gradient_calls=calls,max_recorded_gradient_error=max(r['recorded_gradient_error'] for r in records),max_symmetry_error=max(r['symmetry_error'] for r in records),max_step_error=max(r['step_error'] for r in records),full_min_eigenvalue=min(min(r['full_eigenvalues']) for r in records),block=None)
 if block_matrices:
  Q=np.array(block_matrices);eig=np.linalg.eigvalsh(Q);info=dict(coordinates=[names[k] for k in block],min_eigenvalue=float(eig.min()),positive_definite_all=bool(eig.min()>0))
  if eig.min()>0:
   norm=Q/np.array(traces)[:,None,None];center=norm.mean(0);diags=np.diagonal(Q,axis1=1,axis2=2);corr=Q/np.sqrt(diags[:,:,None]*diags[:,None,:]);ceig=np.linalg.eigvalsh(corr)
   info.update(trace_scale_ratio=float(max(traces)/min(traces)),relative_shape_variation=float(max(np.linalg.norm(v-center)/np.linalg.norm(center) for v in norm)),max_normalized_entry_range=float(np.ptp(corr,axis=0).max()),diagonal_condition_min=float((ceig[:,-1]/ceig[:,0]).min()),diagonal_condition_max=float((ceig[:,-1]/ceig[:,0]).max()))
   if sigmas:
    scaled=np.array(traces)*np.array(sigmas)**2;info.update(sigma_min=min(sigmas),sigma_max=max(sigmas),trace_times_sigma_squared_relative_range=float(np.ptp(scaled)/np.mean(scaled)))
  summary['block']=info
 rows.append(summary);raw.append(dict(**j,records=records))
out=root/'curvature01'/'result';out.mkdir(exist_ok=False)
for name,data in [('ROWS',rows),('RAW',raw),('INPUTS',inputs)]: (out/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
(out/'SUMMARY.json').write_text(json.dumps(dict(seconds=time.monotonic()-start,gradient_calls=sum(r['offline_gradient_calls'] for r in rows),rows=rows),indent=2)+'\n');print(json.dumps(rows,indent=2))
