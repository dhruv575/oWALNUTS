"""Fixed-position target-only profile, one variant per fresh process, no sampling."""
import argparse
import hashlib
import json
from pathlib import Path
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=['loop','scan'],required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--iterations',type=int,default=300)
    args=parser.parse_args()
    if args.out.exists():raise FileExistsError(args.out)
    if args.iterations<1:raise ValueError('Positive iterations required')
    source_paths=[Path(__file__),Path(__file__).with_name('local_conditional_whitening.py')]
    source_before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    from hardware_control import set_affinity,hardware_metadata
    set_affinity([0])
    begin=time.perf_counter()
    import numpy as np
    import jax
    jax.config.update('jax_enable_x64',True)
    jax.config.update('jax_enable_compilation_cache',False)
    import jax.numpy as jnp
    import local_conditional_whitening as model
    imports=time.perf_counter()-begin
    t=128
    data=dict(y=np.linspace(-.2,.4,t).tolist(),dt=np.linspace(.4,1.6,t-1).tolist(),anchor=.13,anchor_mode='exogenous',nu=5.)
    points=np.array([np.r_[np.linspace(-.5,.7,t),lo,lr] for lo,lr in [(-2.5,-2.),(-4.,-1.),(-1.,-4.)]])
    device_points=[jnp.asarray(q) for q in points]
    density=(lambda q:model.jax_log_density(q,data)) if args.variant=='scan' else (lambda q:model.log_density(q,data,jnp))
    vg=jax.jit(jax.value_and_grad(density))
    print(json.dumps(dict(event='compile_begin',variant=args.variant)),flush=True)
    start=time.perf_counter();compiled=vg.lower(device_points[0]).compile();compile_seconds=time.perf_counter()-start
    print(json.dumps(dict(event='compile_end',seconds=compile_seconds)),flush=True)
    for q in device_points:
        value,gradient=compiled(q);value.block_until_ready();gradient.block_until_ready()
    blocks=[]
    for block in range(5):
        start=time.perf_counter()
        for i in range(args.iterations):
            value,gradient=compiled(device_points[i%len(points)])
            gradient.block_until_ready()
        blocks.append((time.perf_counter()-start)/args.iterations)
    parity=[]
    for q,dq in zip(points,device_points):
        value,gradient=compiled(dq)
        parity.append(dict(value=float(value),numpy_value=float(model.log_density(q,data)),gradient=np.asarray(gradient).tolist()))
    source_after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    if source_before!=source_after:raise ValueError('Profile sources changed during evaluation')
    report=dict(variant=args.variant,model='local_conditional_whitening',periods=t,imports_seconds=imports,
        trace_and_compile_seconds=compile_seconds,seconds_per_call_blocks=blocks,iterations_per_block=args.iterations,
        timing_scope='Target value+gradient only, including synchronized host dispatch; no sampling claim',
        cache_policy='Fresh process, JAX persistent compilation cache disabled',hardware=hardware_metadata(),
        data=data,positions=points.tolist(),parity=parity,jax_version=jax.__version__,
        source_sha256=source_before,source_unchanged_through_profile=True)
    with args.out.open('x',encoding='utf-8') as handle:json.dump(report,handle,indent=2,allow_nan=False)
    print(json.dumps(dict(variant=args.variant,compile_seconds=compile_seconds,seconds_per_call_blocks=blocks)),flush=True)


if __name__=='__main__':main()
