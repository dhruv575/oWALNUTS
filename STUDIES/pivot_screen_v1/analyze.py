"""Full planned-denominator report; exploratory paired intervals, no winner claims."""
import json,sys,hashlib
from pathlib import Path
import numpy as np

CANDIDATES=['hierarchical_ab','revenue_ab','contextual_bandit','inventory']
SCENARIOS=['easy','near_tie','sparse','heterogeneous','misspecified']


def interval(values,seed):
    x=np.asarray(values,dtype=float)
    if not len(x):return dict(n=0,mean=None,interval_95=None)
    rng=np.random.default_rng(seed)
    means=x[rng.integers(0,len(x),size=(10000,len(x)))].mean(axis=1)
    return dict(n=len(x),mean=float(x.mean()),interval_95=np.quantile(means,[.025,.975]).tolist())


def method(row,name):
    if name in row['methods']:return row['methods'][name]
    if name in row.get('baselines',{}):return dict(qualified=True,status='ok',decision=row['baselines'][name])
    return dict(status='missing',qualified=False)


def paired(rows,first,second,seed,strict=False):
    # Positive = second loses more than first. Replicates, not decisions, resampled.
    deltas=[];raw=[];pairs=[]
    for row in rows:
        a,b=method(row,first),method(row,second)
        if not (a.get('qualified') and b.get('qualified')):continue
        if strict and not a.get('strict_reference_qualified'):continue
        deltas.append(b['decision']['normalized_regret']-a['decision']['normalized_regret'])
        raw.append(b['decision']['regret']-a['decision']['regret']);pairs.append(row['replicate'])
    result=interval(deltas,seed);result['raw_units']=interval(raw,seed);result['replicates']=pairs
    return result


def summarize(rows,candidate,seed):
    names=['nuts','walnuts','laplace']+(['ucb'] if candidate=='contextual_bandit' else ['separate_beta','pooled_beta'] if candidate=='hierarchical_ab' else ['sample_mean','bootstrap'] if candidate=='revenue_ab' else ['empirical_quantile','shrinkage_nb'])
    methods={}
    for name in names:
        executed=[method(r,name) for r in rows if method(r,name).get('status')=='ok']
        usable=[v for v in executed if v.get('qualified')]
        times=[v['total_seconds'] for v in executed if 'total_seconds' in v]
        methods[name]=dict(executed=len(executed),screen_qualified=len(usable),strict_reference_qualified=sum(v.get('strict_reference_qualified',False) for v in executed),
            mean_regret=float(np.mean([v['decision']['regret'] for v in usable])) if usable else None,
            mean_normalized_regret=float(np.mean([v['decision']['normalized_regret'] for v in usable])) if usable else None,
            median_seconds=float(np.median(times)) if times else None,p95_seconds=float(np.quantile(times,.95)) if times else None,
            timing_scope='All completed method executions, including diagnostic failures; import cost recorded separately')
    comparisons={}
    for i,name in enumerate(names):
        if name in ['nuts','walnuts']:continue
        comparisons['nuts_vs_'+name]=paired(rows,'nuts',name,seed+i)
        comparisons['strict_nuts_vs_'+name]=paired(rows,'nuts',name,seed+i,strict=True)
        comparisons['walnuts_vs_'+name]=paired(rows,'walnuts',name,seed+i)
    comparisons['walnuts_vs_nuts']=paired(rows,'walnuts','nuts',seed+50)
    return dict(reported=len(rows),methods=methods,comparisons=comparisons)


