"""Fixed confirmation batches; resource failures stay in the denominator."""
import concurrent.futures,hashlib,importlib.metadata as md,json,os,queue,shutil,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'amm_accounting_v1'))

def indices(batch):
    if type(batch)is not int or not 0<=batch<255:raise ValueError('Fixed batch index')
    return list(range(batch*12,min((batch+1)*12,3050)))

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def check_previous(lane,batch):
    if not batch:return
    prior=Path(lane)/f'batch-{batch-1:03d}'
    supervision=json.loads((prior/'SUPERVISION.json').read_text())
    final=json.loads((prior/'FINAL.json').read_text())
    if not supervision.get('group_drained') or not supervision.get('sources_unchanged'):raise ValueError('Previous batch not drained or source drift')
    if [r['index'] for r in final]!=indices(batch-1) or not all(r.get('group_drained') for r in final):raise ValueError('Previous denominator/process ownership')
    archive=json.loads((prior/'ARCHIVE-VERIFIED.json').read_text())
    if not archive.get('exact_version_restore_verified') or not archive.get('version_id'):raise ValueError('Previous archive unverified')
    if archive.get('plan_sha256')!=sha(prior/'PLAN.json'):raise ValueError('Archive not bound to previous batch plan')

def check_sources(lane,frozen):
    for relative,digest in frozen['sources'].items():
        path=(Path(lane)/relative).resolve()
        if not path.is_relative_to(Path(lane).resolve()) or sha(path)!=digest:raise ValueError('Frozen source drift')

def campaign(lane,batch,executor=None):
    if executor is None:
        from resource_monitor import execute
        executor=execute
    lane=Path(lane);out=lane/f'batch-{batch:03d}';groups=queue.Queue()
    for i in range(4):groups.put(i)
    def job(index):
        folder=out/f'job-{index}';folder.mkdir();group=groups.get()
        receipt=executor(['taskset','-c',f'{group*4}-{group*4+3}',sys.executable,str(HERE/'worker.py'),str(index),str(lane/'fixtures'),str(folder/'fit')],str(HERE),900,folder,5*1024**3,192*1024**2,folder/'worker.log',output_scan_interval=2,utilization_path=folder/'utilization.jsonl',phase_reserved_cores={'startup':4})
        write(folder/'SUPERVISION.json',receipt)
        if not receipt.get('group_drained'):raise RuntimeError('Undrained group cannot be reused')
        groups.put(group);return dict(index=index,**receipt)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(job,indices(batch)))
    write(out/'FINAL.json',rows)
    # Individual failed slots remain recorded. Campaign completeness is distinct.
    return 0

def launch(lane,batch):
    from resource_monitor import execute
    lane=Path(lane).resolve();planned=indices(batch)
    frozen=json.loads((lane/'FREEZE.json').read_text())
    if frozen.get('status')!='admitted' or frozen.get('cells')!=3050:raise ValueError('Admission required')
    if not frozen.get('versions') or not frozen.get('binaries'):raise ValueError('Runtime freeze required')
    for package,version in frozen['versions'].items():
        if md.version(package)!=version:raise ValueError('Runtime version drift')
    for path,digest in frozen['binaries'].items():
        if sha(path)!=digest:raise ValueError('Runtime binary drift')
    check_sources(lane,frozen);check_previous(lane,batch)
    if shutil.disk_usage(lane).free<int(3.5*1024**3):raise ValueError('Disk admission')
    if set(os.sched_getaffinity(0))!=set(range(16)):raise ValueError('CPU admission')
    out=lane/f'batch-{batch:03d}';out.mkdir(exist_ok=False)
    write(out/'PLAN.json',dict(batch=batch,indices=planned,freeze_sha256=sha(lane/'FREEZE.json')))
    receipt=execute([sys.executable,str(Path(__file__).resolve()),'--campaign',str(lane),str(batch)],str(HERE),2760,out,22*1024**3,int(2.5*1024**3),out/'campaign.log',ownership_env='OWALNUTS_CONFIRMATION_BATCH',output_scan_interval=2,utilization_path=out/'utilization.jsonl',phase_reserved_cores={'startup':16})
    try:check_sources(lane,frozen);receipt['sources_unchanged']=True
    except Exception:receipt['sources_unchanged']=False
    write(out/'SUPERVISION.json',receipt);print(json.dumps(receipt),flush=True)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') and receipt['sources_unchanged'] else 1

if __name__=='__main__':
    if sys.argv[1]=='--campaign':raise SystemExit(campaign(sys.argv[2],int(sys.argv[3])))
    raise SystemExit(launch(sys.argv[1],int(sys.argv[2])))
