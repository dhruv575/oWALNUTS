"""Frozen six-batch market schedule with disjoint process-group core ownership."""
import concurrent.futures,hashlib,importlib.metadata as md,importlib.util,json,os,queue,shutil,sys
from pathlib import Path
from resource_monitor import execute
from price_cell_synthetic_supervisor import integers,sha

ROOT=Path(__file__).resolve().parent;LANE=ROOT.parents[2]
def write(p,r):
    with p.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
def source_inventory():
    return {str(p):sha(p) for p in sorted(ROOT.parent.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.stan','.md','.json','.npz']}
def validate_inputs():
    prep=json.loads((LANE/'fixtures/PREPARATION.json').read_text())
    if prep['origins']!=24 or prep['baseline_slots']!=72:raise ValueError('Fixed fixtures')
    for n,r in prep['files'].items():
        p=LANE/'fixtures'/n
        if sha(p)!=r['sha256'] or p.stat().st_size!=r['bytes']:raise ValueError('Prepared fixture drift')
    parity=json.loads((ROOT/'NATIVE-PARITY.json').read_text())
    if len(parity['rows'])!=72 or not parity.get('capture_passed') or len(parity['tail_checks'])!=4:raise ValueError('Native admission')
    for n,h in parity['sources'].items():
        if sha(ROOT/n)!=h:raise ValueError('Native source drift')
    if sha(ROOT/'CAPTURE.npz')!=parity['capture_sha256']:raise ValueError('Captured regression fixture drift')

def freeze():
    validate_inputs();sources=source_inventory();p=LANE/'FREEZE.json';audit_path=LANE/'SEED-AUDIT.json'
    if p.exists():
        r=json.loads(p.read_text())
        if r['sources']!=sources or r['seed_audit_sha256']!=sha(audit_path):raise ValueError('Frozen campaign drift')
        return r
    if audit_path.exists():raise ValueError('Partial admission needs review')
    seeds=set(range(398141000,398142152));inputs=[];collisions=[]
    for folder,dirs,files in os.walk('/home/ubuntu/lanes'):
        dirs[:]=[d for d in dirs if d not in ('env','.git','runtime-cache','node_modules','__pycache__')]
        for name in files:
            if 'seed' not in name.lower() or not name.lower().endswith('.json'):continue
            file=Path(folder)/name
            if file.stat().st_size>64*1024**2:raise ValueError('Oversize seed inventory')
            raw=file.read_bytes();shared=sorted(seeds.intersection(integers(json.loads(raw))))
            inputs.append(dict(path=str(file),sha256=hashlib.sha256(raw).hexdigest()))
            if shared:collisions.append(dict(path=str(file),seeds=shared))
    audit=dict(proposed=sorted(seeds),inputs=inputs,collisions=collisions,scope='All external lane seed-named JSON; opaque engine-internal streams excluded')
    write(audit_path,audit)
    if not inputs or collisions:raise ValueError('Seed admission')
    binaries={}
    for package in ['owalnuts','nutpie']:
        origin=Path(importlib.util.find_spec(package).origin)
        for f in [origin,*origin.parent.glob('*.so')]:binaries[str(f)]=sha(f)
    r=dict(sources=sources,seed_audit_sha256=sha(audit_path),preparation_sha256=sha(LANE/'fixtures/PREPARATION.json'),python=sys.version,versions={n:md.version(n) for n in ['owalnuts','nutpie','bridgestan','arviz','numpy','scipy','numba','psutil']},binaries=binaries,batches=[list(range(12*i,12*i+12)) for i in range(6)],scope='72 paired-sampler development cells; no omitted failed slots')
    write(p,r);return r

def campaign(batch,out):
    groups=queue.Queue()
    for i in range(4):groups.put(i)
    def job(index):
        folder=out/f'job-{index}';folder.mkdir();group=groups.get()
        receipt=execute(['taskset','-c',f'{4*group}-{4*group+3}',sys.executable,str(ROOT/'bounded_market_worker.py'),str(index),str(LANE/'fixtures'),str(folder/'fit')],str(ROOT),900,folder,5*1024**3,192*1024**2,folder/'worker.log',output_scan_interval=2,utilization_path=folder/'utilization.jsonl',phase_reserved_cores={'startup':4})
        write(folder/'SUPERVISION.json',receipt)
        if not receipt.get('group_drained'):raise RuntimeError('Do not reuse undrained core group')
        groups.put(group);return dict(index=index,**receipt)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(job,range(12*batch,12*batch+12)))
    write(out/'FINAL.json',rows)
    return 0 if all(r.get('exit_code')==0 and r.get('group_drained') for r in rows) else 1

def launch(batch):
    if type(batch)is not int or not 0<=batch<6:raise ValueError('Fixed batch')
    if shutil.disk_usage(LANE).free<int(3.5*1024**3):raise ValueError('Disk admission')
    if set(os.sched_getaffinity(0))!=set(range(16)):raise ValueError('Sixteen CPU admission')
    frozen=freeze()
    for file,digest in frozen['binaries'].items():
        if sha(file)!=digest:raise ValueError('Runtime binary drift')
    for package,version in frozen['versions'].items():
        if md.version(package)!=version:raise ValueError('Runtime version drift')
    if batch:
        prev=LANE/f'batch-{batch-1:02d}'
        r=json.loads((prev/'SUPERVISION.json').read_text())
        if not r['group_drained'] or not r['sources_unchanged'] or len(json.loads((prev/'FINAL.json').read_text()))!=12:raise ValueError('Previous batch needs review')
    out=LANE/f'batch-{batch:02d}';out.mkdir(exist_ok=False)
    write(out/'PLAN.json',dict(batch=batch,indices=frozen['batches'][batch],freeze_sha256=sha(LANE/'FREEZE.json'),seed_audit_sha256=sha(LANE/'SEED-AUDIT.json')))
    r=execute([sys.executable,str(Path(__file__).resolve()),'--campaign',str(batch),str(out)],str(ROOT),2760,out,22*1024**3,int(2.5*1024**3),out/'campaign.log',ownership_env='OWALNUTS_BOUNDED_MARKET_BATCH',output_scan_interval=2,utilization_path=out/'outer-utilization.jsonl',phase_reserved_cores={'startup':16})
    r['sources_unchanged']=source_inventory()==frozen['sources'];write(out/'SUPERVISION.json',r);print(json.dumps(r),flush=True)
    return 0 if r.get('exit_code')==0 and r.get('group_drained') and r['sources_unchanged'] else 1

if __name__=='__main__':raise SystemExit(campaign(int(sys.argv[2]),Path(sys.argv[3])) if sys.argv[1]=='--campaign' else launch(int(sys.argv[1])))
