"""Bounded acquisition and fixture preparation with pre-outcome source binding."""
import hashlib,importlib.metadata as md,importlib.util,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;LANE=HERE.parents[2]
sys.path.insert(0,str(HERE.parent/'amm_accounting_v1'))
from resource_monitor import execute
from confirmation_calendar import schedule

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def sources():
    return {p.relative_to(LANE).as_posix():sha(p) for p in sorted((LANE/'source').rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.stan','.md','.json','.npz']}

def acquisition():
    if (LANE/'PRE-ACQUISITION.json').exists():raise FileExistsError('Inspect prior admission')
    with (LANE/'PREFLIGHT.log').open('x') as log:
        for cwd,args in [(HERE,['discover','-p','test_*.py','-v']),(HERE.parent/'amm_accounting_v1',['test_confirmation_bootstrap','test_confirmation_calendar','-v'])]:
            subprocess.run([sys.executable,'-m','unittest',*args],cwd=cwd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    for name in ['LOCAL-SEEDS.json','REMOTE-SEEDS.json']:
        audit=json.loads((HERE/'evidence/admission'/name).read_text())
        if not audit['inputs'] or audit['collisions']:raise ValueError('Seed audit gate')
    calendar=schedule();write(LANE/'CALENDAR.json',calendar)
    protocol=json.loads((HERE/'ACQUISITION-DRAFT.json').read_text())
    protocol.update(status='frozen_authorized',acquire_source_sha256=sha(HERE/'acquire.py'))
    write(LANE/'ACQUISITION.json',protocol)
    binaries={}
    for package in ['owalnuts','nutpie']:
        origin=Path(importlib.util.find_spec(package).origin)
        for p in [origin,*origin.parent.glob('*.so')]:binaries[str(p)]=sha(p)
    frozen=dict(sources=sources(),calendar_sha256=sha(LANE/'CALENDAR.json'),protocol_sha256=sha(LANE/'ACQUISITION.json'),tests_sha256=sha(LANE/'PREFLIGHT.log'),versions={n:md.version(n) for n in ['numpy','scipy','arviz','nutpie','owalnuts','numba','psutil']},binaries=binaries,cells=3050,batches=255,batch_cells=12,final_batch_cells=2,per_cell_seconds=900,per_batch_seconds=2760,concurrent_cells=4,cores_per_cell=4,scope='Historical project-access confirmation; bounded exposure audit, not prospective live evidence')
    write(LANE/'PRE-ACQUISITION.json',frozen)
    receipt=execute([sys.executable,str(HERE/'acquire.py'),'--protocol',str(LANE/'ACQUISITION.json'),'--out',str(LANE/'acquisition')],str(HERE),660,LANE/'acquisition',512*1024**2,100*1024**2,LANE/'acquisition.log',ownership_env='OWALNUTS_CONFIRMATION_ACQUISITION',output_scan_interval=2,utilization_path=LANE/'acquisition-utilization.jsonl',phase_reserved_cores={'startup':1})
    # The collector requires a new output directory. The monitor must not create it.
    terminal_path=LANE/'acquisition/terminal.json'
    terminal=json.loads(terminal_path.read_text()) if terminal_path.exists() else {}
    receipt['sealed_acquisition_admitted']=bool(receipt.get('exit_code')==0 and receipt.get('group_drained') and terminal.get('complete') and sources()==frozen['sources'])
    write(LANE/'acquisition-supervisor.json',receipt)
    if not receipt['sealed_acquisition_admitted']:raise RuntimeError('Acquisition did not admit')
    bindings=dict(directory=str(LANE/'acquisition'),supervisor_final_path=str(LANE/'acquisition-supervisor.json'),supervisor_final_sha256=sha(LANE/'acquisition-supervisor.json'),collector_sha256=sha(HERE/'acquire.py'))
    for name,key in [('terminal.json','terminal_sha256'),('protocol.json','protocol_sha256'),('bars.json','bars_sha256')]:bindings[key]=sha(LANE/'acquisition'/name)
    write(LANE/'ACQUISITION-BINDINGS.json',bindings);print(json.dumps(dict(acquisition_admitted=True,valid_bars=terminal['valid_bars'])))

if __name__=='__main__':acquisition()
