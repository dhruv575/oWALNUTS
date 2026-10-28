"""Fixed local engineering fixture; not a scientific performance campaign."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'sv_prototype'))
from target import Target, Priors
from hybrid import EvaluationBudget, sweep
from interwoven import sweep_interwoven


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    base = Path(__file__).resolve().parent
    return [base/n for n in ('development.py','hybrid.py','interwoven.py')]+[base.parent/'sv_prototype'/'target.py']


def verify(root):
    manifest = json.loads((root/'PLAN.json').read_bytes())
    for name, expected in manifest['sources'].items():
        if sha(name) != expected:
            raise ValueError('Development source drift')


def worker(root, method, chain):
    verify(root)
    start = time.monotonic()
    y = np.resize(np.array([.001,-.002,.0005,0.,.003]),32)
    model = Target(y,np.ones((32,1)),np.empty((32,0)),np.ones(32,dtype=bool),rho=.95,nu=5.,priors=Priors(2*np.log(.005),1.,np.log(.2),.5,.002,.03))
    q = np.r_[model.priors.mu_mean,model.priors.log_sigma_mean,0.,np.zeros(32)]
    rng = np.random.default_rng(2026102807000000+100*method+chain)
    function = (sweep,sweep_interwoven)[method]
    budget = EvaluationBudget(2000000)
    result = dict(method=method,chain=chain,status='running',completed_sweeps=0)
    full, compact = [], []
    try:
        for step in range(3000):
            if time.monotonic()-start > 100:
                raise TimeoutError('Development chain time cap')
            q,_ = function(model,q,rng,budget=budget)
            result['completed_sweeps'] = step+1
            if step >= 1000:
                full.append(q.copy())
                compact.append(np.r_[q[:3],model.path(q)[-1]])
        result['status'] = 'complete'
    except Exception as exc:
        result.update(status='failed',error=repr(exc))
    finally:
        name = f'm{method}-c{chain}'
        path = root/(name+'.npz')
        np.savez_compressed(path, full=np.asarray(full), compact=np.asarray(compact))
        result.update(elapsed_seconds=time.monotonic()-start,retained=len(compact),evaluations=budget.calls,arrays_sha256=sha(path))
        verify(root)
        write(root/(name+'.json'),result)
    return 0 if result['status']=='complete' else 1


def campaign(root):
    root.mkdir(exist_ok=False)
    write(root/'PLAN.json',dict(scope='Fixed literal development fixture; no market data, target qualification or cross-hardware speed claim',
                              warmup=1000,retained=2000,chains=4,methods=['original','interwoven'],
                              seeds=[2026102807000000+100*m+c for m in range(2) for c in range(4)],
                              internal_chain_cap_seconds=100,external_chain_cap_seconds=120,
                              sources={str(p):sha(p) for p in sources()}))
    receipts = []
    for method in range(2):
        for chain in range(4):
            start = time.monotonic()
            with (root/f'm{method}-c{chain}.log').open('wb') as log:
                try:
                    completed = subprocess.run([sys.executable,str(Path(__file__).resolve()),str(root),'--worker',str(method),str(chain)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
                    receipt = dict(method=method,chain=chain,exit_code=completed.returncode)
                except subprocess.TimeoutExpired:
                    receipt = dict(method=method,chain=chain,external_timeout=True)
            receipt['outer_seconds'] = time.monotonic()-start
            receipts.append(receipt)
            write(root/f'm{method}-c{chain}-receipt.json',receipt)
    write(root/'FINAL.json',dict(receipts=receipts,planned=8))
    return 0 if all(r.get('exit_code')==0 for r in receipts) else 1


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    parser.add_argument('--worker',nargs=2,type=int)
    args=parser.parse_args()
    raise SystemExit(worker(args.root,*args.worker) if args.worker else campaign(args.root.resolve()))
