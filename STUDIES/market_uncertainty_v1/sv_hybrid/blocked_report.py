"""Literal block-update diagnostics and fixed-label reference corroboration."""
import argparse,json,time
from pathlib import Path
import numpy as np
import arviz as az
from literal_reference import sha,write,load
from reference_report import summarize


def run(root,reference,out):
    root=Path(root);reference=Path(reference);out=Path(out);out.mkdir(exist_ok=False)
    supervisor=json.loads((root/'SUPERVISION.json').read_bytes())
    ledger=json.loads((root/'FINAL.json').read_bytes())
    if supervisor.get('group_drained') is not True or len(ledger['receipts'])!=4:raise ValueError('Terminal four-chain ledger required')
    plan=json.loads((root/'PLAN.json').read_bytes());full=[];compact=[];records=[]
    for chain in range(4):
        p=root/f'chain-{chain}/FINAL.json';r=json.loads(p.read_bytes()) if p.exists() else dict(status='missing')
        records.append(r)
        if r['status']!='complete' or ledger['receipts'][chain].get('exit_code')!=0 or ledger['receipts'][chain].get('group_drained') is not True:continue
        if r['seed']!=plan['seeds'][chain] or r['chain']!=chain or r['plan_sha256']!=sha(root/'PLAN.json'):raise ValueError('Chain provenance')
        p=root/f'chain-{chain}/draws.npz'
        if sha(p)!=r['arrays_sha256']:raise ValueError('Draw drift')
        with np.load(p,allow_pickle=False) as a:
            if a['full'].shape!=(2000,253) or a['compact'].shape!=(2000,4):raise ValueError('Draw axes')
            full.append(a['full'].copy());compact.append(a['compact'].copy())
    original=json.loads((reference/'COMPARISON.json').read_bytes())['methods'][0]
    scores=json.loads((reference/'predictive/REPORT.json').read_bytes())['reference_rows']
    result=dict(scope='Literal development only; no market or speed superiority',source_sha256=sha(__file__),chains=records,
                reference_summary_sha256=sha(reference/'COMPARISON.json'),reference_scores_sha256=sha(reference/'predictive/REPORT.json'),
                status='unavailable',predictive=[])
    if len(full)==4:
        draws=np.stack(compact);result.update(summarize(np.stack(full),draws));result['status']='complete'
        result['mean_differences']={n:result['coordinates'][n]['mean']-original['coordinates'][n]['mean'] for n in ('mu','log_sigma','beta','h_last')}
        result['reference_unresolved']=original['reference_unresolved']
        evaluator=load(Path(__file__).resolve().parents[2]/'predictive_value_diagnostic_v1/predictive_density.py','blocked_predictive')
        for index,label in enumerate([-.005,0.,.005]):
            row=dict(label=label,status='unavailable');result['predictive'].append(row)
            try:
                score=evaluator.evaluate_observation(draws,label,deadline=time.monotonic()+30)
                logs,pits=score['logpdf_by_chain_draw'],score['pit_by_chain_draw'];scaled=np.exp(logs-logs.max())
                def mcse(a):return 0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
                lm,pm=mcse(scaled)/float(scaled.mean()),mcse(pits)
                if not np.isfinite([lm,pm]).all():raise ValueError('MCSE unavailable')
                ref=next(r for r in scores if r['label']==label)
                np.savez_compressed(out/f'score-{index}.npz',logpdf=logs,pit=pits)
                row.update(status='available',logpdf=score['logpdf'],pit=score['pit'],logpdf_mcse=lm,pit_mcse=pm,
                           numerical=score['numerical'],reference=ref,array_sha256=sha(out/f'score-{index}.npz'))
                if ref['status']=='available':row['difference']={n:score[n]-ref[n] for n in ('logpdf','pit')}
            except (ValueError,TimeoutError) as exc:row['error']=repr(exc)
    else:result['predictive']=[dict(label=y,status='unavailable') for y in [-.005,0.,.005]]
    write(out/'REPORT.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('reference');p.add_argument('out');a=p.parse_args();run(a.root,a.reference,a.out)
