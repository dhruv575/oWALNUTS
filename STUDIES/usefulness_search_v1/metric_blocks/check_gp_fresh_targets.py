import hashlib,json
from pathlib import Path
import numpy as np,bridgestan as bs
from bounded_transport import encode,decode,score,logdet
from native_common import model_files
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_fresh_target01';r.mkdir(exist_ok=False)
pilots=json.loads((l/'gp_fresh_pilot01/SUMMARY.json').read_text());assert pilots['all_qualified'];so,_,source=model_files('gp_pois_regr-gp_pois_regr')
build=json.loads((l/'bounded_gp_target01/SUMMARY.json').read_text());transformed_so=Path(build['library']);assert build['passed'] and hashlib.sha256(transformed_so.read_bytes()).hexdigest()==build['library_sha256']
inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),p/'GP-FRESH-TARGET-PROTOCOL.md',p/'bounded_transport.py',so,source,transformed_so]};rows=[]
for scenario in range(4):
    data=l/f'gp_fresh_data01/scenario-{scenario}/DATA.json';folder=l/f'gp_fresh_pilot01/scenario-{scenario}';mf=folder/'MAP.json';refdraws=l/f'gp_fresh_reference01/{scenario}-0/DRAWS-STATS.npz'
    for f in [data,mf,refdraws]:inputs[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    m=json.loads(mf.read_text());original=bs.StanModel(str(so),data=data.read_text(),seed=1);on=original.param_names(include_tp=True,include_gq=False);physical_names=['rho','alpha']+[f'f.{j}' for j in range(1,12)];oi=[on.index(n) for n in physical_names]
    q=np.load(refdraws)['sample_stats__unconstrained_draw'].reshape(-1,13)[np.linspace(0,31999,32,dtype=int)];fresh=np.random.default_rng(949700001+scenario).normal(size=(16,13))
    for affine in [True,False]:
        arm='affine' if affine else 'bounded';df=folder/(arm+'.json');inputs[str(df)]=hashlib.sha256(df.read_bytes()).hexdigest();target=bs.StanModel(str(transformed_so),data=df.read_text(),seed=1);tn=target.param_names(include_tp=True,include_gq=False);qi=[tn.index(f'q.{j}') for j in range(1,14)];fi=[tn.index(n) for n in physical_names]
        z=np.concatenate([encode(q,m,affine),fresh]);errors=[]
        for point in z:
            constrained=target.param_constrain(point,include_tp=True,include_gq=False);physical=np.asarray(constrained)[qi];expected_q=point@np.asarray(m['L']).T+np.asarray(m['mu']) if affine else decode(point[None],m)[0]
            lp,g=target.log_density_gradient(point,propto=False,jacobian=True);olp,og=original.log_density_gradient(physical,propto=False,jacobian=True);expected_g=og@np.asarray(m['L']) if affine else score(physical[None],np.asarray(og)[None],m)[0]
            of=original.param_constrain(physical,include_tp=True,include_gq=False);a=np.asarray(constrained)[fi];b=np.asarray(of)[oi];a=np.r_[a,np.exp(a[2:])];b=np.r_[b,np.exp(b[2:])]
            e=dict(roundtrip=float(max(abs(physical-expected_q)/(1+abs(physical)))),density=float(abs(lp-olp-logdet(m,affine))),gradient=float(max(abs(g-expected_g)/(1+abs(expected_g)))),functionals=float(max(abs(a-b)/(1+abs(b)))));assert all(np.isfinite(v) for v in e.values());errors.append(e)
        maxima={k:max(x[k] for x in errors) for k in errors[0]};passed=maxima['roundtrip']<=1e-9 and maxima['density']<=1e-6 and maxima['gradient']<=1e-5 and maxima['functionals']<=1e-6
        np.savez_compressed(r/f'{scenario}-{arm}-points.npz',z=z);rows.append(dict(scenario=scenario,arm=arm,passed=passed,maxima=maxima,errors=errors));print(json.dumps(dict(scenario=scenario,arm=arm,passed=passed,maxima=maxima)),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in inputs.items())
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,passed=all(x['passed'] for x in rows),rows=rows,inputs=inputs),indent=2)+'\n')
