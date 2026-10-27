"""One bounded API/target development preflight; never a calibration study."""
import argparse,hashlib,inspect,json,os,subprocess,sys,time,traceback
from pathlib import Path
import numpy as np
from common import fixture,data,extract,require_finite

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--native-python',required=True);p.add_argument('--bridgestan-sdk',required=True);a=p.parse_args()
 out=Path(a.output);out.mkdir(exist_ok=False);r=dict(status='running',phase='inventory',started=time.time());
 def save(): (out/'result.json').write_text(json.dumps(r,indent=2,allow_nan=False))
 save()
 try:
  bundle=Path(__file__).parent
  manifest=json.loads((bundle/'manifest.json').read_text())
  for name,digest in manifest.items():
   if sha(bundle/name)!=digest:raise RuntimeError('source manifest differs: '+name)
  if os.path.abspath(sys.prefix)!='/home/ubuntu/venv':raise RuntimeError('unexpected shared interpreter prefix')
  r['source_manifest']=manifest
  sdk=Path(a.bridgestan_sdk)
  if not (sdk/'Makefile').is_file():raise RuntimeError('preinstalled BridgeStan SDK required; downloads forbidden')
  os.environ['BRIDGESTAN']=str(sdk);os.environ['TMPDIR']=str(out/'tmp');(out/'tmp').mkdir()
  import tempfile;tempfile.tempdir=None
  import nutpie,bridgestan
  if nutpie.__version__!='0.16.8':raise RuntimeError('nutpie version differs')
  r['runtime_binaries']={str(f):sha(f) for package in (nutpie,bridgestan) for f in Path(package.__file__).parent.rglob('*.so')}
  r['inventory']=dict(prefix=sys.prefix,executable=sys.executable,nutpie=nutpie.__version__,bridgestan=bridgestan.__version__,numpy=np.__version__,sdk=str(sdk),sdk_makefile_sha256=sha(sdk/'Makefile'),sample_signature=str(inspect.signature(nutpie.sample)),compile_signature=str(inspect.signature(nutpie.compile_stan_model)))
  for name,obj in [('sample',nutpie.sample),('compile',nutpie.compile_stan_model),('bridgestan_compile',bridgestan.compile_model)]:
   source=inspect.getsource(obj);(out/(name+'-installed.py')).write_text(source)
  r['phase']='native fixtures';save()
  subprocess.run([os.path.abspath(a.native_python),str(Path(__file__).with_name('native_fixture.py')),str(out)],check=True)
  native=json.loads((out/'native-fixtures.json').read_text())
  r['phase']='BridgeStan compile and parity';save()
  source=Path(__file__).with_name('model.stan');modelcopy=out/'model.stan';modelcopy.write_bytes(source.read_bytes())
  lib=bridgestan.compile_model(str(modelcopy),make_args=['STAN_THREADS=true'])
  r['bridgestan_library']=dict(path=str(lib),sha256=sha(lib));r['parity']=[]
  for n in (12,250):
   y,_=fixture(n);model=bridgestan.StanModel(str(lib),json.dumps(data(y)))
   offsets=[]
   for variant in (0,1,-1):
    _,q=fixture(n,variant);lp,g=model.log_density_gradient(q,propto=False,jacobian=True)
    expected=next(x for x in native['rows'] if x['n']==n and x['variant']==variant)
    require_finite(lp,g,expected['lp'],expected['gradient'])
    error=float(np.max(np.abs(g-np.array(expected['gradient']))/(1+np.abs(g))));offsets.append(float(lp-expected['lp']))
    fd=[]
    for j in (range(15) if n==12 else [0,1,2,3,4,127,252]):
     h=1e-7 if j==2 else 1e-5;plus=q.copy();minus=q.copy();plus[j]+=h;minus[j]-=h
     numerical=(model.log_density(plus,propto=False,jacobian=True)-model.log_density(minus,propto=False,jacobian=True))/(2*h)
     fd.append(abs(numerical-g[j])/(1+abs(g[j])))
    require_finite(error,fd,offsets)
    r['parity'].append(dict(n=n,variant=variant,lp_offset=offsets[-1],gradient_relative_error=error,finite_difference_error=float(max(fd))))
    if error>1e-8 or max(fd)>1e-5:raise RuntimeError('gradient parity failed')
   if np.ptp(offsets)>1e-8:raise RuntimeError('density offset not constant')
  r['phase']='public nutpie compile';save()
  compiled=nutpie.compile_stan_model(code=source.read_text(encoding='utf-8-sig'),cleanup=False)
  r['compiled_libraries']={str(f):sha(f) for f in (out/'tmp').rglob('*.so')}
  if not r['compiled_libraries']:raise RuntimeError('compiled library identity unavailable')
  r['with_data_signature']=str(inspect.signature(compiled.with_data))
  (out/'with-data-installed.py').write_text(inspect.getsource(type(compiled).with_data))
  y,_=fixture(12);model=compiled.with_data(seed=99371041,**data(y))
  options=dict(draws=50,tune=200,chains=4,cores=4,seed=99371042,save_warmup=True,progress_bar=False,target_accept=.8,maxdepth=10,store_mass_matrix=True,low_rank_modified_mass_matrix=False,transform_adapt=False)
  r['options']=options;r['model_seed']=99371041;r['phase']='development fit';save()
  trace=nutpie.sample(model,**options)
  joint,diag=extract(trace);np.save(out/'joint.npy',joint);trace.to_netcdf(out/'trace.nc')
  z=np.asarray(trace.posterior.z.transpose('chain','draw',...));mu=joint[:,:,0];sigma=np.exp(joint[:,:,1]);h=mu+sigma*z[:,:,0]/np.sqrt(1-.95**2)
  for j in range(1,12):h=mu+.95*(h-mu)+sigma*z[:,:,j]
  require_finite(h,joint)
  err=float(np.max(abs(h-joint[:,:,3])))
  require_finite(err)
  if err>1e-10:raise RuntimeError('terminal latent reconstruction failed')
  r.update(status='complete',phase='complete',diagnostics=diag,h_last_reconstruction_error=err,variables=list(trace.sample_stats),joint_sha256=sha(out/'joint.npy'),api_and_target_verified=True,engine_options={k:options[k] for k in ['target_accept','maxdepth','store_mass_matrix','low_rank_modified_mass_matrix','transform_adapt']},limitations=['Tiny fit is API/extraction validation, not convergence qualification.','Seed arguments and installed forwarding source recorded; internal chain seed derivation not independently audited.'])
 except BaseException as e:r.update(status='failed',error=repr(e),traceback=traceback.format_exc())
 finally:r['finished']=time.time();save()
 return 0 if r['status']=='complete' else 1
if __name__=='__main__':sys.exit(main())
