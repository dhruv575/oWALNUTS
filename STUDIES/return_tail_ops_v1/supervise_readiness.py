"""600-second aggregate envelope for twelve full-size literal checks."""
import argparse,hashlib,json
from pathlib import Path
from batch import load_worker,safe
from evidence_io import exclusive
from resource_monitor import execute

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    manifest=Path(a.manifest).absolute();original=manifest.read_bytes();raw=json.loads(original);worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest,expected_status='development_authorized')
    root=Path(a.out).absolute();root.mkdir(exist_ok=False);here=Path(__file__).resolve().parent
    exclusive(root/'LAUNCH.json',dict(manifest_sha256=hashlib.sha256(original).hexdigest(),planned_shards=12,literal_only=True))
    result=execute([spec['python'],str(here/'readiness_batch.py'),'--manifest',str(manifest),'--out',str(root/'batch')],here,600,root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/'batch.log',ownership_env='OWALNUTS_TAIL_READINESS_TOKEN',output_scan_interval=2,utilization_path=root/'utilization.jsonl')
    result['complete']=False
    try:
        final=json.loads((root/'batch/READINESS-FINAL.json').read_bytes())
        if manifest.read_bytes()!=original:raise ValueError('Manifest changed')
        worker.admit(manifest,expected_status='development_authorized')
        result['complete']=result.get('status')=='exited' and result.get('exit_code')==0 and safe(result) and final['complete'] is True and len(final['jobs'])==12
        result['manifest_unchanged']=True
    except Exception as exc:result['readiness_error']=repr(exc)
    exclusive(root/'OUTER-FINAL.json',result)
    return 0 if result['complete'] else 1
if __name__=='__main__':raise SystemExit(main())
