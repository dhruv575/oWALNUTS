import hashlib,json,traceback
from pathlib import Path
import numpy as np
from quadratic_transport import fit,encode,decode,score,logdet
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'quadratic_transport02';r.mkdir(exist_ok=False)
rng=np.random.default_rng(945100001);q=rng.normal(size=(1000,4));q[:,1]+=2*(q[:,0]**2-1);m=fit(q);z=encode(q,m);assert np.max(abs(decode(z,m)-q))/(1+np.max(abs(q)))<1e-9
point=np.array([[.1,-.2,.3,-.4]]);physical=decode(point,m);g=score(physical,-physical,m)[0];fd=[];jac=[]
for j in range(4):
    d=np.zeros_like(point);d[0,j]=1e-6;a=decode(point+d,m);b=decode(point-d,m);fd.append(float((-.5*np.sum(a*a)+.5*np.sum(b*b))/2e-6));jac.append((a[0]-b[0])/2e-6)
gradient_error=float(max(abs(g-np.asarray(fd))));det_ratio=float(np.linalg.det(np.asarray(jac).T)/np.exp(logdet(m)));assert gradient_error<1e-5 and abs(det_ratio-1)<1e-5
(r/'CHECKS.json').write_text(json.dumps(dict(passed=True,gradient_error=gradient_error,determinant_ratio=det_ratio),indent=2));rows=[];hashes={str(p/n):hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['quadratic_transport.py','quadratic_transport_diagnostic.py','QUADRATIC-TRANSPORT-PROTOCOL.md']}
for name in ['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']:
    folder=r/name;folder.mkdir();prior=l/'native_prefix02'/name;files=[prior/'short.npz',prior/'long.npz',prior/'SUMMARY.json',l/'matched_geometry01'/name/'SUMMARY.json']
    for f in files:
        if f.exists():hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    assert json.loads(files[2].read_text())['passed'];qualification=json.loads(files[3].read_text())['native']['passed'] if files[3].exists() else False;row=dict(model=name,prior_native_qualified=qualification,qualification_artifact_present=files[3].exists())
    try:
        with np.load(files[0]) as data:train=data['sample_stats__unconstrained_draw'].copy()
        with np.load(files[1]) as data:q=data['sample_stats__unconstrained_draw'].copy();g=data['sample_stats__gradient'].copy()
        assert np.array_equal(train,q[:,:100]);assert train.shape[:2]==(4,100) and q.shape[:2]==(4,2100);d=q.shape[-1];m=fit(train.reshape(-1,d));(folder/'MAP.json').write_text(json.dumps(m,indent=2));q=q[:,100:].reshape(-1,d);g=g[:,100:].reshape(-1,d);metrics={}
        for arm,affine in [('affine',True),('quadratic',False)]:
            z=encode(q,m,affine);gz=score(q,g,m,affine);assert np.isfinite(z).all() and np.isfinite(gz).all()
            if not affine:assert np.max(abs(decode(z,m)-q))/(1+np.max(abs(q)))<1e-9
            moments=(z-z.mean(0))/z.std(0);metrics[arm]=dict(score_discrepancy=float(np.mean((gz+z)**2)),skewness_squared=float(np.mean(np.mean(moments**3,axis=0)**2)),cross_entropy_per_dimension=float(.5*np.mean(z*z)+logdet(m,affine)/d),max_covariance_error=float(np.max(abs(np.cov(z,rowvar=False)-np.eye(d)))))
            np.savez_compressed(folder/(arm+'.npz'),z=z,score=gz)
        ratio=metrics['quadratic']['score_discrepancy']/metrics['affine']['score_discrepancy'];loss=metrics['quadratic']['cross_entropy_per_dimension']-metrics['affine']['cross_entropy_per_dimension'];row.update(passed=True,metrics=metrics,score_ratio=ratio,cross_entropy_change=loss,advance=qualification and name!='sblrc-blr' and ratio<.8 and loss<=.1)
    except Exception:row.update(passed=False,advance=False,error=traceback.format_exc());(folder/'ERROR.txt').write_text(row['error'])
    rows.append(row);print(json.dumps(row),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items());(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows,inputs=hashes,unchanged=True),indent=2,allow_nan=False)+'\n')
