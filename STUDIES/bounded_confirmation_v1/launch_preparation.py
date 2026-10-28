"""External operations runner; does not modify the pre-acquisition source snapshot."""
import hashlib,json,sys
from pathlib import Path

def run(lane):
    lane=Path(lane).resolve();root=lane/'source/STUDIES/bounded_confirmation_v1'
    sys.path.insert(0,str(root));sys.path.insert(0,str(root.parent/'amm_accounting_v1'))
    from resource_monitor import execute
    def sha(p):
        with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    frozen=json.loads((lane/'PRE-ACQUISITION.json').read_text())
    def intact():return all(sha(lane/name)==h for name,h in frozen['sources'].items())
    if not intact():raise ValueError('Pre-acquisition source drift')
    monitor=lane/'preparation-monitor';monitor.mkdir(exist_ok=False)
    receipt=execute([sys.executable,str(root/'prepare.py'),str(lane/'ACQUISITION-BINDINGS.json'),str(lane/'fixtures')],str(root),10800,lane/'fixtures',8*1024**3,512*1024**2,monitor/'worker.log',ownership_env='OWALNUTS_CONFIRMATION_PREPARATION',output_scan_interval=2,utilization_path=monitor/'utilization.jsonl',phase_reserved_cores={'startup':4})
    receipt['sources_unchanged']=intact();receipt['runner_sha256']=sha(__file__)
    (monitor/'SUPERVISION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if receipt.get('exit_code')!=0 or not receipt.get('group_drained') or not receipt['sources_unchanged']:raise RuntimeError('Preparation failed admission')
    prep=json.loads((lane/'fixtures/PREPARATION.json').read_text())
    if prep['origins']!=2928 or prep['baseline_slots']!=8784:raise ValueError('Preparation denominator')
    for name,meta in prep['files'].items():
        p=lane/'fixtures'/name
        if not p.resolve().is_relative_to(lane/'fixtures') or p.stat().st_size!=meta['bytes'] or sha(p)!=meta['sha256']:raise ValueError('Prepared file integrity')
    print(json.dumps(dict(preparation_admitted=True,origins=prep['origins'],baseline_slots=prep['baseline_slots'],unavailable_baselines=prep['unavailable_baselines'])),flush=True)

if __name__=='__main__':run(sys.argv[1])
