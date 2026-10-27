"""Global fixed-plan orchestration; injected launcher permits outcome-free fixtures."""
import argparse,json,sys,time
from pathlib import Path
from evidence import atomic,digest
from ledger import build_ledger,sentinel_ledger
from sentinel_adapter import SENTINELS

PHASES=(('candidate',32),('sides',32),('reference',8),('report',1))

def campaign(spec,root,launch,clock=time.monotonic):
    if spec.get('status')!='frozen_authorized':raise ValueError('Draft cannot execute')
    root=Path(root)
    if root.exists():raise FileExistsError('Never resume/retry a campaign without separate recovery design')
    root.mkdir(parents=True);started=clock();state=dict(status='running',planned_streams=32,planned_origins=1024,planned_reference_fits=8,jobs=[dict(kind=k,id=i,status='not_started') for k,n in PHASES for i in range(n)],active_job=None)
    atomic(root/'campaign.json',state);unsafe=False
    try:
        for kind,count in PHASES:
            phase_started=clock();phase_cap=spec['bounds'][kind+'_phase_seconds']
            for index in range(count):
                job=next(j for j in state['jobs'] if j['kind']==kind and j['id']==index)
                whole_left=spec['bounds']['whole_seconds']-(clock()-started);phase_left=phase_cap-(clock()-phase_started)
                if unsafe or min(whole_left,phase_left)<=5:
                    job['reason']='prior_cleanup_or_global_resource_failure' if unsafe else 'phase_or_global_cap';continue
                if kind in ('sides','reference'):
                    stream=index if kind=='sides' else SENTINELS[index][0]
                    if not (root/f'stream-{stream:02d}'/'data.json').exists():job['reason']='data_unavailable';continue
                cap=min(spec['bounds'][kind+'_job_seconds'],whole_left-5,phase_left-5)
                state['active_job']=dict(kind=kind,id=index);job.update(status='running',cap_seconds=cap);atomic(root/'campaign.json',state)
                result=launch(kind,index,root,cap);job.update(result)
                state['active_job']=None
                if not result.get('group_drained',False) or result.get('reason') in ('rss_limit','output_limit'):unsafe=True
                atomic(root/'campaign.json',state)
            # Always emit full ledger even when no jobs can run.
            atomic(root/'ledger.json',build_ledger(root));atomic(root/'sentinel-ledger.json',sentinel_ledger(root))
        state['status']='finished_with_failures_or_missing' if unsafe else 'execution_finished'
    except Exception as exc:state.update(status='failed',error=repr(exc))
    finally:
        state['elapsed_seconds']=clock()-started
        try:
            ledger=build_ledger(root);atomic(root/'ledger.json',ledger);refs=sentinel_ledger(root);atomic(root/'sentinel-ledger.json',refs)
            state['candidate_valid_origins']=sum(r['arms']['candidate']['status']=='ok' for r in ledger)
            state['baseline_valid_origins']=sum(r['arms']['baseline']['status']=='ok' for r in ledger)
            state['oracle_valid_origins']=sum(r['arms']['oracle']['status']=='ok' for r in ledger)
            state['ledger_complete']=len(ledger)==1024 and len(refs)==8
            state['all_candidate_origins_valid']=state['candidate_valid_origins']==1024
        except Exception as exc:state.update(status='evidence_failed',ledger_error=repr(exc),ledger_complete=False)
        state['qualification']=None;atomic(root/'campaign.json',state)
    return state

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True);a=parser.parse_args();path=Path(a.manifest).resolve();spec=json.loads(path.read_text())
    if spec.get('status')!='frozen_authorized':raise ValueError('Draft cannot execute')
    for name,want in spec['sources'].items():
        if digest(name)!=want:raise ValueError('Frozen source mismatch')
    from resource_monitor import execute
    worker=Path(__file__).resolve().parent/'worker.py'
    def launch(kind,index,root,cap):
        command=['taskset','-c','0-3',spec['python_by_kind'][kind],str(worker),kind,'--id',str(index),'--manifest',str(path),'--root',str(root)]
        return execute(command,worker.parent,cap,root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/f'{kind}-{index:02d}.log')
    state=campaign(spec,a.out,launch)
    matched=all(digest(name)==want for name,want in spec['sources'].items());state['postrun_sources_match']=matched
    if not matched:state['status']='integrity_failed'
    atomic(Path(a.out)/'campaign.json',state)
    from validate_evidence import validate
    try:validation=validate(a.out,spec['sources'])
    except Exception as exc:validation=dict(evidence_complete=False,errors=[repr(exc)])
    atomic(Path(a.out)/'evidence-validation.json',validation)
if __name__=='__main__':main()
