"""One terminal method/window analysis, retaining incomplete chains and reference flags."""
import argparse,json,time
from pathlib import Path
import numpy as np
import arviz as az
from literal_reference import sha,write,load
from reference_report import summarize,metrics


def collect_chains(root,spec,spot,method):
    records=[];full=[];compact=[]
    methods=spec.get('methods',[0,1])
    if methods not in ([0,1],[2]) or method not in methods:raise ValueError('Declared method panel')
    for chain in range(4):
        j=spot*4*len(methods)+methods.index(method)*4+chain;directory=root/f'campaign01/chain-{j:03d}'
        monitor=json.loads((directory/'MONITOR.json').read_bytes()) if (directory/'MONITOR.json').exists() else dict(status='missing')
        path=directory/'fit/FINAL.json';done=json.loads(path.read_bytes()) if path.exists() else dict(status='missing')
        records.append(dict(index=j,monitor=monitor,done=done))
        if done['status']!='complete' or monitor.get('exit_code')!=0 or monitor.get('group_drained') is not True:continue
        if (done['index'],done['spot'],done['method'],done['chain'])!=(j,spot,method,chain):raise ValueError('Chain identity')
        start=json.loads((directory/'fit/STARTED.json').read_bytes())
        if start['seed']!=spec['seeds'][j] or start['manifest_sha256']!=sha(root/'MANIFEST.json') or start['window_sha256']!=spec['windows'][spot]['sha256']:
            raise ValueError('Chain source/seed binding')
        path=directory/'fit/draws.npz'
        if sha(path)!=done['arrays_sha256']:raise ValueError('Specialist draws drift')
        with np.load(path,allow_pickle=False) as data:
            retained=spec.get('retained',2000)
            if data['full'].shape!=(retained,253) or data['compact'].shape!=(retained,4):raise ValueError('Specialist axes')
            full.append(data['full'].copy());compact.append(data['compact'].copy())
    return records,full,compact


def run(root,reference_root,index,evaluator_path,out):
    root=Path(root);reference_root=Path(reference_root);out=Path(out);out.mkdir(exist_ok=False)
    spec=json.loads((root/'MANIFEST.json').read_bytes());methods=spec.get('methods',[0,1])
    if methods not in ([0,1],[2]) or not 0<=index<24*len(methods):raise ValueError('Fixed fit index')
    if json.loads((root/'SUPERVISION.json').read_bytes()).get('group_drained') is not True:
        raise ValueError('Terminal drained campaign required')
    spot,position=divmod(index,len(methods));method=methods[position];item=spec['windows'][spot]
    if sha(root/Path(item['file']).name)!=item['sha256']:raise ValueError('Window drift')
    with np.load(root/Path(item['file']).name,allow_pickle=False) as data:
        if float(data['label'])!=item['label']:raise ValueError('Actual-label mismatch')
    comparison=reference_root/'COMPARISON.json'
    if sha(comparison)!='51a9157e7de396022a4f28a9cfdf0aff609ce0d6a227c067fc3447ec0bc46b57':raise ValueError('Reference comparison drift')
    rows=json.loads(comparison.read_bytes())['rows'];ref=rows[spot]
    if (ref['month'],ref['tick'])!=(item['month'],item['tick']):raise ValueError('Reference spot mismatch')
    directory=reference_root/f'campaign01/job-{spot:02d}/results'/item['month']/f'references/{spot%8:02d}'
    if sha(directory/'reference.json')!=ref['extended_sha256']:raise ValueError('Reference receipt drift')
    receipt=json.loads((directory/'reference.json').read_bytes())
    if receipt['origin_ms']!=item['origin_ms'] or receipt['label_available_ms']!=item['label_available_ms']:raise ValueError('Causal timestamps differ')
    if sha(directory/receipt['compact']['file'])!=receipt['compact']['sha256']:raise ValueError('Reference draw drift')
    rd=np.load(directory/receipt['compact']['file'],allow_pickle=False)
    if rd.shape!=(4,16000,4):raise ValueError('Reference axes')
    names=('mu','log_sigma','beta','h_last')
    result=dict(index=index,spot=spot,method=method,month=item['month'],tick=item['tick'],status='unavailable',
                reference=ref['extended'],reference_compact={n:metrics(rd[:,:,i]) for i,n in enumerate(names)},chains=[],
                source_sha256=sha(__file__),manifest_sha256=sha(root/'MANIFEST.json'))
    result['chains'],full,compact=collect_chains(root,spec,spot,method)
    if len(full)==4:
        draws=np.stack(compact);result.update(summarize(np.stack(full),draws));result['status']='complete'
        result['mean_differences']={n:result['coordinates'][n]['mean']-result['reference_compact'][n]['mean'] for n in names}
        if sha(evaluator_path)!='e46294e0ac3ea9805bf5b4713c15ea3f63e73b37b9de6b27d7186706ebc03094':raise ValueError('Evaluator drift')
        evaluator=load(evaluator_path,'market_fixed_predictive')
        try:
            score=evaluator.evaluate_observation(draws,item['label'],deadline=time.monotonic()+30)
            logs,pits=score['logpdf_by_chain_draw'],score['pit_by_chain_draw'];scaled=np.exp(logs-logs.max())
            def mcse(a):return 0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
            lm,pm=mcse(scaled)/float(scaled.mean()),mcse(pits)
            if not np.isfinite([lm,pm]).all():raise ValueError('Nonfinite MCSE')
            np.savez_compressed(out/'scores.npz',logpdf=logs,pit=pits)
            result['predictive']=dict(status='available',logpdf=score['logpdf'],pit=score['pit'],logpdf_mcse=lm,pit_mcse=pm,numerical=score['numerical'],
                                      difference={n:score[n]-ref['extended'][n] for n in ('logpdf','pit')},array_sha256=sha(out/'scores.npz'))
        except (ValueError,TimeoutError) as exc:result['predictive']=dict(status='unavailable',error=repr(exc))
    else:result['predictive']=dict(status='unavailable',reason='Incomplete four-chain fit')
    write(out/'REPORT.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('reference_root');p.add_argument('index',type=int);p.add_argument('evaluator');p.add_argument('out');a=p.parse_args()
    run(a.root,a.reference_root,a.index,a.evaluator,a.out)
