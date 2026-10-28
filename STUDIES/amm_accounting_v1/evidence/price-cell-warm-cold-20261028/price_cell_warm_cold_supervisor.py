"""Four disjoint monitored fits under an outer process-tree monitor."""
import concurrent.futures,hashlib,json,os,shutil,sys
from pathlib import Path
from resource_monitor import execute
from price_cell_synthetic_supervisor import integers,sha

root=Path(__file__).resolve().parent


def campaign(out):
    def job(i):
        folder=out/f'job-{i}';folder.mkdir()
        receipt=execute(['taskset','-c',f'{4*i}-{4*i+3}',sys.executable,str(root/'price_cell_warm_cold_worker.py'),str(i),str(folder/'fit')],str(root),600,folder,4*1024**3,256*1024**2,folder/'worker.log',output_scan_interval=2,utilization_path=folder/'utilization.jsonl',phase_reserved_cores={'startup':4})
        (folder/'SUPERVISION.json').write_text(json.dumps(receipt,indent=2)+'\n')
        return dict(index=i,**receipt)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(job,range(4)))
    (out/'FINAL.json').write_text(json.dumps(rows,indent=2)+'\n')
    return 0 if all(r.get('exit_code')==0 and r.get('group_drained') for r in rows) else 1


def launch():
    if shutil.disk_usage(root).free<3*1024**3:raise ValueError('Disk admission')
    if set(os.sched_getaffinity(0))!=set(range(16)):raise ValueError('Sixteen CPU admission')
    out=root/'run01';out.mkdir(exist_ok=False)
    seeds=set(range(398131000,398131064));inputs=[];collisions=[]
    for folder,dirs,files in os.walk('/home/ubuntu/lanes'):
        dirs[:]=[d for d in dirs if d not in ('env','.git','runtime-cache','node_modules','__pycache__')]
        for name in files:
            if 'seed' not in name.lower() or not name.lower().endswith('.json'):continue
            p=Path(folder)/name
            if p.stat().st_size>64*1024**2:raise ValueError('Oversize inventory')
            raw=p.read_bytes();shared=sorted(seeds.intersection(integers(json.loads(raw))))
            inputs.append(dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest()))
            if shared:collisions.append(dict(path=str(p),seeds=shared))
    audit=dict(proposed=sorted(seeds),inputs=inputs,collisions=collisions,scope='Seed-named JSON inventories in AWS lane tree; excludes dependency caches and opaque engine-internal derivations')
    (out/'SEED-AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
    if not inputs or collisions:raise ValueError('Seed admission')
    names=['price_cell_warm_cold_worker.py','price_cell_fixtures.py','price_cell_native.py','PRICE-CELL-WARM-COLD-PLAN.md','price_cell_remap.py','price_cell_sv.stan','STATIC-MANIFEST.json','resource_monitor.py','price_cell_warm_cold_supervisor.py','price_cell_synthetic_supervisor.py']
    sources={n:sha(root/n) for n in names}
    import importlib.metadata as md
    plan=dict(sources=sources,versions={n:md.version(n) for n in ['owalnuts','numba','nutpie','bridgestan','arviz','numpy','scipy','psutil']},python=sys.version,seed_audit_sha256=sha(out/'SEED-AUDIT.json'),scope='Fixed four-pair shifted-window synthetic panel')
    (out/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
    receipt=execute([sys.executable,str(Path(__file__).resolve()),'--campaign',str(out)],str(root),660,out,18*1024**3,1342177280,out/'campaign.log',ownership_env='OWALNUTS_CELL_WARM_COLD_OUTER',output_scan_interval=2,utilization_path=out/'outer-utilization.jsonl',phase_reserved_cores={'startup':16})
    receipt['sources_unchanged']=sources=={n:sha(root/n) for n in names}
    (out/'SUPERVISION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') and receipt['sources_unchanged'] else 1


if __name__=='__main__':raise SystemExit(campaign(Path(sys.argv[2])) if len(sys.argv)>1 else launch())
