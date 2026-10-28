"""Fixed inference/reference/arithmetic queue with mandatory process drain barriers."""
import argparse,concurrent.futures,hashlib,importlib.util,json,sys,threading,time
from pathlib import Path
from evidence_io import exclusive
from resource_monitor import execute
PHASES=('native','baselines','reference','tail_candidate','tail_reference','report')

def drained(j):return j.get('group_drained')is True and not j.get('orphaned_children_after_leader_exit')
def safe(j):return drained(j) and j.get('reason')not in ('rss_limit','output_limit','output_limit_final_scan') and not j.get('final_output_scan_error')
def load_worker(path,want):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=want:raise ValueError('Worker identity changed')
    sys.path.insert(0,str(path.parent));s=importlib.util.spec_from_file_location('bound_risk_confirmation_worker',path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def planned_jobs(months):
    jobs=[]
    for phase in PHASES:
        if phase.startswith('tail_'):jobs.extend(dict(phase=phase,shard=i,status='not_started') for i in range(12))
        else:jobs.extend(dict(phase=phase,month=m['month'],index=i,status='not_started') for m in months for i in range(8 if phase=='reference' else 1))
    return jobs

def run(spec,root,launch,clock=time.monotonic,finalize=None,aggregate=None,seal_inference=None):
    fixed=json.loads(Path(__file__).with_name('OPS-DRAFT.json').read_bytes())
    if [{k:m[k] for k in ('month','origins')} for m in spec['months']]!=fixed['months'] or any(spec['bounds'].get(k)!=v for k,v in fixed['bounds'].items()):raise ValueError('Fixed scope/bounds changed')
    root=Path(root);root.mkdir(parents=True,exist_ok=False);jobs=planned_jobs(spec['months']);start=clock();deadline=start+spec['bounds']['whole_seconds'];unsafe=threading.Event();seal_result=None;seal_error=None
    exclusive(root/'BATCH-START.json',dict(planned_jobs=57,planned_origins=4320,planned_references=24,jobs=jobs))
    def one(job,end,affinity):
        if unsafe.is_set():job['reason']='prior_cleanup_or_resource_failure';return
        remaining=min(end,deadline)-clock()
        if remaining<=5:job['reason']='fixed_phase_or_whole_budget';return
        cap=min(remaining-5,spec['bounds']['reference_job_seconds']) if job['phase']=='reference' else remaining-5
        job.update(status='running',cap_seconds=cap,affinity=affinity)
        try:job.update(launch(job,root,cap,affinity))
        except Exception as exc:job.update(status='launch_failed',error=repr(exc),group_drained=False)
        if not safe(job):unsafe.set()
        key=str(job['shard']) if 'shard'in job else job['month']+'-'+str(job['index'])
        exclusive(root/f"monitor-{job['phase']}-{key}.json",job)
    try:
        for phase in PHASES:
            if phase=='tail_candidate' and not unsafe.is_set() and seal_inference is not None:
                try:
                    if clock()>=deadline:raise TimeoutError('Whole budget before input seal')
                    seal_result=seal_inference(spec,root)
                    if seal_result is None:raise ValueError('Missing inference seal result')
                except Exception as exc:seal_error=repr(exc);unsafe.set()
            exclusive(root/f'PHASE-{phase}.json',dict(phase=phase,elapsed_seconds=clock()-start,reserved_cores=fixed['phase_reserved_cores'][phase]))
            selected=[j for j in jobs if j['phase']==phase];end=min(deadline,clock()+spec['bounds'][phase+'_seconds'])
            if unsafe.is_set():
                for job in selected:job['reason']='prior_cleanup_or_resource_failure'
                continue
            if phase=='reference':
                def queue(q):
                    for job in selected[q::4]:one(job,end,f'{4*q}-{4*q+3}')
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    for f in [pool.submit(queue,q) for q in range(4)]:f.result()
            elif phase=='native' or phase.startswith('tail_'):
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected)) as pool:
                    futures=[pool.submit(one,job,end,f'{4*i}-{4*i+3}' if phase=='native' else str(i)) for i,job in enumerate(selected)]
                    for f in futures:f.result()
            else:
                for job in selected:one(job,end,'0')
    finally:
        all_drained=all(j['status']=='not_started' or drained(j) for j in jobs);accounting=None;error=None;summary=None;summary_error=None
        exclusive(root/'OPERATIONAL-JOBS.json',jobs)
        if all_drained and clock()<deadline:
            try:
                if finalize is not None:accounting=finalize(spec,root,jobs)
            except Exception as exc:error=repr(exc)
            try:
                if aggregate is not None:summary=aggregate(spec,root)
            except Exception as exc:summary_error=repr(exc)
        success=all(j.get('status')=='exited' and j.get('exit_code')==0 and safe(j) for j in jobs)
        state=dict(jobs=jobs,planned_jobs=57,planned_origins=4320,planned_references=24,job_accounting_complete=len(jobs)==57 and all(j['status']!='running' for j in jobs),all_jobs_successful=success,all_launched_groups_drained=all_drained,accounting=accounting,accounting_error=error,aggregate_written=summary is not None,aggregate_error=summary_error,execution_complete=success and accounting is not None and accounting.get('accounting_complete')is True and accounting.get('artifact_integrity',{}).get('integrity_ok')is True and summary is not None and error is None and summary_error is None,elapsed_seconds=clock()-start,qualification=None)
        state.update(inference_seal=seal_result,inference_seal_error=seal_error)
        exclusive(root/'BATCH-FINAL.json',state)
    return state

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args();manifest=Path(a.manifest).absolute();raw=json.loads(manifest.read_bytes());worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest)
    def launch(job,root,cap,affinity):
        cmd=['taskset','-c',affinity,spec['python'],spec['worker_path'],job['phase'],'--manifest',str(manifest),'--root',str(root)]
        cmd+=['--shard',str(job['shard'])] if 'shard'in job else ['--month',job['month'],'--index',str(job['index'])]
        key=str(job['shard']) if 'shard'in job else job['month']+'-'+str(job['index']);owned=root/'worker-monitor'/f"{job['phase']}-{key}";owned.mkdir(parents=True)
        rss=spec['bounds']['reference_worker_rss_bytes' if job['phase']=='reference' else 'tail_worker_rss_bytes' if job['phase'].startswith('tail_') else 'native_worker_rss_bytes']
        return execute(cmd,Path(spec['worker_path']).parent,cap,owned,rss,spec['bounds']['output_bytes'],owned/'worker.log',output_scan_interval=2)
    state=run(spec,a.out,launch,finalize=worker.terminal_accounting,aggregate=worker.batch_summary,seal_inference=worker.seal_inference);worker.admit(manifest)
    return 0 if state['job_accounting_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
