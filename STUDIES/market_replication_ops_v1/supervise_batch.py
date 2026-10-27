"""External fixed-resource envelope for the three mandatory market months."""
import argparse,hashlib,json,sys
from pathlib import Path
from batch import load_worker
from evidence_io import exclusive
from resource_monitor import execute

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args();manifest=Path(a.manifest).absolute();original=manifest.read_bytes();raw=json.loads(original);worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest);root=Path(a.out).absolute();root.mkdir(exist_ok=False);here=Path(__file__).resolve().parent
    exclusive(root/'LAUNCH.json',dict(manifest_sha256=hashlib.sha256(original).hexdigest(),planned_months=[m['month'] for m in spec['months']],planned_jobs=33))
    result=execute([spec['python'],str(here/'batch.py'),'--manifest',str(manifest),'--out',str(root/'batch')],here,spec['bounds']['external_seconds'],root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/'batch.log',ownership_env='OWALNUTS_MARKET_BATCH_TOKEN',output_scan_interval=2)
    result.update(evidence_complete=False,execution_complete=False,qualification=None)
    try:
        state=json.loads((root/'batch/BATCH-FINAL.json').read_bytes());worker.admit(manifest)
        if manifest.read_bytes()!=original:raise ValueError('Manifest bytes changed')
        for month in spec['months']:
            value=state['month_accounting'][month['month']]
            if value.get('planned_origins')!=month['origins'] or value.get('planned_references')!=8 or value.get('accounting_complete')is not True or value.get('artifact_integrity',{}).get('integrity_ok')is not True:raise ValueError('Incomplete month accounting '+month['month'])
        result['evidence_complete']=result.get('status')=='exited' and result.get('exit_code')==0 and result.get('group_drained')is True and not result.get('orphaned_children_after_leader_exit') and state.get('job_accounting_complete')is True and state.get('all_launched_groups_drained')is True
        result.update(execution_complete=state['execution_complete'] and state['aggregate_written'] and state['aggregate_error'] is None,month_accounting=state['month_accounting'],evidence_complete_meaning='All fixed denominators and artifact integrity accounted; does not imply all forecasts available or scientific success',manifest_unchanged=True)
    except Exception as exc:result['accounting_error']=repr(exc)
    exclusive(root/'BATCH-SUPERVISION.json',result);return 0 if result['evidence_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
