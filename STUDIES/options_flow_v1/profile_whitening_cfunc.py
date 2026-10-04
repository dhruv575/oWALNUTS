"""Target-only profile: launch a fresh affinity-controlled process for each T.
No MCMC or JAX parity in measured process. Never run alongside sampling timings.
Example: python hardware_control.py --cpus 0 --record affinity.json -- python
profile_whitening_cfunc.py --periods 128 --out profile.json
"""
import time
PROCESS_START=time.perf_counter()
import argparse,ctypes,hashlib,json,os,platform,sys
from pathlib import Path


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def snapshot(extension,adapter):
    root=Path(__file__).resolve().parent
    return dict(source_sha256={p.name:digest(p) for p in root.glob('*.py')},
        extension_path=str(extension),extension_sha256=digest(extension),
        adapter_path=str(adapter),adapter_sha256=digest(adapter),
        python_path=sys.executable,python_executable_sha256=digest(sys.executable))

def peak_memory():
    if os.name!='nt':return None
    from ctypes import wintypes as w
    class Counters(ctypes.Structure):
        _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(n,ctypes.c_size_t) for n in ['peak_working_set','working_set','peak_paged_pool','paged_pool','peak_nonpaged_pool','nonpaged_pool','pagefile','peak_pagefile']]
    k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=w.HANDLE
    api=ctypes.WinDLL('psapi');api.GetProcessMemoryInfo.argtypes=[w.HANDLE,ctypes.POINTER(Counters),w.DWORD]
    c=Counters();c.cb=ctypes.sizeof(c)
    if not api.GetProcessMemoryInfo(k.GetCurrentProcess(),ctypes.byref(c),c.cb):return None
    return dict(peak_working_set_bytes=c.peak_working_set,working_set_bytes=c.working_set,peak_pagefile_bytes=c.peak_pagefile)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--periods',type=int,choices=[32,128,512,1000],required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--calls-per-block',type=int,default=300)
    p.add_argument('--blocks',type=int,default=5);p.add_argument('--expected-cpus',default='0');a=p.parse_args()
    if a.calls_per_block<3 or a.blocks<1:p.error('Require >=3 calls and >=1 blocks')
    if a.out.exists():raise FileExistsError(a.out)
    import numpy as np
    import owalnuts
    import owalnuts._owalnuts as extension
    import pymc,pytensor,numba
    from hardware_control import get_affinity,parse_cpus
    from pymc_workflow import compile_target
    expected=parse_cpus(a.expected_cpus)
    if get_affinity()!=expected:raise RuntimeError('Run under affinity wrapper with expected CPUs')
    before=snapshot(extension.__file__,owalnuts.__file__)
    t=a.periods;index=np.arange(t,dtype=float)
    # Deterministic declared data/positions, no generating truth or fitted values.
    data=dict(y=(.2*np.sin(index*.17)+.001*index).tolist(),dt=(.7+.6*(np.arange(t-1)%7)/6).tolist(),anchor=.1,anchor_mode='exogenous',nu=5.)
    points=[np.ascontiguousarray(np.r_[.25*np.cos(index*.11+shift),lo,lr],dtype=np.float64) for shift,lo,lr in [(0.,-2.5,-2.),(.7,-4.,-1.),(1.4,-1.,-4.)]]
    start=time.perf_counter();target,metadata=compile_target(data,'conditional_whitening');compile_seconds=time.perf_counter()-start
    # Construct ABI wrapper and buffer pointers exactly once, outside timed loops.
    pointer=ctypes.POINTER(ctypes.c_double)
    prototype=ctypes.CFUNCTYPE(ctypes.c_double,ctypes.c_ssize_t,pointer,pointer,ctypes.c_void_p)
    caller=prototype(target.address);grads=[np.empty_like(q) for q in points]
    inputs=[q.ctypes.data_as(pointer) for q in points];outputs=[g.ctypes.data_as(pointer) for g in grads]
    first=[];values=[]
    for i in range(3):
        start=time.perf_counter();value=caller(t+2,inputs[i],outputs[i],None);elapsed=time.perf_counter()-start
        if not np.isfinite(value) or not np.isfinite(grads[i]).all():raise ValueError('Nonfinite target output')
        first.append(elapsed);values.append(dict(position=points[i].tolist(),value=float(value),gradient=grads[i].tolist()))
    blocks=[];checksum=0.
    for block in range(a.blocks):
        cpu=time.process_time();start=time.perf_counter()
        for j in range(a.calls_per_block):
            i=j%3;checksum+=caller(t+2,inputs[i],outputs[i],None)
        elapsed=time.perf_counter()-start;cpu_elapsed=time.process_time()-cpu
        if any(not np.isfinite(g).all() for g in grads):raise ValueError('Nonfinite repeated gradient')
        blocks.append(dict(calls=a.calls_per_block,seconds=elapsed,cpu_seconds=cpu_elapsed,seconds_per_call=elapsed/a.calls_per_block))
    after=snapshot(extension.__file__,owalnuts.__file__)
    if before!=after or get_affinity()!=expected:raise RuntimeError('Source/binary/affinity changed during profile')
    result=dict(phase='target-only-exploratory',qualified=False,periods=t,data=data,
        data_sha256=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        coordinates='conditional_whitening',process_pid=os.getpid(),source_before=before,source_after=after,
        environment=dict(python=sys.version,platform=platform.platform(),numpy=np.__version__,pymc=pymc.__version__,pytensor=pytensor.__version__,numba=numba.__version__,algorithm_revision=owalnuts.ALGORITHM_REVISION),
        cpus_before=expected,cpus_after=get_affinity(),compile_seconds=compile_seconds,compilation=metadata,
        first_call_seconds=first,blocks=blocks,validation_points=values,checksum=checksum,
        process_elapsed_seconds=time.perf_counter()-PROCESS_START,memory=peak_memory(),
        scope='Fresh process required per T; existing disk compiler caches retained. Compile clock includes model construction/compiler adapter, imports only in process total. Repeated loop includes ctypes crossing and tiny Python dispatch; no prototype or pointer construction inside loop. No MCMC or JAX parity. Compare stored values/gradients against independent JAX scan in a separate validation process.')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)

if __name__=='__main__':main()
