"""Fixed campaign scheduling; no result-dependent retries or allocation."""
import argparse,concurrent.futures,os,sys,time
from pathlib import Path
from runtime import admit
from linear_runner import exclusive
from resource_monitor import execute

def campaign(manifest,root):
    spec=admit(manifest);root=Path(root);root.mkdir(exist_ok=False);(root/'logs').mkdir();b=spec['protocol']['bounds'];deadline=time.monotonic()+b['inner_seconds'];jobs=[];here=Path(__file__).resolve().parent
    def job(kind,index,cap,affinity,phase_end):
        remaining=min(cap,phase_end-time.monotonic(),deadline-time.monotonic())
        if remaining<=0:return dict(kind=kind,index=index,status='not_started',reason='fixed_budget_exhausted')
        scope=root/'lanes'/f"{('control','shift')[index//2]}-r{index%2}" if kind=='lane' else root/'references'/f'{index:02d}' if kind=='reference' else root
        command=['taskset','-c',affinity,sys.executable,str(here/'worker.py'),kind,'--index',str(index),'--manifest',str(manifest),'--root',str(root)]
        value=execute(command,here,remaining,scope,b['rss_bytes'],b['output_bytes'],root/'logs'/f'{kind}-{index:02d}.log',output_scan_interval=2)
        value.update(kind=kind,index=index);exclusive(root/f'monitor-{kind}-{index:02d}.json',value);return value
    jobs.append(job('data',0,30,'0-3',deadline))
    if (root/'data'/'DATA.json').exists() and jobs[0].get('exit_code')==0 and jobs[0].get('group_drained') and jobs[0].get('status')=='exited' and not jobs[0].get('orphaned_children_after_leader_exit'):
        end=min(deadline,time.monotonic()+b['lane_phase_seconds'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(job,'lane',i,b['lane_job_seconds'],spec['protocol']['affinities'][i],end) for i in range(4)]
            for f in futures:jobs.append(f.result())
        drained=all(x.get('group_drained',True) for x in jobs)
        end=min(deadline,time.monotonic()+b['reference_phase_seconds'])
        for i in range(18):
            value=job('reference',i,b['reference_job_seconds'],'0-3',end) if drained else dict(kind='reference',index=i,status='not_started',reason='prior_cleanup_failed')
            jobs.append(value);drained=drained and value.get('group_drained',True) and not value.get('orphaned_children_after_leader_exit')
    else:
        jobs.extend(dict(kind=k,index=i,status='not_started',reason='data_unavailable') for k,n in [('lane',4),('reference',18)] for i in range(n))
    exclusive(root/'JOBS.json',jobs)
    report=job('analysis',0,b['analysis_seconds'],'0-3',deadline);exclusive(root/'ANALYSIS-JOB.json',report)
    admit(manifest)
    exclusive(root/'CAMPAIGN.json',dict(status='finished',planned_jobs=24,jobs=len(jobs)+1,postrun_bindings_match=True,analysis_successful=report.get('exit_code')==0 and report.get('status')=='exited' and report.get('group_drained') and not report.get('orphaned_children_after_leader_exit'),all_owned_groups_drained=all(x.get('group_drained',True) and not x.get('orphaned_children_after_leader_exit') for x in jobs+[report])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('root');a=p.parse_args();campaign(a.manifest,a.root)
