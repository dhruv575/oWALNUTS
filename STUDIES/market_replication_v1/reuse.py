"""Hash-checked E62 imports with only fixed calendar globals configured."""
import hashlib,importlib.util,json,sys
from pathlib import Path
import data_contract

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def calendar(month,e62_root):
    row=data_contract.configure(month);root=Path(e62_root).resolve()
    identities=json.loads(Path(__file__).with_name('REUSE-IDENTITIES.json').read_bytes())['sources']
    for name,want in identities.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=want:raise ValueError('E62 source drift: '+name)
    # Every production process handles one month; fixtures may configure another.
    if str(root)not in sys.path:sys.path.append(str(root))
    for name in ['baselines_snapshot','linear_runner_snapshot']:
        load(root/(name+'.py'),name)
    baseline=load(root/'run_baselines.py','replication_e62_baselines')
    reference=load(root/'run_reference.py','run_reference');reference.TICKS=row['reference_ticks']
    ledger=load(root/'ledger.py','replication_e62_ledger')
    worker=load(root/'worker.py','replication_e62_worker')
    report=load(Path(__file__).with_name('report.py'),'replication_month_report');report.N=row['origins']
    return dict(contract=row,baseline=baseline,reference=reference,ledger=ledger,worker=worker,report=report)
