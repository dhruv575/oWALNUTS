"""External Linux whole-campaign envelope. Draft manifests are never launched."""
import argparse,json,os,sys
from pathlib import Path
from resource_monitor import execute
from evidence import atomic,digest

def supervise(manifest,root,python):
    manifest=Path(manifest).absolute();spec=json.loads(manifest.read_text());root=Path(root).absolute()
    if spec.get('status')!='frozen_authorized':raise ValueError('Draft cannot execute')
    if root.exists():raise FileExistsError('Fresh campaign envelope required')
    for path,want in spec['sources'].items():
        if digest(path)!=want:raise ValueError('Frozen source mismatch')
    root.mkdir(parents=True)
    result=execute([os.path.abspath(python),str(Path(__file__).with_name('orchestrate.py')),'--manifest',str(manifest),'--out',str(root/'campaign')],Path(__file__).parent,spec['bounds']['external_seconds'],root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/'campaign.log',ownership_env='OWALNUTS_CAMPAIGN_TOKEN')
    result['evidence_complete']=False
    try:
        record=json.loads((root/'campaign/evidence-validation.json').read_text())
        result['evidence_complete']=result['status']=='exited' and result['exit_code']==0 and result['group_drained'] and not result.get('orphaned_children_after_leader_exit',False) and record['evidence_complete'] is True
    except (OSError,ValueError,KeyError) as exc:result['evidence_error']=repr(exc)
    result['qualification']=None;atomic(root/'external-supervisor.json',result)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);p.add_argument('--python',required=True);a=p.parse_args();r=supervise(a.manifest,a.out,a.python);sys.exit(0 if r['evidence_complete'] else 1)
