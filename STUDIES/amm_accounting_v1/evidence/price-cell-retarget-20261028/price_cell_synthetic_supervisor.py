"""Source-bound, seed-inventory-audited, bounded synthetic launch."""
import hashlib,json,os,sys
from pathlib import Path
from resource_monitor import execute


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def integers(v):
    if type(v)is int:yield v
    elif isinstance(v,dict):
        for x in v.values():yield from integers(x)
    elif isinstance(v,list):
        for x in v:yield from integers(x)


def main():
    root=Path(__file__).resolve().parent;out=root/'run01';out.mkdir(exist_ok=False)
    proposed={398123781,398123782,398123783};inputs=[];collisions=[]
    # Explicit inventory values, not substring matches in floating-point draws.
    for folder,dirs,files in os.walk('/home/ubuntu/lanes'):
        dirs[:]=[d for d in dirs if d not in ('env','.git','runtime-cache','node_modules','__pycache__')]
        for name in files:
            if 'seed' not in name.lower() or not name.lower().endswith('.json'):continue
            p=Path(folder)/name
            if p.stat().st_size>64*1024**2:raise ValueError('Seed inventory too large: '+str(p))
            raw=p.read_bytes();v=json.loads(raw);shared=sorted(proposed.intersection(integers(v)))
            inputs.append(dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest()))
            if shared:collisions.append(dict(path=str(p),seeds=shared))
    audit=dict(proposed=sorted(proposed),inputs=inputs,collisions=collisions,
        scope='All seed-named JSON inventories reachable in existing AWS lane tree, excluding dependency/cache directories; public scalar seeds only, not opaque internal derivations or unrecorded historical seeds')
    (out/'SEED-AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
    if not inputs or collisions:raise ValueError('Seed audit not admitted')
    names=['price_cell_synthetic_worker.py','price_cell_rejection.py','price_cell_sv.stan','resource_monitor.py','price_cell_synthetic_supervisor.py']
    sources={n:sha(root/n) for n in names}
    import importlib.metadata as md
    versions={n:md.version(n) for n in ['numpy','scipy','arviz','nutpie','bridgestan','psutil']}
    plan=dict(sources=sources,versions=versions,python=sys.version,seed_audit_sha256=sha(out/'SEED-AUDIT.json'),limits=dict(seconds=600,rss=8*1024**3,output=256*1024**2))
    (out/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
    receipt=execute(['taskset','-c','0-3',sys.executable,str(root/'price_cell_synthetic_worker.py'),str(out/'fit')],str(root),600,out,8*1024**3,256*1024**2,out/'worker.log',output_scan_interval=2,utilization_path=out/'utilization.jsonl',phase_reserved_cores={'startup':4})
    receipt['sources_unchanged']=sources=={n:sha(root/n) for n in names}
    (out/'SUPERVISION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') and receipt['sources_unchanged'] else 1


if __name__=='__main__':raise SystemExit(main())
