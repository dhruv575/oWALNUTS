"""Fixed three-label reference scoring, retaining all six specialist contrasts."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import arviz as az
from literal_reference import load, sha, write

LABELS=[-.005,0.,.005]


def contrasts(specialist, reference):
    output=[]
    for method in range(2):
        for label in LABELS:
            row=dict(method=method,label=label,status='unavailable');output.append(row)
            left=[r for r in specialist if r['method']==method and r['label']==label]
            right=[r for r in reference if r['label']==label]
            if len(left)!=1 or len(right)!=1:raise ValueError('Exact fixed score slots required')
            a,b=left[0],right[0]
            if a['status']=='available' and b['status']=='available':
                row.update(status='available',logpdf_difference=a['logpdf']-b['logpdf'],
                           pit_difference=a['pit']-b['pit'],specialist_logpdf_mcse=a['logpdf_mcse'],
                           reference_logpdf_mcse=b['logpdf_mcse'],specialist_pit_mcse=a['pit_mcse'],
                           reference_pit_mcse=b['pit_mcse'])
    return output


def run(reference,development,out):
    reference=Path(reference);development=Path(development);out=Path(out);out.mkdir(exist_ok=False)
    evaluator=load(Path(__file__).resolve().parents[2]/'predictive_value_diagnostic_v1/predictive_density.py','literal_predictive')
    previous=json.loads((development/'PREDICTIVE.json').read_bytes())
    if previous['labels']!=LABELS or previous['identity']['source_sha256']!=evaluator.implementation_identity()['source_sha256']:
        raise ValueError('Fixed labels or evaluator drift')
    if len(previous['rows'])!=6:raise ValueError('All specialist score slots required')
    for r in previous['rows']:
        if r['status']=='available':
            i=LABELS.index(r['label']);p=development/f"predictive-m{r['method']}-label{i}.npz"
            if sha(p)!=r['array_sha256']:raise ValueError('Specialist score array drift')
    supervision=json.loads((reference/'SUPERVISION.json').read_bytes())
    if supervision.get('group_drained') is not True:raise ValueError('Drained reference required')
    p=reference/'fit/FINAL.json';final=json.loads(p.read_bytes()) if p.exists() else dict(status='missing')
    draws=None
    if final['status']=='complete' and supervision.get('exit_code')==0:
        p=reference/'fit/draws.npz'
        if sha(p)!=final['arrays_sha256']:raise ValueError('Reference array drift')
        with np.load(p,allow_pickle=False) as stored:draws=stored['compact'].copy()
        if draws.shape!=(4,4000,4) or not np.isfinite(draws).all():raise ValueError('Reference compact axes')
    rows=[]
    for i,label in enumerate(LABELS):
        row=dict(label=label,status='unavailable');rows.append(row)
        if draws is None:continue
        try:
            score=evaluator.evaluate_observation(draws,label,deadline=time.monotonic()+30)
            logs,pits=score['logpdf_by_chain_draw'],score['pit_by_chain_draw']
            scaled=np.exp(logs-logs.max())
            def mcse(a):return 0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
            density_mcse=mcse(scaled)/float(scaled.mean());pit_mcse=mcse(pits)
            if not np.isfinite([density_mcse,pit_mcse]).all():raise ValueError('Nonfinite MCSE')
            path=out/f'reference-label{i}.npz';np.savez_compressed(path,logpdf=logs,pit=pits)
            row.update(status='available',logpdf=score['logpdf'],pit=score['pit'],logpdf_mcse=density_mcse,
                       pit_mcse=pit_mcse,numerical=score['numerical'],array_sha256=sha(path))
        except (ValueError,TimeoutError) as exc:row['error']=repr(exc)
    result=dict(scope='Literal predictive corroboration only; consult reference diagnostic flags separately',
                labels=LABELS,identity=evaluator.implementation_identity(),source_sha256=sha(__file__),
                specialist_report_sha256=sha(development/'PREDICTIVE.json'),reference_receipt=final,
                reference_rows=rows,contrasts=contrasts(previous['rows'],rows),
                uncertainty='Separate MCSE values; no combined independence approximation or equivalence verdict')
    write(out/'REPORT.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reference');p.add_argument('development');p.add_argument('out');a=p.parse_args()
    run(a.reference,a.development,a.out)
