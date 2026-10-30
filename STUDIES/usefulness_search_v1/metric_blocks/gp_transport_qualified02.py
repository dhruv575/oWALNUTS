import hashlib,json
from pathlib import Path
import numpy as np,bridgestan as bs
from quadratic_transport import fit,encode,decode,score,logdet
from native_common import model_files
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_qualified02';r.mkdir(exist_ok=False)
prior=json.loads((l/'quadratic_transport02/SUMMARY.json').read_text());key=next(k for k in prior['inputs'] if k.endswith('/quadratic_transport.py'));assert hashlib.sha256((p/'quadratic_transport.py').read_bytes()).hexdigest()==prior['inputs'][key]
so,data,source=model_files('gp_pois_regr-gp_pois_regr');target=bs.StanModel(str(so),data=data.read_text(),seed=1);hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [so,data,source,p/'quadratic_transport.py',p/'gp_transport_qualified02.py',p/'GP-TRANSPORT-QUALIFIED-PROTOCOL.md']};rows=[];calls=dict(gradient=0,density=0)
for fold in range(4):
    train_seed=946200001+2*fold;test_seed=train_seed+1;arrays=[]
    for seed in [train_seed,test_seed]:
        d=l/f'gp_fresh_comparison01/low_rank-{seed}';summary=json.loads((d/'SUMMARY.json').read_text());assert summary['passed']
        for f,h in summary['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
        for f in [d/'SUMMARY.json',d/'DRAWS-STATS.npz']:hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
        arrays.append(np.load(d/'DRAWS-STATS.npz')['sample_stats__unconstrained_draw'])
    train=arrays[0][:,:100].reshape(-1,13);q=arrays[1].reshape(-1,13);m=fit(train);folder=r/f'fold-{fold}';folder.mkdir();(folder/'MAP.json').write_text(json.dumps(m,indent=2)+'\n')
    g=np.asarray([target.log_density_gradient(x)[1] for x in q]);calls['gradient']+=len(q);assert np.isfinite(g).all();np.savez_compressed(folder/'INPUTS.npz',train=train,q=q,gradient=g);metrics={}
    for arm,affine in [('affine',True),('quadratic',False)]:
        z=encode(q,m,affine);gz=score(q,g,m,affine);assert np.isfinite(z).all() and np.isfinite(gz).all()
        if not affine:assert np.max(abs(decode(z,m)-q))/(1+np.max(abs(q)))<1e-9
        metrics[arm]=dict(score_discrepancy=float(np.mean((gz+z)**2)),cross_entropy_per_dimension=float(.5*np.mean(z*z)+logdet(m,affine)/13));np.savez_compressed(folder/(arm+'.npz'),z=z,score=gz)
    checks=[];z=encode(q,m);gz=score(q,g,m)
    for index in [0,len(q)//2,len(q)-1]:
        point=z[index:index+1];fd=[];jac=[]
        for j in range(13):
            delta=np.zeros_like(point);delta[0,j]=1e-3;qa=decode(point+delta,m);qb=decode(point-delta,m);fd.append((target.log_density(qa[0])-target.log_density(qb[0]))/2e-3);calls['density']+=2;jac.append((qa[0]-qb[0])/2e-3)
        error=float(np.max(abs(gz[index]-fd)/(1+abs(gz[index])+abs(np.asarray(fd)))));det_error=float(abs(np.linalg.det(np.asarray(jac).T)/np.exp(logdet(m))-1));assert error<1e-4 and det_error<1e-4;checks.append(dict(index=index,gradient_error=error,determinant_error=det_error))
    ratio=metrics['quadratic']['score_discrepancy']/metrics['affine']['score_discrepancy'];loss=metrics['quadratic']['cross_entropy_per_dimension']-metrics['affine']['cross_entropy_per_dimension'];row=dict(fold=fold,train_seed=train_seed,evaluation_seed=test_seed,metrics=metrics,score_ratio=ratio,cross_entropy_change=loss,checks=checks,advance=ratio<.8 and loss<=.1);rows.append(row);print(json.dumps(row),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,advance=all(x['advance'] for x in rows),rows=rows,diagnostic_calls=calls,inputs=hashes),indent=2,allow_nan=False)+'\n')
