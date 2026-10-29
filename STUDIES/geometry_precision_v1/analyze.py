"""Coarse time-to-accuracy ladders with explicit censoring and tuning separation."""
import json,hashlib,sys
from pathlib import Path
import numpy as np

NAMES=['isotropic','correlated','banana','funnel_moderate','funnel_severe','funnel_noncentered','changing_scale','student_t','mixture']
BUDGETS=[250,1000,3000]


def ladder(rows):
    by_budget={r['draws']:r for r in rows}
    total=0.;sampling=0.;calls=0;cost_complete=True;attempts=[]
    for d in BUDGETS:
        r=by_budget.get(d)
        if r is None:return dict(reached=False,censored=True,reason='missing_attempt',attempts=attempts)
        total+=r.get('total_seconds',r.get('resource_seconds',0.))
        sampling+=r.get('seconds',0.);calls+=r.get('target_calls',0)
        if 'seconds' not in r or 'target_calls' not in r:cost_complete=False
        passed=r.get('status')=='ok' and r.get('metrics',{}).get('passed',False)
        attempts.append(dict(draws=d,passed=passed,status=r.get('status')))
        if passed:return dict(reached=True,censored=False,budget=d,total_seconds=total,sampler_seconds=sampling if cost_complete else None,target_calls=calls if cost_complete else None,attempts=attempts)
    return dict(reached=False,censored=True,total_seconds_spent=total,attempts=attempts)


def ratio_summary(ratios,seed):
    if not ratios:return dict(n=0,median=None,interval_95=None)
    x=np.asarray(ratios);rng=np.random.default_rng(seed)
    samples=np.median(x[rng.integers(0,len(x),size=(10000,len(x)))],axis=1)
    return dict(n=len(x),median=float(np.median(x)),interval_95=np.quantile(samples,[.025,.975]).tolist(),scope='Paired successful ladders only; exploratory median ratio, no censoring correction')


def load_rows(root):
    final=json.loads((root/'FINAL.json').read_text());manifest=json.loads((root/'MANIFEST.json').read_text())
    assert len(final['jobs'])==len(manifest['jobs']) and final['sources_unchanged']
    rows=[]
    for job in final['jobs']:
        index=job['index'];name,config,rep,draws=manifest['jobs'][index]
        folder=root/f'{index:03d}-{name}-{config}-{rep}-{draws}'
        p=folder/'result/RESULT.json'
        if p.exists():
            r=json.loads(p.read_text());assert (r['name'],r['config'],r['rep'],r['draws'])==(name,config,rep,draws)
        else:r=dict(name=name,config=config,rep=rep,draws=draws,status='resource_failed')
        if not job.get('group_drained') or job.get('exit_code')!=0:r['status']='resource_failed'
        r['resource_seconds']=job.get('elapsed_seconds',0.);r['engine']='nuts' if config.startswith('nuts') else 'walnuts';rows.append(r)
    return rows,manifest,final


