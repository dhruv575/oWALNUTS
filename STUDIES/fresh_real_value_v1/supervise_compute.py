"""External3720-second compute envelope using the E61 process monitor snapshot."""
import argparse,json,sys
from pathlib import Path
from resource_monitor_snapshot import execute
from linear_runner_snapshot import exclusive
from worker import admit

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    manifest=Path(args.manifest).resolve();spec=admit(manifest);root=Path(args.out).resolve();root.mkdir(parents=True,exist_ok=False)
    entry=Path(__file__).with_name('orchestrate.py')
    result=execute([spec['python'],str(entry),'--manifest',str(manifest),'--out',str(root/'campaign')],entry.parent,
        spec['bounds']['external_seconds'],root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/'campaign.log',ownership_env='OWALNUTS_CAMPAIGN_TOKEN',output_scan_interval=2)
    result['evidence_complete']=False
    try:
        validation=json.loads((root/'campaign/evidence-validation.json').read_bytes());admit(manifest)
        result['evidence_complete']=result['status']=='exited' and result['exit_code']==0 and result['group_drained'] and not result.get('orphaned_children_after_leader_exit',False) and validation['evidence_complete']is True
        result.update(evidence_complete_meaning='Accounting and integrity only; exit0 preserves complete failure packets too',execution_complete=validation['execution_complete'],
            all_planned_forecasts_available=validation['all_planned_forecasts_available'],valid_scores=validation['valid_scores'],references_complete=validation['references_complete'])
    except Exception as error:result['evidence_error']=repr(error)
    result['qualification']=None;exclusive(root/'external-supervisor.json',result)
    return 0 if result['evidence_complete'] else 1

if __name__=='__main__':raise SystemExit(main())
