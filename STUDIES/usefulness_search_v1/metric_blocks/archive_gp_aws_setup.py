import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs
from bounded_transport import fit,decode,score,logdet
from native_common import model_files
p=Path(__file__).resolve().parent;l=p/'local_recovery';pilot=l/'gp_aws_pilot_qualification01/evidence';targets=l/'gp_aws_map_equivalence01';s=json.loads((pilot/'SUMMARY.json').read_text());ref=json.loads((l/'gp_fresh_reference01/SUMMARY.json').read_text());so,_,_=model_files('gp_pois_regr-gp_pois_regr');tso=l/'bounded_gp_target01/bounded_gp_model.so';rows=[]
def near(a,b):
 if isinstance(a,dict):return a.keys()==b.keys() and all(near(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(near(x,y) for x,y in zip(a,b))
 if isinstance(a,(int,float)):return bool(np.isclose(a,b,rtol=1e-10,atol=1e-10))
 return a==b
for item in s['rows']:
 i=item['scenario'];d=pilot/f'scenario-{i}';saved=np.load(d/'DRAWS-FUNCTIONALS.npz');q=saved['q'];v=saved['values'];ds=az.convert_to_dataset({'p':v});stats=dict(mean=v.mean((0,1)),sd=v.reshape(-1,24).std(0,ddof=1),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),rhat=np.asarray(az.rhat(ds,method='rank').p),mcse=np.asarray(az.mcse(ds,method='mean').p))
 for k,value in stats.items():assert np.allclose(value,item['stats'][k],rtol=1e-12,atol=1e-12)
 for t,m in [('affine','walnuts_dense'),('affine','diag'),('bounded','walnuts_dense'),('bounded','diag')]:
  raw=json.loads((l/f'gp_aws_full_remote01/results/{i}-{t}-{m}/PILOT-RAW.json').read_text());assert np.array_equal(q,raw['draws']) and raw['target_calls']==item['calls']['gradient'] and raw['retained_divergences']==0
 rr=next(x['stats'] for x in ref['references'] if x['scenario']==i);z=abs(stats['mean']-rr['mean'])/np.sqrt(stats['mcse']**2+np.asarray(rr['mcse'])**2);assert max(z)<=4 and max(abs(stats['mean']-rr['mean'])/rr['sd'])<=.1 and max(abs(stats['sd']/rr['sd']-1))<=.1 and max(stats['rhat'])<=1.01 and min(stats['bulk'])>=400 and min(stats['tail'])>=400
 model=bs.StanModel(str(so),data=(l/f'gp_fresh_data01/scenario-{i}/DATA.json').read_text(),seed=1);names=model.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,12)]]
 physical=np.asarray([model.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,13)]).reshape(4,2000,13);physical=np.concatenate([physical,np.exp(physical[:,:,2:])],axis=2);assert np.allclose(physical,v,rtol=1e-12,atol=1e-12)
 m=json.loads((d/'MAP.json').read_text());assert near(fit(q[:,:100].reshape(-1,13)),m)
 for affine in [True,False]:
  arm='affine' if affine else 'bounded';target=bs.StanModel(str(tso),data=(d/(arm+'.json')).read_text(),seed=1);names=target.param_names(include_tp=True,include_gq=False);qi=[names.index(f'q.{j}') for j in range(1,14)];points=np.load(targets/f'{i}-{arm}-points.npz')['z'];assert points.shape==(48,13)
  for point in points:
   actual=np.asarray(target.param_constrain(point,include_tp=True,include_gq=False))[qi];expected=point@np.asarray(m['L']).T+np.asarray(m['mu']) if affine else decode(point[None],m)[0];lp,g=target.log_density_gradient(point,propto=False,jacobian=True);olp,og=model.log_density_gradient(actual,propto=False,jacobian=True);eg=og@np.asarray(m['L']) if affine else score(actual[None],np.asarray(og)[None],m)[0]
   assert max(abs(actual-expected)/(1+abs(actual)))<=1e-9 and abs(lp-olp-logdet(m,affine))<=1e-6 and max(abs(g-eg)/(1+abs(eg)))<=1e-5
 rows.append(dict(scenario=i,passed=True,points=96))
out=l/'gp_aws_setup_archive01';out.mkdir(exist_ok=False);(out/'AUDIT.json').write_text(json.dumps(dict(passed=True,rows=rows),indent=2)+'\n');files={}
for folder in [pilot.parent,targets]:
 for f in folder.rglob('*'):
  if f.is_file():files[str(f.relative_to(p))]=f
for name in ['GP-AWS-PILOT-QUALIFICATION-PROTOCOL.md','GP-AWS-MAP-PROTOCOL.md','qualify_gp_aws_pilots.py','run_gp_aws_pilot_qualification.py','check_gp_aws_maps.py','archive_gp_aws_setup.py','bounded_transport.py','local_recovery/gp_aws_full_failed_archive01/VERIFICATION.json','local_recovery/gp_fresh_reference_archive01/VERIFICATION.json','local_recovery/gp_aws_setup_archive01/AUDIT.json']:files[name]=p/name
manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()};archive=out/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);tar.addfile(info,io.BytesIO(b))
 for n,f in files.items():tar.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as tar:
 for n,m in manifest.items():
  b=tar.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local raw-pilot/replay/map/target audit and archive; compiled models and references separate; not S3')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
