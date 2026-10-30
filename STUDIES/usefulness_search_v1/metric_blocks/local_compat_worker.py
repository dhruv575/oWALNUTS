import hashlib,importlib.metadata,json,platform,subprocess,sys,tarfile,zipfile
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
study=Path(__file__).resolve().parent;root=Path(sys.argv[1]);inputs=study/'local_recovery/inputs'
so=next((inputs/'dependencies').glob('*-sblrc-blr_model.so'));data=next((inputs/'dependencies').glob('*-sblrc-blr.data.json'))
binary=inputs/'online-binary';target=bs.StanModel(str(so),data=data.read_text(),seed=1)
assert target.param_unc_names()==[f'beta.{i}' for i in range(1,6)]+['sigma']
d=json.loads(data.read_text());x=np.asarray(d['X']);y=np.asarray(d['y']);n,p=x.shape;rng=np.random.default_rng(929699999);diff=[];errors=[]
for _ in range(64):
    beta=np.ones(p)+rng.normal(size=p)*.001;t=rng.uniform(-.4,.4);ss=np.exp(2*t);q=np.r_[beta,t]
    lp,g=target.log_density_gradient(q);r=y-x@beta;expected=-beta@beta/200-ss/200-(n-1)*t-r@r/(2*ss)
    grad=np.r_[-beta/100+x.T@r/ss,-ss/100-(n-1)+r@r/ss]
    diff.append(lp-expected);errors.append(float(np.max(np.abs(g-grad)/(1+np.abs(g)))))
de=float(np.max(np.abs(np.array(diff)-diff[0])));ge=max(errors)
(root/'DENSITY.json').write_text(json.dumps(dict(passed=de<=1e-6 and ge<=1e-7,density_error=de,gradient_error=ge),indent=2)+'\n')
assert de<=1e-6 and ge<=1e-7
archive=study/'hybrid01_archive/evidence.tar-s3-restored.tar.gz';receipt=json.loads((study/'hybrid01_archive/S3-VERIFICATION.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['sha256'];comparisons={}
with tarfile.open(archive) as tar:
    manifest=json.load(tar.extractfile('EVIDENCE-MANIFEST.json'))
    def archived(name):
        raw=tar.extractfile(name).read();assert hashlib.sha256(raw).hexdigest()==manifest[name]['sha256'];return json.loads(raw)
    refs=archived('REFERENCES.json');ref=refs['sblrc-blr'];assert ref['passed']
    for arm in ['pilot','auto']:
        name='runs/sblrc-blr-929300001-'+arm;args=archived(name+'/INPUT.json');original=archived(name+'/RESULT.json')
        args.update(model=str(so),data=str(data));ip=root/(arm+'-INPUT.json');op=root/(arm+'-RESULT.json')
        ip.write_text(json.dumps(args,indent=2)+'\n');subprocess.run([str(binary),str(ip),str(op)],check=True)
        result=json.loads(op.read_text());a=np.asarray(result['draws']);assert np.isfinite(a).all()
        comparisons[arm]=dict(exact_non_timing={k:v for k,v in result.items() if k!='seconds'}=={k:v for k,v in original.items() if k!='seconds'},target_calls=result['target_calls'])
        if arm=='auto':
            a[:,:,-1]=np.exp(a[:,:,-1]);ds=az.convert_to_dataset({'p':a});mean=a.mean((0,1));sd=a.reshape(-1,6).std(0,ddof=1)
            rh=np.asarray(az.rhat(ds,method='rank').p);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);mcse=np.asarray(az.mcse(ds,method='mean').p)
            z=np.abs(mean-ref['mean'])/np.sqrt(mcse**2+np.array(ref['mcse'])**2);delta=np.abs(mean-ref['mean'])/ref['sd'];se=np.abs(sd/ref['sd']-1)
            passed=max(rh)<=1.01 and min(bulk)>=400 and min(tail)>=400 and result['retained_divergences']==0 and max(z)<=4.5 and max(delta)<=.1 and max(se)<=.1
            comparisons[arm].update(passed=bool(passed),rhat=float(max(rh)),bulk=float(min(bulk)),tail=float(min(tail)),divergences=result['retained_divergences'],max_z=float(max(z)),max_mean_sd=float(max(delta)),max_sd_error=float(max(se)))
environment=dict(python=sys.version,platform=platform.platform(),packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()})
(root/'ENVIRONMENT.json').write_text(json.dumps(environment,indent=2)+'\n')
summary=dict(passed=comparisons['auto']['passed'],comparisons=comparisons,density_error=de,gradient_error=ge,parent_archive_sha256=receipt['sha256'],
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),so,data,binary,study/'LOCAL-COMPATIBILITY.md']},exposed_environment_check_only=True)
(root/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));assert summary['passed']
