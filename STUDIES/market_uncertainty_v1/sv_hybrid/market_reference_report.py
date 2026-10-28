"""One reference-cost fit: full diagnostics and unchanged pointwise prediction."""
import argparse,json,time
from pathlib import Path
import numpy as np
import arviz as az
from literal_reference import sha,write,load
from reference_report import summarize

def run(root,index,comparison,evaluator,out):
    root=Path(root);out=Path(out);out.mkdir(exist_ok=False)
    if type(index) is not int or not 0<=index<24:raise ValueError('Fixed panel index')
    panel=json.loads((root/'PANEL.json').read_bytes());item=panel['manifests'][index]
    if sha(item['path'])!=item['sha256']:raise ValueError('Manifest drift')
    spec=json.loads(Path(item['path']).read_bytes());window=spec['window_metadata']
    if spec['spot']!=index or spec['scope']!='fixed_market_reference':raise ValueError('Fit identity')
    if sha(spec['bindings']['window']['path'])!=spec['bindings']['window']['sha256']:raise ValueError('Window drift')
    with np.load(spec['bindings']['window']['path'],allow_pickle=False) as data:
        if float(data['label'])!=window['label']:raise ValueError('Label mismatch')
    if sha(comparison)!='51a9157e7de396022a4f28a9cfdf0aff609ce0d6a227c067fc3447ec0bc46b57':raise ValueError('Reference comparison drift')
    ref=json.loads(Path(comparison).read_bytes())['rows'][index]
    if (ref['month'],ref['tick'])!=(window['month'],window['tick']):raise ValueError('Reference window mismatch')
    directory=root/f'campaign01/job-{index:02d}'
    monitor=json.loads((directory/'SUPERVISION.json').read_bytes()) if (directory/'SUPERVISION.json').exists() else dict(status='missing')
    final=json.loads((directory/'fit/FINAL.json').read_bytes()) if (directory/'fit/FINAL.json').exists() else dict(status='missing')
    result=dict(index=index,month=window['month'],tick=window['tick'],method='nutpie',status='unavailable',
                monitor=monitor,receipt=final,reference=ref['extended'],manifest_sha256=item['sha256'],source_sha256=sha(__file__))
    if final['status']=='complete' and monitor.get('exit_code')==0 and monitor.get('group_drained') is True:
        if final['manifest_sha256']!=item['sha256']:raise ValueError('Receipt manifest mismatch')
        path=directory/'fit/draws.npz'
        if sha(path)!=final['arrays_sha256']:raise ValueError('Draw drift')
        with np.load(path,allow_pickle=False) as data:full,compact=data['full'].copy(),data['compact'].copy()
        if full.shape!=(4,8000,253) or compact.shape!=(4,8000,4):raise ValueError('Fixed draw axes')
        result.update(summarize(full,compact));result['status']='complete'
        result['divergences']=final['metadata']['divergences']
        result['diagnostic_passed']=not result['flagged_coordinates'] and sum(result['divergences'])==0
        if sha(evaluator)!='e46294e0ac3ea9805bf5b4713c15ea3f63e73b37b9de6b27d7186706ebc03094':raise ValueError('Evaluator drift')
        module=load(evaluator,'fixed_reference_predictive')
        try:
            score=module.evaluate_observation(compact,window['label'],deadline=time.monotonic()+30)
            logs,pits=score['logpdf_by_chain_draw'],score['pit_by_chain_draw'];scaled=np.exp(logs-logs.max())
            def mcse(a):return 0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
            lm,pm=mcse(scaled)/float(scaled.mean()),mcse(pits)
            if not np.isfinite([lm,pm]).all():raise ValueError('Nonfinite MCSE')
            np.savez_compressed(out/'scores.npz',logpdf=logs,pit=pits)
            result['predictive']=dict(status='available',logpdf=score['logpdf'],pit=score['pit'],logpdf_mcse=lm,pit_mcse=pm,
                difference={n:score[n]-ref['extended'][n] for n in ('logpdf','pit')},numerical=score['numerical'],array_sha256=sha(out/'scores.npz'))
        except (ValueError,TimeoutError) as exc:result['predictive']=dict(status='unavailable',error=repr(exc))
    else:result['predictive']=dict(status='unavailable',reason='Incomplete or undrained fit')
    write(out/'REPORT.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('index',type=int);p.add_argument('comparison');p.add_argument('evaluator');p.add_argument('out');a=p.parse_args()
    run(a.root,a.index,a.comparison,a.evaluator,a.out)
