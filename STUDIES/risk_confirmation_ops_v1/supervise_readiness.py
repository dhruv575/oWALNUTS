"""Fixed 600-second/12-GiB literal readiness envelope; no host shutdown."""
import argparse,hashlib,json
from pathlib import Path
from batch import load_worker,safe
from evidence_io import exclusive
from resource_monitor import execute

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args();manifest=Path(a.manifest).absolute();original=manifest.read_bytes();raw=json.loads(original);worker=load_worker(raw['worker_path'],raw['sources'][raw['worker_path']]);spec=worker.admit(manifest,expected_status='development_authorized');root=Path(a.out).absolute();root.mkdir(exist_ok=False);here=Path(__file__).resolve().parent
    exclusive(root/'LAUNCH.json',dict(manifest_sha256=hashlib.sha256(original).hexdigest(),literal_only=True,planned_reference_workers=4))
    result=execute([spec['python'],str(here/'readiness_batch.py'),'--manifest',str(manifest),'--out',str(root/'batch')],here,600,root,spec['bounds']['rss_bytes'],spec['bounds']['output_bytes'],root/'batch.log',ownership_env='OWALNUTS_RISK_READINESS_TOKEN',output_scan_interval=2,utilization_path=root/'utilization.jsonl',phase_reserved_cores={'native':4,'baselines':1,'reference':16,'tails':1,'report':1})
    result['complete']=False
    try:
        final=json.loads((root/'batch/READINESS-FINAL.json').read_bytes());worker.admit(manifest,expected_status='development_authorized')
        if manifest.read_bytes()!=original:raise ValueError('Manifest drift')
        result['complete']=result.get('status')=='exited' and result.get('exit_code')==0 and safe(result) and final.get('complete')is True and final.get('shared_sdk_products_unchanged')is True and len(final['jobs'])==8
        result['manifest_unchanged']=True
    except Exception as exc:result['readiness_error']=repr(exc)
    exclusive(root/'OUTER-FINAL.json',result);return 0 if result['complete'] else 1
if __name__=='__main__':raise SystemExit(main())
