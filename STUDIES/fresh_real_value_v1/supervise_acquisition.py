"""Acquisition-only Windows watchdog; PID+creation-time ownership from E60."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import psutil

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def exclusive(path,value):
    with Path(path).open('x',encoding='utf8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n')

def supervise(command,cwd,out,*,seconds=300,rss_limit=512*1024**2,output_limit=64*1024**2,metadata=None,finish_check=None):
    """Injectable command/caps for deterministic process fixtures; CLI fixes limits."""
    out=Path(out).resolve();cwd=Path(cwd).resolve()
    prefix=out.parent/(out.name+'.supervisor');start_path=Path(str(prefix)+'.start.json');final_path=Path(str(prefix)+'.final.json');log=Path(str(prefix)+'.log')
    if out.exists() or any(p.exists() for p in [start_path,final_path,log]):raise FileExistsError('No attempt overwrite/retry')
    out.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();state=dict(status='starting',supervisor_pid=os.getpid(),command=list(command),started_unix=time.time(),
        whole_process_seconds=seconds,startup_allowance_seconds=0,rss_limit_bytes=rss_limit,output_limit_bytes=output_limit,
        sample_seconds=.1,cleanup_seconds=5,supervisor_sha256=sha(__file__),psutil_version=psutil.__version__,
        observed_peak_owned_rss=0,observed_output_bytes=0,limitation='Sampled resources; bounded cleanup follows deadline')
    state.update(metadata or {})
    exclusive(start_path,state);tracked={};process=None
    def discover():
        for key,parent in list(tracked.items()):
            try:
                if not parent.is_running() or parent.create_time()!=key[1]:continue
                for item in parent.children(recursive=True):tracked.setdefault((item.pid,item.create_time()),item)
            except psutil.NoSuchProcess:pass
        alive=[]
        for key,item in tracked.items():
            try:
                if item.is_running() and item.create_time()==key[1] and item.status()!=psutil.STATUS_ZOMBIE:alive.append(item)
            except psutil.NoSuchProcess:pass
        return alive
    try:
        with log.open('xb') as stream:
            env=os.environ.copy();env.update({k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']})
            process=subprocess.Popen(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
            launcher=psutil.Process(process.pid);tracked[(launcher.pid,launcher.create_time())]=launcher
            state.update(status='running',launcher_pid=process.pid)
            while True:
                alive=discover();rss=0
                for item in alive:
                    try:rss+=item.memory_info().rss
                    except psutil.NoSuchProcess:pass
                size=sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) if out.exists() else 0
                size+=log.stat().st_size
                state['observed_peak_owned_rss']=max(state['observed_peak_owned_rss'],rss);state['observed_output_bytes']=max(state['observed_output_bytes'],size)
                reason=('whole_process_deadline' if time.monotonic()-started>=seconds else 'rss_limit' if rss>rss_limit else 'output_limit' if size>output_limit else None)
                if reason:state.update(status='terminated',reason=reason);break
                code=process.poll()
                if code is not None and not alive:state.update(status='exited',exit_code=code);break
                time.sleep(.1)
    except BaseException as error:state.update(status='supervisor_failed',error=repr(error))
    finally:
        for item in reversed(discover()):
            try:item.terminate()
            except psutil.NoSuchProcess:pass
        _,remaining=psutil.wait_procs(discover(),timeout=3)
        for item in remaining:
            try:item.kill()
            except psutil.NoSuchProcess:pass
        psutil.wait_procs(remaining,timeout=2)
        if process is not None:state['exit_code']=process.poll()
        state['remaining_owned_pids']=[p.pid for p in discover()]
        state['processes']=[dict(pid=k[0],create_time=k[1]) for k in tracked]
        if state['remaining_owned_pids']:state['status']='cleanup_failed'
        terminal=None
        try:
            if (out/'terminal.json').exists():terminal=json.loads((out/'terminal.json').read_bytes())
        except Exception as error:state['terminal_error']=repr(error)
        state['collector_complete']=bool(terminal and terminal.get('complete')is True)
        completed=set((terminal or {}).get('completed_requests',[]))
        state['request_statuses']=[dict(index=i,status='complete' if i in completed else
            ('failed' if terminal else 'interrupted') if (out/f'request-{i:03d}.json').exists() else 'not_started') for i in range(37)]
        state.update(ended_unix=time.time(),elapsed_seconds=time.monotonic()-started)
        if finish_check is not None:
            try:state.update(finish_check())
            except Exception as error:state.update(bindings_held=False,admission_error=repr(error))
        if 'sealed_acquisition_admitted' in state:
            state['sealed_acquisition_admitted']=bool(state['sealed_acquisition_admitted'] and
                state['status']=='exited' and state.get('exit_code')==0 and not state['remaining_owned_pids'])
        exclusive(final_path,state)
    return state

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True);parser.add_argument('--python',required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    study=Path(__file__).resolve().parent;protocol=args.protocol.resolve();value=json.loads(protocol.read_bytes())
    if value.get('status')!='frozen_authorized':raise ValueError('Parent-authorized frozen protocol required')
    if sha(study/'acquire.py')!=value['acquire_source_sha256']:raise ValueError('Collector binding mismatch')
    if sha(__file__)!=value['supervisor_source_sha256']:raise ValueError('Supervisor binding mismatch')
    if sha(study/'PLAN-DRAFT.md')!=value['method_plan_sha256']:raise ValueError('Method plan binding mismatch')
    runtime=value['runtime']
    if sys.version!=runtime['python'] or sha(args.python)!=runtime['executable_sha256'] or sha(sys._base_executable)!=runtime['base_executable_sha256'] or psutil.__version__!=runtime['psutil']:
        raise ValueError('Frozen acquisition runtime mismatch')
    expected=sha(protocol)
    command=[os.path.abspath(args.python),str(study/'acquire.py'),'--protocol',str(protocol),'--out',str(args.out.resolve())]
    def finish_check():
        held=sha(protocol)==expected and sha(study/'acquire.py')==value['acquire_source_sha256'] and sha(__file__)==value['supervisor_source_sha256'] and sha(study/'PLAN-DRAFT.md')==value['method_plan_sha256']
        terminal_path=args.out.resolve()/'terminal.json';admitted=False
        if terminal_path.exists():
            terminal=json.loads(terminal_path.read_bytes())
            if terminal.get('complete')is True:
                admitted=held and terminal['protocol_sha256']==expected and terminal['source_sha256']==value['acquire_source_sha256'] and terminal['valid_bars']==1776 and terminal['completed_requests']==list(range(37)) and sha(args.out.resolve()/'bars.json')==terminal['bars_sha256']
        return dict(bindings_held=held,sealed_acquisition_admitted=bool(admitted))
    state=supervise(command,study,args.out,metadata=dict(protocol_sha256=expected,collector_sha256=value['acquire_source_sha256'],method_plan_sha256=value['method_plan_sha256'],runtime=runtime),finish_check=finish_check)
    held=state.get('bindings_held',False)
    print(json.dumps(dict(status=state['status'],collector_complete=state['collector_complete'],bindings_held=held,remaining_owned_pids=state['remaining_owned_pids']),indent=2))
    return 0 if state['status']=='exited' and state['exit_code']==0 and state.get('sealed_acquisition_admitted') and held else 1

if __name__=='__main__':raise SystemExit(main())