def run(root,out):
    root=Path(root);out=Path(out);rows,manifest,final=load_rows(root/'test-v1');cal,cm,cf=load_rows(root/'calibrate-v1')
    assert len(rows)==432 and len(cal)==126
    selection=json.loads((root/'SELECTION.json').read_text())
    assert hashlib.sha256((root/'SELECTION.json').read_bytes()).hexdigest()==manifest['selection_sha256']
    summary=dict(planned_validation=432,reported_validation=sum(r['status']=='ok' for r in rows),planned_calibration=126,
        calibration_wall_seconds=cf['elapsed_seconds'],validation_wall_seconds=final['elapsed_seconds'],targets={},selected=selection['selected'],versions=manifest['versions'])
    for ni,name in enumerate(NAMES):
        result=dict(methods={});ladders={}
        for engine in ['nuts','walnuts']:
            subset=[r for r in rows if r['name']==name and r['engine']==engine]
            assert len(subset)==24 and all(r['config']==selection['selected'][name][engine] for r in subset)
            series=[dict(rep=rep,**ladder([r for r in subset if r['rep']==rep])) for rep in range(8)];ladders[engine]=series
            result['methods'][engine]=dict(reached=sum(r['reached'] for r in series),planned=8,ladders=series,
                fixed_budget_passes={str(d):sum(r.get('metrics',{}).get('passed',False) for r in subset if r['draws']==d and r['status']=='ok') for d in BUDGETS},
                failed_executions=sum(r['status']!='ok' for r in subset))
        result['nuts_over_walnuts']={}
        for metric in ['total_seconds','sampler_seconds','target_calls']:
            values=[a[metric]/b[metric] for a,b in zip(ladders['nuts'],ladders['walnuts']) if a['reached'] and b['reached'] and a.get(metric) is not None and b.get(metric) is not None and b[metric]>0]
            result['nuts_over_walnuts'][metric]=ratio_summary(values,665000000+ni)
        a,b=result['methods']['nuts']['reached'],result['methods']['walnuts']['reached']
        result['cold_total_lead']=bool(b>=7 and b>=a and (result['nuts_over_walnuts']['total_seconds']['median'] or 0)>=1.5)
        result['sampler_only_lead']=bool(b>=7 and b>=a and (result['nuts_over_walnuts']['sampler_seconds']['median'] or 0)>=1.5)
        summary['targets'][name]=result
    controls=[]
    cfinal=json.loads((root/'controls-v1/FINAL.json').read_text());assert cfinal['sources_unchanged']
    for job in cfinal['jobs']:
        p=root/'controls-v1'/f"{job['index']:02d}"/'result/RESULTS.json'
        if job.get('exit_code')==0 and job.get('group_drained') and p.exists():controls+=json.loads(p.read_text())
    for name,v in summary['targets'].items():
        v['controls']={m:{str(d):dict(reported=sum(r['name']==name and r['method']==m and r.get('draws')==d for r in controls),passed=sum(r.get('metrics',{}).get('passed',False) for r in controls if r['name']==name and r['method']==m and r.get('draws')==d)) for d in (BUDGETS if m=='iid' else [3000])} for m in ['iid','laplace']}
    warm=[];wfinal=json.loads((root/'warm-v1/FINAL.json').read_text());assert len(wfinal['jobs'])==16 and wfinal['sources_unchanged']
    for job in wfinal['jobs']:
        p=root/'warm-v1'/f"{job['index']:02d}"/'result/RESULT.json'
        if p.exists():
            r=json.loads(p.read_text());r['resource_ok']=job.get('exit_code')==0 and job.get('group_drained');warm.append(r)
    summary['warm']={}
    for name in ['correlated','banana']:
        summary['warm'][name]={}
        for path in ['smooth','abrupt']:
            subset=[r for r in warm if r['name']==name and r['path']==path];group={}
            for mode in ['walnuts_warm','nuts_cold','walnuts_cold']:
                records=[(r,next((v for v in r['results'] if v['mode']==mode),{})) for r in subset]
                allok=[];times=[];update_passes=0;updates_reported=0
                for owner,r in records:
                    updates=r.get('updates',[]);passes=sum(u['metrics']['passed'] for u in updates);update_passes+=passes;updates_reported+=len(updates)
                    passed=bool(owner['resource_ok'] and r.get('status')=='ok' and len(updates)==6 and passes==6 and (mode!='walnuts_warm' or r.get('initial_metrics',{}).get('passed',False)))
                    allok.append(passed)
                    if r.get('status')=='ok':times.append(r['total_seconds'])
                group[mode]=dict(planned_streams=4,reported=len(records),qualified_streams=sum(allok),planned_updates=24,reported_updates=updates_reported,passing_updates=update_passes,median_total_seconds=float(np.median(times)) if times else None)
            summary['warm'][name][path]=group
    out.mkdir(parents=True,exist_ok=False)
    for filename,value in [('SUMMARY.json',summary),('VALIDATION-ROWS.json',rows),('CALIBRATION-ROWS.json',cal),('CONTROL-ROWS.json',controls),('WARM-ROWS.json',warm)]:
        (out/filename).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(validation=sum(r['status']=='ok' for r in rows),controls=len(controls),warm_streams=len(warm))))


if __name__=='__main__':run(*sys.argv[1:])
