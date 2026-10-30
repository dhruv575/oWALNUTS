import concurrent.futures,ctypes,hashlib,json,shutil,subprocess,sys
from pathlib import Path
import numpy as np
import bridgestan as bs
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=Path(sys.argv[1]);build=local/'threaded_build01'
summary=json.loads((build/'SUMMARY.json').read_text());assert summary['passed']
original=build/'sblrc-blr_model.so';assert hashlib.sha256(original.read_bytes()).hexdigest()==summary['new_library_sha256']
toolchain=Path(json.loads((build/'SUPERVISION.json').read_text())['build_directory'])/'bridgestan-2.9.0'
shutil.copy2(toolchain/'src/bridgestan.h',root/'bridgestan.h');shutil.copy2(study/'count_target.cpp',root/'count_target.cpp')
(root/'original_path.h').write_text('#define ORIGINAL_LIBRARY '+json.dumps(str(original))+'\n')
shim=root/'counted_model.so'
command=['g++','-shared','-fPIC','-O2','-std=c++17',str(root/'count_target.cpp'),'-Wl,--no-as-needed',str(original),'-Wl,--as-needed','-ldl','-o',str(shim)]
subprocess.run(command,check=True);(root/'BUILD.json').write_text(json.dumps(dict(command=command,library_sha256=hashlib.sha256(shim.read_bytes()).hexdigest()),indent=2)+'\n')
counter=ctypes.CDLL(str(shim));counter.ow_target_calls.argtypes=[ctypes.c_uint];counter.ow_target_calls.restype=ctypes.c_uint64;counter.ow_reset_target_calls.argtypes=[];counter.ow_reset_target_calls.restype=None
def counts():return [counter.ow_target_calls(i) for i in range(4)]
data=(build/'sblrc-blr.data.json').read_text();old=bs.StanModel(str(original),data=data,seed=1);new=bs.StanModel(str(shim),data=data,seed=1)
points=np.asarray(summary['points']);q=points[0];rows=[]
methods=[('log_density',(q,)),('log_density_gradient',(q,)),('log_density_hessian',(q,)),('log_density_hessian_vector_product',(q,np.ones(6)))]
for i,(name,args) in enumerate(methods):
    a=getattr(old,name)(*args);counter.ow_reset_target_calls();b=getattr(new,name)(*args);expected=[0]*4;expected[i]=1
    aa=a if isinstance(a,tuple) else (a,);bb=b if isinstance(b,tuple) else (b,)
    same=len(aa)==len(bb) and all(np.array_equal(x,y) for x,y in zip(aa,bb));observed=counts()
    rows.append(dict(test=name,passed=same and observed==expected,counts=observed));assert rows[-1]['passed']
counter.ow_reset_target_calls();failed=False
try:new.log_density_gradient(np.full(6,np.nan))
except Exception:failed=True
rows.append(dict(test='failed_attempt',passed=failed and counts()==[0,1,0,0],counts=counts()));assert rows[-1]['passed']
models=[bs.StanModel(str(shim),data=data,seed=1) for _ in range(4)]
expected=[old.log_density_gradient(q) for q in points]
def run(model):return [model.log_density_gradient(q) for q in points]
counter.ow_reset_target_calls()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:outputs=list(pool.map(run,models))
same=all(np.array_equal(a[0],b[0]) and np.array_equal(a[1],b[1]) for output in outputs for a,b in zip(output,expected))
rows.append(dict(test='parallel_256',passed=same and counts()==[0,256,0,0],counts=counts()));assert rows[-1]['passed']
(root/'API-CHECKS.json').write_text(json.dumps(rows,indent=2)+'\n')
source=(study/'nutpie_native_worker.py').read_text()
source=source.replace('import hashlib,','import ctypes,hashlib,',1)
needle="library=_lib.StanLibrary(str(paths['model']))"
replacement="counter=ctypes.CDLL(str(paths['model']))\ncounter.ow_target_calls.argtypes=[ctypes.c_uint];counter.ow_target_calls.restype=ctypes.c_uint64\ncounter.ow_reset_target_calls.argtypes=[];counter.ow_reset_target_calls.restype=None\ncounter.ow_reset_target_calls()\n"+needle
assert source.count(needle)==1;source=source.replace(needle,replacement)
needle="out.write_text(json.dumps(result,allow_nan=False)+'\\n')"
replacement="result['target_api_calls']={name:counter.ow_target_calls(i) for i,name in enumerate(['value','gradient','hessian','hvp'])}\nresult['target_call_scope']='Attempted BridgeStan C-ABI evaluations, including initialization and failed calls; kinds reported separately.'\n"+needle
assert source.count(needle)==1;source=source.replace(needle,replacement)
worker=root/'counted_worker.py';worker.write_text(source);parity=[]
for arm in ['draw_diag','diag','low_rank']:
    prior=local/'nativepreflight03'/arm;folder=root/arm;folder.mkdir();inp=json.loads((prior/'INPUT.json').read_text());inp['model']=str(shim)
    ip=folder/'INPUT.json';op=folder/'RESULT.json';ip.write_text(json.dumps(inp,indent=2)+'\n')
    with (folder/'worker.log').open('w') as log:subprocess.run([sys.executable,str(worker),str(ip),str(op)],check=True,stdout=log,stderr=subprocess.STDOUT)
    a=json.loads((prior/'RESULT.json').read_text());b=json.loads(op.read_text());same=a['draws']==b['draws'] and a['retained_divergences']==b['retained_divergences']
    with np.load(folder/'NATIVE-STATS.npz') as z:steps=int(z['sample_stats__n_steps'].sum()+z['warmup_sample_stats__n_steps'].sum())
    c=b['target_api_calls'];passed=same and c['gradient']>0 and c['gradient']>=steps and c['hessian']==c['hvp']==0
    parity.append(dict(arm=arm,passed=passed,exact_draws_and_divergences=same,calls=c,native_steps=steps,gradient_minus_steps=c['gradient']-steps));assert passed
result=dict(passed=True,api_checks=rows,sampling_parity=parity,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),study/'count_target.cpp',study/'COUNTED-NATIVE-PREFLIGHT.md',study/'nutpie_native_worker.py',original,root/'bridgestan.h']})
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
