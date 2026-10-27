"""One fixed11-job campaign; no acquisition and no retry/selection logic."""
import argparse,json,time
from pathlib import Path
from worker import admit
from linear_runner_snapshot import exclusive
from resource_monitor_snapshot import execute
from ledger import build,references,validate_artifacts

PHASES=[('candidate',1),('baselines',1),('reference',8),('report',1)]

def campaign(spec,root,launch,clock=time.monotonic):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    state=dict(status='running',planned_origins=1488,planned_forecasts=4464,planned_references=8,jobs=[dict(phase=phase,index=i,status='not_started') for phase,count in PHASES for i in range(count)])
    exclusive(root/'CAMPAIGN-START.json',state);started=clock();unsafe=False
    try:
        for phase,count in PHASES:
            phase_start=clock();phase_cap=spec['bounds'][phase+'_seconds']
            for index in range(count):
                job=next(j for j in state['jobs'] if j['phase']==phase and j['index']==index)
                left=min(spec['bounds']['whole_seconds']-(clock()-started),phase_cap-(clock()-phase_start))
                if unsafe or left<=5:
                    job['reason']='prior_cleanup_or_resource_failure' if unsafe else 'phase_or_whole_budget';continue
                cap=min(left-5,spec['bounds']['reference_job_seconds'] if phase=='reference' else phase_cap)
                job.update(status='running',cap_seconds=cap)
                result=launch(phase,index,root,cap);job.update(result)
                exclusive(root/f'monitor-{phase}-{index:02d}.json',job)
                if result.get('group_drained')is not True or result.get('reason') in ['rss_limit','output_limit','output_limit_final_scan'] or result.get('final_output_scan_error'):unsafe=True
        state['status']='execution_finished'
    except Exception as error:state.update(status='failed',error=repr(error))
    finally:
        state['elapsed_seconds']=clock()-started
        try:
            ledger=build(root);ref=references(root);exclusive(root/'terminal-ledger.json',ledger);exclusive(root/'terminal-references.json',ref)
            integrity=validate_artifacts(root)
            state.update(valid_scores={a:sum(r['arms'][a]['status']=='ok' for r in ledger) for a in ['candidate','rolling_t5','ewma_t5']},artifact_integrity=integrity)
            complete=integrity['integrity_ok'] and len(ledger)==1488 and len(ref)==8 and not unsafe and all(j['status']!='running' for j in state['jobs'])
            execution=all(j['status']=='exited' and j.get('exit_code')==0 and j.get('group_drained')is True for j in state['jobs'])
            state.update(accounting_complete=complete,execution_complete=execution,
                all_planned_forecasts_available=all(v==1488 for v in state['valid_scores'].values()),
                references_complete=sum(r['status']=='complete' for r in ref),reference_diagnostics_pass=sum(r.get('reference_diagnostics_pass')is True for r in ref))
            exclusive(root/'evidence-validation.json',dict(evidence_complete=complete,evidence_complete_meaning='Accounting/integrity only, not full execution, forecast availability or scientific success',accounting_complete=complete,
                execution_complete=execution,valid_scores=state['valid_scores'],all_planned_forecasts_available=state['all_planned_forecasts_available'],references_complete=state['references_complete'],
                planned_origins=1488,planned_references=8,artifact_integrity=integrity,qualification=None))
        except Exception as error:state.update(status='evidence_failed',error=repr(error))
        exclusive(root/'CAMPAIGN-FINAL.json',state)
    return state

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    manifest=Path(args.manifest).resolve();spec=admit(manifest);worker=Path(__file__).with_name('worker.py')
    def launch(phase,index,root,cap):
        command=['taskset','-c','0-3',spec['python'],str(worker),phase,'--index',str(index),'--manifest',str(manifest),'--root',str(root)]
        return execute(command,worker.parent,cap,root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/f'{phase}-{index:02d}.log',output_scan_interval=2)
    result=campaign(spec,args.out,launch);admit(manifest)
    return 1 if result['status'] in ['failed','evidence_failed'] else 0

if __name__=='__main__':raise SystemExit(main())
