"""External aggregate budget covers all nested worker sessions via inherited token."""
import argparse,os,sys,json
from pathlib import Path
from runtime import admit,sha
from linear_runner import exclusive
from resource_monitor import execute

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('output');a=p.parse_args();manifest=Path(a.manifest).absolute();identity=sha(manifest);spec=admit(manifest);out=Path(a.output).absolute();out.mkdir(exist_ok=False);b=spec['protocol']['bounds'];here=Path(__file__).resolve().parent
    exclusive(out/'LAUNCH.json',dict(manifest=str(manifest),sha256=identity))
    result=execute([sys.executable,str(here/'campaign.py'),str(manifest),str(out/'work')],here,b['outer_seconds'],out,b['rss_bytes'],b['output_bytes'],out/'campaign.log',ownership_env='OWALNUTS_CAMPAIGN_TOKEN',output_scan_interval=2)
    result['manifest_unchanged']=sha(manifest)==identity
    campaign=json.loads((out/'work'/'CAMPAIGN.json').read_text()) if (out/'work'/'CAMPAIGN.json').exists() else {}
    summary=json.loads((out/'work'/'SUMMARY.json').read_text()) if (out/'work'/'SUMMARY.json').exists() else {}
    result['evidence_complete']=campaign.get('analysis_successful') is True and campaign.get('all_owned_groups_drained') is True and summary.get('planned_updates')==8000 and summary.get('planned_checkpoints')==44 and summary.get('planned_query_comparisons')==264 and summary.get('planned_scale_comparisons')==88 and (out/'work'/'SUMMARY.json').exists() and (out/'work'/'CAMPAIGN.json').exists() and result.get('group_drained') and result.get('exit_code')==0 and result.get('status')=='exited' and not result.get('orphaned_children_after_leader_exit') and result['manifest_unchanged']
    exclusive(out/'SUPERVISION.json',result)
    return 0 if result['evidence_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
