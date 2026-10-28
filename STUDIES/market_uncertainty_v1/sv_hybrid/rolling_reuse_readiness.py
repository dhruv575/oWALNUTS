"""Three literal fits, one compiled library; no market or convergence claim."""
import argparse,importlib.metadata,json,os,sys,tempfile,time
from pathlib import Path
import numpy as np
from literal_reference import sha,write,load,extract_full,extract_compact
from rolling_initialization import initialization_center
from resource_monitor import execute

def validate(path):
    spec=json.loads(Path(path).read_bytes())
    if spec['status']!='frozen_authorized' or len(spec['seeds'])!=6 or len(set(spec['seeds']))!=6:raise ValueError('Fixed six-seed plan')
    for name,digest in spec['sources'].items():
        if sha(name)!=digest:raise ValueError('Source drift')
    runtime=spec['runtime']
    if sys.prefix!=runtime['prefix']:raise ValueError('Runtime prefix drift')
    for name,version in runtime['packages'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('Runtime package drift')
    for name,digest in runtime['binaries'].items():
        if sha(name)!=digest:raise ValueError('Runtime binary drift')
    return spec

def worker(manifest,out):
    spec=validate(manifest);out=Path(out);out.mkdir(exist_ok=False);result=dict(status='incomplete',fits=[],manifest_sha256=sha(manifest))
    try:
        os.environ['BRIDGESTAN']=str(Path(spec['sdk_makefile']).parent)
        workspace=out/'compile';workspace.mkdir();os.environ['TMPDIR']=str(workspace);tempfile.tempdir=str(workspace)
        import nutpie,bridgestan
        adapter=load(spec['adapter'],'reuse_adapter');capture=load(spec['capture'],'reuse_capture')
        captures=[];start=time.monotonic()
        with capture.capture_compiler(bridgestan,out/'captured-libraries',captures):
            compiled=nutpie.compile_stan_model(code=Path(spec['stan']).read_text(),cleanup=False)
        if not captures:raise ValueError('Missing compilation provenance')
        write(out/'COMPILER.json',captures);result['compile_seconds']=time.monotonic()-start
        y=np.resize(np.array([.001,-.002,.0005,0.,.003]),253);previous=[];last=None
        for tick in range(3):
            directory=out/f'fit-{tick:02d}';directory.mkdir()
            window=y[tick:tick+250].copy();model=compiled.with_data(seed=spec['seeds'][2*tick],**adapter.stan_data(window))
            if model.library is not compiled.library:raise ValueError('Compiled library was not reused')
            for old,data in previous:
                if not np.array_equal(old.data['y'],data):raise ValueError('Prior data mapping mutated')
            center=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(250)] if last is None else initialization_center(last)[0]
            draws=200 if tick==0 else 400
            np.savez_compressed(directory/'INPUT.npz',window=window,initialization_center=center)
            start=time.monotonic()
            trace=nutpie.sample(model,chains=4,cores=4,tune=1000,draws=draws,seed=spec['seeds'][2*tick+1],init_mean=center,
                save_warmup=True,progress_bar=False,**spec['engine_options'])
            seconds=time.monotonic()-start;trace.to_netcdf(directory/'trace.nc')
            full=extract_full(trace,draws);compact,metadata=extract_compact(trace,draws)
            np.savez_compressed(directory/'draws.npz',full=full,compact=compact)
            previous.append((model,window));last=full[:,-1,:].copy()
            for group in trace.groups():getattr(trace,group).close()
            trace.close()
            row=dict(tick=tick,draws=draws,tune=1000,sampling_seconds=seconds,metadata=metadata,library_reused=True,
                input_sha256=sha(directory/'INPUT.npz'),draws_sha256=sha(directory/'draws.npz'),trace_sha256=sha(directory/'trace.nc'))
            write(directory/'FINAL.json',row);result['fits'].append(row)
        validate(manifest);result['status']='complete'
    except Exception as exc:result['error']=repr(exc)
    write(out/'FINAL.json',result)
    return 0 if result['status']=='complete' else 1

def supervise(manifest,out):
    validate(manifest);out=Path(out);out.mkdir(exist_ok=False)
    if len(os.sched_getaffinity(0))!=4:raise ValueError('Four allocated cores required')
    receipt=execute([sys.executable,str(Path(__file__).resolve()),str(manifest),str(out/'fit'),'--worker'],str(out),900,out,
        4*1024**3,512*1024**2,out/'worker.log',output_scan_interval=5,utilization_path=out/'utilization.jsonl',phase_reserved_cores={'startup':4})
    write(out/'SUPERVISION.json',receipt)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('out');p.add_argument('--worker',action='store_true');a=p.parse_args()
    raise SystemExit((worker if a.worker else supervise)(a.manifest,a.out))
