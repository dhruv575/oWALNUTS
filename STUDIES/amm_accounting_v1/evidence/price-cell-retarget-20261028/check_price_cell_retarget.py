"""Seed-matched live retarget regression, not a posterior experiment."""
import hashlib,json,os,sys,time
from pathlib import Path
import numpy as np
import owalnuts
from price_cell_native import compile_target
from price_cell_remap import shift
from price_cell_synthetic_supervisor import integers


def serial(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    raise TypeError(type(v).__name__)


def run(out):
    out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic()
    proposed=set(range(398130000,398130024));inputs=[];collisions=[]
    for folder,dirs,files in os.walk('/home/ubuntu/lanes'):
        dirs[:]=[d for d in dirs if d not in ('env','.git','runtime-cache','node_modules','__pycache__')]
        for name in files:
            if 'seed' not in name.lower() or not name.endswith('.json'):continue
            p=Path(folder)/name
            if p.stat().st_size>64*1024**2:raise ValueError('Inventory too large')
            raw=p.read_bytes();shared=sorted(proposed.intersection(integers(json.loads(raw))))
            inputs.append(dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest()))
            if shared:collisions.append(dict(path=str(p),seeds=shared))
    (out/'SEED-AUDIT.json').write_text(json.dumps(dict(proposed=sorted(proposed),inputs=inputs,collisions=collisions,scope='Explicit resident call chain seeds; intentional paired reuse in fresh sessions. No claim about opaque internal streams.'),indent=2)+'\n')
    if not inputs or collisions:raise ValueError('Seed admission')
    rows=[]
    for j,n in enumerate((2,12,250)):
        lo=.002*np.sin(np.arange(n+1)*.17)-.0005;hi=lo+.001
        old=compile_target(lo[:-1],hi[:-1],0.)
        lower=lo[1:].copy();upper=hi[1:].copy();new=compile_target(lower,upper,0.)
        q=np.tile(np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(2*n)],(4,1))
        mass=np.ones_like(q);mass[:,2]=250000.
        initial=owalnuts.WarmState(q,np.full(4,.02),mass)
        tuning=owalnuts.Tuning(max_depth=5,max_refinement_levels=4)
        seed=398130000+8*j
        with owalnuts.WarmSession(old.target,initial,seed=seed,threads=4,tuning=tuning) as live:
            first=live.refresh(8);current=live.state()
            pos,metric,steps=shift(current.positions,current.mass_diagonal,current.step_sizes,lo[:-1],hi[:-1],lo[1:],hi[1:])
            shifted=owalnuts.WarmState(pos,steps,metric)
            live.retarget(new.target,shifted)
            # Mutating original caller data cannot change the new target.
            lower[:]+=100;upper[:]+=100
            actual=live.refresh(16)
        fresh=compile_target(lo[1:],hi[1:],0.)
        with owalnuts.WarmSession(fresh.target,shifted,seed=seed+4,threads=4,tuning=tuning) as control:
            expected=control.refresh(16)
        np.testing.assert_array_equal(actual.samples,expected.samples)
        assert actual.target_calls==expected.target_calls
        assert json.dumps(actual.diagnostics,default=serial,sort_keys=True)==json.dumps(expected.diagnostics,default=serial,sort_keys=True)
        assert actual.seed==expected.seed==seed+4 and actual.call_index==1 and expected.call_index==0
        np.savez_compressed(out/f'fixture-{j}.npz',before=first.samples,remapped=pos,actual=actual.samples,expected=expected.samples)
        details=dict(actual=actual.diagnostics,expected=expected.diagnostics,actual_metadata=actual.metadata,expected_metadata=expected.metadata)
        (out/f'fixture-{j}-diagnostics.json').write_text(json.dumps(details,default=serial)+'\n')
        rows.append(dict(n=n,exact_draw_match=True,exact_diagnostics_match=True,target_calls=actual.target_calls,seed=actual.seed))
    root=Path(__file__).resolve().parent
    result=dict(rows=rows,elapsed_seconds=time.monotonic()-start,sources={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['check_price_cell_retarget.py','price_cell_native.py','price_cell_remap.py','price_cell_synthetic_supervisor.py']},scope='API transition equivalence only; tiny unadapted chains do not test posterior fidelity')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run(sys.argv[1])
