"""Fixed three-month batch: parallel candidates, then fully drained serial phases."""
import argparse,concurrent.futures,hashlib,importlib.util,json,sys,time
from pathlib import Path
from evidence_io import exclusive
from resource_monitor import execute

def drained(result):return result.get('group_drained')is True and not result.get('orphaned_children_after_leader_exit')

def safe(result):
    return drained(result) and result.get('reason') not in ('rss_limit','output_limit','output_limit_final_scan') and not result.get('final_output_scan_error')

def run(spec,root,launch,clock=time.monotonic,finalize=None,aggregate=None):
    draft=json.loads(Path(__file__).with_name('OPS-DRAFT.json').read_bytes())
    if [{k:m[k] for k in ('month','origins')} for m in spec['months']]!=draft['months']:raise ValueError('Fixed month/count mismatch')
    if any(spec['bounds'].get(k)!=v for k,v in draft['bounds'].items()):raise ValueError('Fixed operational bounds mismatch')
    root=Path(root);root.mkdir(parents=True,exist_ok=False);months=spec['months'];bounds=spec['bounds'];start=clock();deadline=start+bounds['whole_seconds'];jobs=[dict(month=m['month'],phase=p,index=i,status='not_started') for p,n in [('candidate',1),('baselines',1),('reference',8),('report',1)] for m in months for i in range(n)]
    for m in months:(root/m['month']).mkdir()
    exclusive(root/'BATCH-START.json',dict(planned_jobs=33,planned_origins=sum(m['origins'] for m in months),planned_forecasts=3*sum(m['origins'] for m in months),planned_references=24,jobs=jobs));unsafe=False
    def one(job,phase_end,affinity):
        remaining=min(deadline-clock(),phase_end-clock())
        if remaining<=5:job['reason']='fixed_phase_or_whole_budget';return job
        cap=min(remaining-5,bounds['reference_job_seconds'] if job['phase']=='reference' else remaining-5);job.update(status='running',cap_seconds=cap,affinity=affinity)
        try:job.update(launch(job['month'],job['phase'],job['index'],root/job['month'],cap,affinity))
        except Exception as exc:job.update(status='launch_failed',error=repr(exc),group_drained=False)
        exclusive(root/f"monitor-{job['month']}-{job['phase']}-{job['index']:02d}.json",job);return job
    try:
        end=min(deadline,clock()+bounds['candidate_seconds']);candidates=[j for j in jobs if j['phase']=='candidate']
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(one,j,end,a) for j,a in zip(candidates,('0-3','4-7','8-11'))]
            for f in futures:
                result=f.result()
                if result['status']!='not_started' and not safe(result):unsafe=True
        for phase in ('baselines','reference','report'):
            end=min(deadline,clock()+bounds[phase+'_seconds'])
            for job in [j for j in jobs if j['phase']==phase]:
                if unsafe:job['reason']='prior_cleanup_or_resource_failure';continue
                result=one(job,end,'0-3')
                if result['status']!='not_started' and not safe(result):unsafe=True
    finally:
        month_accounting={}
        for month in months:
            owned=[j for j in jobs if j['month']==month['month']];exclusive(root/month['month']/'OPERATIONAL-JOBS.json',owned)
            if finalize is not None and all(j['status']=='not_started' or drained(j) for j in jobs) and clock()<deadline:
                try:month_accounting[month['month']]=finalize(spec,month['month'],root/month['month'],owned)
                except Exception as exc:month_accounting[month['month']]=dict(accounting_complete=False,error=repr(exc))
            else:month_accounting[month['month']]=dict(accounting_complete=False,reason='unavailable_finalizer_or_deadline_or_undrained_group')
        aggregate_result=None;aggregate_error=None
        if aggregate is not None and all(j['status']=='not_started' or drained(j) for j in jobs) and clock()<deadline:
            try:aggregate_result=aggregate(spec,root)
            except Exception as exc:aggregate_error=repr(exc)
        execution=all(j.get('status')=='exited' and j.get('exit_code')==0 and safe(j) for j in jobs)
        state=dict(status='batch_finished',jobs=jobs,planned_jobs=33,planned_origins=sum(m['origins'] for m in months),planned_forecasts=3*sum(m['origins'] for m in months),planned_references=24,job_accounting_complete=len(jobs)==33 and all(j['status']!='running' for j in jobs),execution_complete=execution,month_accounting=month_accounting,aggregate_written=aggregate_result is not None,aggregate_error=aggregate_error,all_launched_groups_drained=all(j['status']=='not_started' or drained(j) for j in jobs),elapsed_seconds=clock()-start,qualification=None)
        exclusive(root/'BATCH-FINAL.json',state)
    return state

def load_worker(path,expected_sha256):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('Worker source mismatch before import')
    sys.path.insert(0,str(path.parent));s=importlib.util.spec_from_file_location('bound_replication_worker',path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args();manifest=Path(a.manifest).absolute();raw=json.loads(manifest.read_bytes());worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest)
    def launch(month,phase,index,root,cap,affinity):
        return execute(['taskset','-c',affinity,spec['python'],spec['worker_path'],phase,'--month',month,'--index',str(index),'--manifest',str(manifest),'--root',str(root)],Path(spec['worker_path']).parent,cap,root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/f'{phase}-{index:02d}.log',output_scan_interval=2)
    result=run(spec,a.out,launch,finalize=worker.terminal_accounting,aggregate=worker.batch_summary);worker.admit(manifest);return 0 if result['job_accounting_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
