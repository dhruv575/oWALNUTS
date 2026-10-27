"""Bound only the owned arithmetic workload; never change host lifecycle."""
import argparse,hashlib,json
from pathlib import Path
from batch import load_worker,safe
from evidence_io import exclusive
from resource_monitor import execute

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    manifest=Path(a.manifest).absolute();original=manifest.read_bytes();raw=json.loads(original)
    worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest)
    root=Path(a.out).absolute();root.mkdir(exist_ok=False);here=Path(__file__).resolve().parent
    exclusive(root/'LAUNCH.json',dict(manifest_sha256=hashlib.sha256(original).hexdigest(),planned_jobs=27,host_shutdown=False))
    result=execute([spec['python'],str(here/'batch.py'),'--manifest',str(manifest),'--out',str(root/'batch')],here,
        spec['bounds']['external_seconds'],root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/'batch.log',
        ownership_env='OWALNUTS_TAIL_BATCH_TOKEN',output_scan_interval=2,utilization_path=root/'utilization.jsonl')
    result.update(evidence_complete=False,execution_complete=False,qualification=None)
    try:
        state=json.loads((root/'batch/BATCH-FINAL.json').read_bytes());worker.admit(manifest)
        if manifest.read_bytes()!=original:raise ValueError('Manifest bytes changed')
        accounting=state['accounting']
        if not isinstance(accounting,dict) or accounting.get('accounting_complete') is not True or accounting.get('planned_candidate_origins')!=4368 or accounting.get('planned_reference_origins')!=24 or accounting.get('artifact_integrity',{}).get('integrity_ok') is not True:raise ValueError('Incomplete fixed accounting or artifact integrity')
        result['evidence_complete']=result.get('status')=='exited' and result.get('exit_code')==0 and safe(result) and state.get('job_accounting_complete') is True and state.get('all_launched_groups_drained') is True and state.get('aggregate_written') is True and state.get('aggregate_error') is None
        result.update(execution_complete=result['evidence_complete'] and state['execution_complete'] and state['aggregate_written'] and state['aggregate_error'] is None,accounting=accounting,manifest_unchanged=True,evidence_complete_meaning='Fixed denominators and artifact integrity accounted; not a numerical or scientific pass')
    except Exception as exc:result['accounting_error']=repr(exc)
    exclusive(root/'BATCH-SUPERVISION.json',result)
    return 0 if result['evidence_complete'] else 1

if __name__=='__main__':raise SystemExit(main())
