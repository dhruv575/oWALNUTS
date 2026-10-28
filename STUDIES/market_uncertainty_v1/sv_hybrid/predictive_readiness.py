"""Fixed three-label numerical readiness on a completed literal fixture."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import arviz as az
import numpy as np


def run(root):
    root=Path(root)
    if not (root/'FINAL.json').exists():
        raise ValueError('Terminal development ledger required')
    path=Path(__file__).resolve().parents[2]/'predictive_value_diagnostic_v1'/'predictive_density.py'
    spec=importlib.util.spec_from_file_location('development_predictive_density',path)
    evaluator=importlib.util.module_from_spec(spec);sys.modules[spec.name]=evaluator;spec.loader.exec_module(evaluator)
    result=dict(scope='Literal numerical/predictive-functional readiness; no observed market scoring or independent reference',
                labels=[-.005,0.,.005],identity=evaluator.implementation_identity(),arviz=az.__version__,rows=[])
    for method in range(2):
        draws=[]
        for chain in range(4):
            record=json.loads((root/f'm{method}-c{chain}.json').read_bytes())
            if record['status']!='complete':
                break
            p=root/f'm{method}-c{chain}.npz'
            if hashlib.sha256(p.read_bytes()).hexdigest()!=record['arrays_sha256']:
                raise ValueError('Source draw drift')
            with np.load(p,allow_pickle=False) as stored:
                draws.append(stored['compact'].copy())
        for index,label in enumerate(result['labels']):
            row=dict(method=method,label=label,status='unavailable');result['rows'].append(row)
            if len(draws)!=4:
                continue
            try:
                started=time.monotonic()
                score=evaluator.evaluate_observation(np.stack(draws),label,deadline=started+30)
                logs,pits=score['logpdf_by_chain_draw'],score['pit_by_chain_draw']
                scaled=np.exp(logs-logs.max())
                def mcse(a):
                    return 0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
                row.update(status='available',logpdf=score['logpdf'],pit=score['pit'],
                           logpdf_mcse=mcse(scaled)/float(scaled.mean()),pit_mcse=mcse(pits),
                           seconds=time.monotonic()-started,numerical=score['numerical'])
                out=root/f'predictive-m{method}-label{index}.npz'
                if out.exists():raise FileExistsError(out)
                np.savez_compressed(out,logpdf=logs,pit=pits)
                row['array_sha256']=hashlib.sha256(out.read_bytes()).hexdigest()
            except (ValueError,TimeoutError) as exc:
                row.update(status='unavailable',error=repr(exc))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('out');args=parser.parse_args()
    result=run(args.root)
    with Path(args.out).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(result))
