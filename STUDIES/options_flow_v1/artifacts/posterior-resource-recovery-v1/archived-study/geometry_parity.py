"""Independent normalized density/gradient parity for Rust geometry arms."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64',True)
import jax.numpy as jnp
from model import simulate
from geometry import FixedGeometry,transformed_log_density

def check(exe):
    cases=[]
    with tempfile.TemporaryDirectory(prefix='owalnuts-geometry-parity-') as tmp:
        folder=Path(tmp)
        for periods in [8,128,1000]:
            fixture=simulate(187+periods,periods,4,1,True);data=fixture['data']
            (folder/'data.json').write_text(json.dumps(data))
            canonical=np.asarray(fixture['truth'])+np.random.default_rng(71).normal(0,.1,len(fixture['truth']))
            for shear in [False,True]:
                geom=FixedGeometry.from_data(data,shear);u=geom.to_transformed(canonical)
                (folder/'q.json').write_text(json.dumps(u.tolist()))
                value,gradient=jax.jit(jax.value_and_grad(lambda z:transformed_log_density(z,data,geom,jnp)))(jnp.asarray(u))
                for prefix in ['', 'autodiff-']:
                    arm=prefix+('fisher-shear' if shear else 'fisher')
                    raw=json.loads(subprocess.check_output([str(exe),'--eval',str(folder/'data.json'),str(folder/'q.json'),arm]))
                    row=dict(periods=periods,arm=arm,value_error=abs(float(value)-raw['logp']),
                             gradient_max_error=float(np.max(np.abs(np.asarray(gradient)-raw['gradient']))))
                    if row['value_error']>1e-8 or row['gradient_max_error']>1e-8:raise AssertionError(row)
                    cases.append(row)
    return dict(passed=True,cases=cases,executable_sha256=hashlib.sha256(Path(exe).read_bytes()).hexdigest(),
                construction='Deterministic prior draw seed187+T plus Gaussian perturbation seed71, canonical -> exact fixed geometry')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--exe',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise FileExistsError('Parity artifact immutable')
    result=check(a.exe);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2));print(json.dumps(result))
