"""Plan/run eight target-only profiles; validate JAX separately after timing."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():return {p.name:sha(p) for p in ROOT.glob('*.py')}
def save(p,x):
    with Path(p).open('x') as f:json.dump(x,f,indent=2,allow_nan=False)
def verify(path,plan):
    if sha(path)!=path.with_suffix('.sha256').read_text().strip():raise ValueError('Plan digest changed')
    if sources()!=plan['source_sha256'] or any(sha(k)!=v for k,v in plan['bound_files'].items()):raise ValueError('Source/dependency drift')
def create(out,python,adapter,extension):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    bound={str(Path(f).resolve()):sha(f) for f in [python,adapter,extension]}
    cells=[]
    for i,t in enumerate([32,128,512,1000]):
        for solve in (['original','combined'] if i%2==0 else ['combined','original']):
            name=f'T{t}-{solve}'
            command=[str(Path(python).resolve()),str(ROOT/'hardware_control.py'),'--cpus','0','--record',str(out/(name+'-hardware.json')),'--timeout','600','--',str(Path(python).resolve()),str(ROOT/'profile_whitening_cfunc.py'),'--periods',str(t),'--solve',solve,'--out',str(out/(name+'.json')),'--calls-per-block','300','--blocks','5']
            cells.append(dict(id=name,periods=t,solve=solve,command=command))
    plan=dict(phase='target-only-exploratory',qualified=False,frozen=True,source_sha256=sources(),bound_files=bound,cells=cells,cache_policy='Freshprocess per cell, existing disk caches retained; balanced order; all compile/setup costs preserved',scope='No MCMC; no workflow speed inference from callback timing')
    save(out/'plan.json',plan);(out/'plan.sha256').write_text(sha(out/'plan.json')+'\n')
def execute(path):
    path=Path(path);plan=json.loads(path.read_text());verify(path,plan)
    for cell in plan['cells']:
        status=path.parent/(cell['id']+'-status.json');marker=path.parent/(cell['id']+'-started.json')
        if marker.exists() or status.exists():raise ValueError('Already attempted')
        save(marker,dict(plan_sha256=sha(path),id=cell['id']));verify(path,plan)
        with (path.parent/(cell['id']+'.log')).open('x') as log:r=subprocess.run(cell['command'],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
        verify(path,plan);save(status,dict(returncode=r.returncode,id=cell['id']))
        if r.returncode:raise RuntimeError('Profilefailed, remainingcells unattempted')
def validate(path,out):
    # Explicitly separate validation process; never imported by timed worker.
    import numpy as np
    import jax
    jax.config.update('jax_enable_x64',True)
    import jax.numpy as jnp
    from local_conditional_whitening import jax_log_density
    path=Path(path);plan=json.loads(path.read_text());verify(path,plan);rows=[];profiles={}
    for cell in plan['cells']:
        f=path.parent/(cell['id']+'.json');r=json.loads(f.read_text());profiles[cell['id']]=r
        vg=jax.jit(jax.value_and_grad(lambda q:jax_log_density(q,r['data'])))
        for point in r['validation_points']:
            value,gradient=vg(jnp.asarray(point['position']));np.testing.assert_allclose(value,point['value'],rtol=1e-9,atol=1e-7);np.testing.assert_allclose(gradient,point['gradient'],rtol=1e-7,atol=2e-6)
        rows.append(dict(id=cell['id'],passed=True,profile_sha256=sha(f)))
    for t in [32,128,512,1000]:
        a,b=[profiles[f'T{t}-{s}'] for s in ['original','combined']]
        if a['data_sha256']!=b['data_sha256']:raise ValueError('Paireddata mismatch')
        for x,y in zip(a['validation_points'],b['validation_points']):np.testing.assert_array_equal(x['position'],y['position'])
    save(out,dict(phase='target-only-exploratory',qualified=False,validation=rows))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['plan','run','validate']);p.add_argument('--out',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--python');p.add_argument('--adapter');p.add_argument('--extension');a=p.parse_args()
    if a.action=='plan':create(a.out,a.python,a.adapter,a.extension)
    elif a.action=='run':execute(a.plan)
    else:validate(a.plan,a.out)