def run(root,output):
    root=Path(root);output=Path(output);manifest=json.loads((root/'MANIFEST.json').read_text());final=json.loads((root/'FINAL.json').read_text())
    assert manifest['mode']=='main' and len(manifest['jobs'])==400 and len(final['jobs'])==400 and final['sources_unchanged']
    assert sorted(r['index'] for r in final['jobs'])==list(range(400))
    rows=[];missing=[];inputs={}
    for index,(c,s,r) in enumerate(manifest['jobs']):
        folder=root/f'{index:03d}-{c}-{s}-{r:02d}'
        receipt=final['jobs'][index]
        assert (receipt['candidate'],receipt['scenario'],receipt['replicate'])==(c,s,r)
        p=folder/'result/RESULT.json'
        if not p.exists():missing.append(index);continue
        if receipt.get('exit_code')!=0 or not receipt.get('group_drained'):missing.append(index);continue
        row=json.loads(p.read_text());assert not row['pilot'] and (row['candidate'],row['scenario'],row['replicate'])==(c,s,r)
        rows.append(row);inputs[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
    result=dict(planned=400,reported=len(rows),missing_or_resource_failed=missing,wall_seconds=final['elapsed_seconds'],source_hashes=manifest['sources'],versions=manifest['versions'],candidates={},scope='Exploratory synthetic screen; no multiplicity adjustment, no real-world or matched-precision advantage established')
    for ci,c in enumerate(CANDIDATES):
        selected=[r for r in rows if r['candidate']==c];v=summarize(selected,c,549100000+ci*1000)
        v['planned']=100;v['scenarios']={}
        for si,s in enumerate(SCENARIOS):
            group=[r for r in selected if r['scenario']==s];v['scenarios'][s]=dict(planned=20,**summarize(group,c,549100000+ci*1000+si*100))
        # The aggregate is descriptive; replace naive pooled interval with a
        # stratified paired bootstrap preserving five fixed scenario weights.
        for key,comp in v['comparisons'].items():
            strict=key.startswith('strict_');clean=key.removeprefix('strict_');a,b=clean.split('_vs_')
            groups=[]
            for s in SCENARIOS:
                vals=[]
                for r in selected:
                    if r['scenario']!=s:continue
                    first,second=method(r,a),method(r,b)
                    if first.get('qualified') and second.get('qualified') and (not strict or first.get('strict_reference_qualified')):
                        vals.append([second['decision']['normalized_regret']-first['decision']['normalized_regret'],second['decision']['regret']-first['decision']['regret']])
                groups.append(np.asarray(vals))
            if all(len(g) for g in groups):
                rng=np.random.default_rng(549100000+ci*1000);means=np.zeros((10000,2))
                for g in groups:means+=g[rng.integers(0,len(g),size=(10000,len(g)))].mean(axis=1)/5
                comp['mean']=float(np.mean([g[:,0].mean() for g in groups]));comp['interval_95']=np.quantile(means[:,0],[.025,.975]).tolist()
                comp['raw_units']['mean']=float(np.mean([g[:,1].mean() for g in groups]));comp['raw_units']['interval_95']=np.quantile(means[:,1],[.025,.975]).tolist()
            else:comp['mean']=None;comp['interval_95']=None;comp['raw_units']['mean']=None;comp['raw_units']['interval_95']=None
            comp['bootstrap']='10,000 stratified paired draws, equal five-scenario weights; available-case within scenario'
        if c!='contextual_bandit':
            discrepancies=[]
            for r in selected:
                a,b=method(r,'nuts'),method(r,'walnuts')
                if not(a.get('strict_reference_qualified') and b.get('qualified')):continue
                zs=[]
                for x,y in zip(a['functional_summary'],b['functional_summary']):
                    se=np.hypot(x['mcse_mean'],y['mcse_mean'])
                    zs.append(abs(x['mean']-y['mean'])/se if se else 0.)
                discrepancies.append(dict(scenario=r['scenario'],replicate=r['replicate'],max_standardized_mean_difference=max(zs)))
            v['posterior_functional_checks']=discrepancies
        result['candidates'][c]=v
    output.mkdir(parents=True,exist_ok=False)
    for name,value in [('SUMMARY.json',result),('RESULTS.json',rows),('INPUT-HASHES.json',inputs)]:
        (output/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(planned=400,reported=len(rows),wall_seconds=result['wall_seconds'])))


if __name__=='__main__':run(*sys.argv[1:])
