"""Fixed independent arithmetic shards; no sampling or host lifecycle calls."""
import argparse, concurrent.futures, hashlib, importlib.util, json, sys, time
from pathlib import Path
from evidence_io import exclusive
from resource_monitor import execute

def drained(job):
    return job.get('group_drained') is True and not job.get('orphaned_children_after_leader_exit')

def safe(job):
    return drained(job) and job.get('reason') not in ('rss_limit','output_limit','output_limit_final_scan') and not job.get('final_output_scan_error')

def load_worker(path, sha):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha: raise ValueError('Worker hash mismatch')
    sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('bound_tail_worker',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

def run(spec,root,launch,clock=time.monotonic,finalize=None,aggregate=None):
    draft=json.loads(Path(__file__).with_name('OPS-DRAFT.json').read_bytes())
    if [{k:m[k] for k in ('month','origins')} for m in spec['months']]!=draft['months']:raise ValueError('Fixed month/count mismatch')
    if any(spec['bounds'].get(k)!=v for k,v in draft['bounds'].items()): raise ValueError('Operational bounds mismatch')
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    jobs=[dict(phase=p,shard=i,status='not_started') for p in ('candidate','reference') for i in range(12)]
    jobs += [dict(phase='report',month=m['month'],status='not_started') for m in draft['months']]
    start=clock();deadline=start+spec['bounds']['whole_seconds'];unsafe=False
    exclusive(root/'BATCH-START.json',dict(planned_jobs=27,planned_candidate_origins=4368,planned_reference_origins=24,jobs=jobs))
    def one(job,end):
        remaining=min(end,deadline)-clock()
        if remaining<=5:job['reason']='fixed_phase_or_whole_budget';return job
        job.update(status='running',cap_seconds=remaining-5,affinity=str(job.get('shard',0)))
        try:job.update(launch(job,root,remaining-5,job['affinity']))
        except Exception as exc:job.update(status='launch_failed',error=repr(exc),group_drained=False)
        key=str(job.get('shard',job.get('month')))
        exclusive(root/f"monitor-{job['phase']}-{key}.json",job)
        return job
    try:
        for phase in ('candidate','reference','report'):
            exclusive(root/f'PHASE-{phase}.json',dict(phase=phase,elapsed_seconds=clock()-start))
            selected=[j for j in jobs if j['phase']==phase]
            if unsafe:
                for j in selected:j['reason']='prior_cleanup_or_resource_failure'
                continue
            end=min(deadline,clock()+spec['bounds'][phase+'_seconds'])
            if phase!='report':
                with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                    results=[pool.submit(one,j,end) for j in selected]
                    for future in results:
                        result=future.result()
                        if result['status']!='not_started' and not safe(result):unsafe=True
            else:
                for j in selected:
                    if unsafe:j['reason']='prior_cleanup_or_resource_failure';continue
                    result=one(j,end)
                    if result['status']!='not_started' and not safe(result):unsafe=True
    finally:
        all_drained=all(j['status']=='not_started' or drained(j) for j in jobs)
        accounting=None;accounting_error=None;summary=None;summary_error=None
        exclusive(root/'OPERATIONAL-JOBS.json',jobs)
        if all_drained and clock()<deadline:
            try:
                if finalize is not None:accounting=finalize(spec,root,jobs)
            except Exception as exc:accounting_error=repr(exc)
            try:
                if aggregate is not None:summary=aggregate(spec,root)
            except Exception as exc:summary_error=repr(exc)
        state=dict(jobs=jobs,planned_jobs=27,planned_candidate_origins=4368,planned_reference_origins=24,
            job_accounting_complete=len(jobs)==27 and all(j['status']!='running' for j in jobs),
            execution_complete=all(j.get('status')=='exited' and j.get('exit_code')==0 and safe(j) for j in jobs) and accounting is not None and accounting.get('accounting_complete') is True and accounting.get('artifact_integrity',{}).get('integrity_ok') is True and accounting_error is None and summary is not None and summary_error is None,
            all_jobs_successful=all(j.get('status')=='exited' and j.get('exit_code')==0 and safe(j) for j in jobs),
            all_launched_groups_drained=all_drained,accounting=accounting,accounting_error=accounting_error,
            aggregate_written=summary is not None,aggregate_error=summary_error,elapsed_seconds=clock()-start,qualification=None)
        exclusive(root/'BATCH-FINAL.json',state)
    return state

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    manifest=Path(a.manifest).absolute();raw=json.loads(manifest.read_bytes());worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest)
    def launch(job,root,cap,affinity):
        command=['taskset','-c',affinity,spec['python'],spec['worker_path'],job['phase'],'--manifest',str(manifest),'--root',str(root)]
        command += ['--month',job['month']] if job['phase']=='report' else ['--shard',str(job['shard'])]
        key=str(job.get('shard',job.get('month')))
        owned=root/'worker-monitor'/f"{job['phase']}-{key}";owned.mkdir(parents=True)
        return execute(command,Path(spec['worker_path']).parent,cap,owned,spec['bounds']['worker_rss_bytes'],spec['bounds']['output_bytes'],owned/'worker.log',output_scan_interval=2)
    result=run(spec,a.out,launch,finalize=worker.terminal_accounting,aggregate=worker.batch_summary)
    worker.admit(manifest)
    return 0 if result['job_accounting_complete'] else 1

if __name__=='__main__':raise SystemExit(main())
