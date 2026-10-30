"""Apply the frozen screen only to four complete, archived chunks."""
import hashlib,json
from pathlib import Path
import numpy as np

STUDY=Path(__file__).resolve().parent
MODELS=['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']
ARMS=['walnuts_auto','scaled_original','scaled_fast','fisher_fast','native_draw_diag','native_diag','native_low_rank']
SEEDS=list(range(940600001,940600005))

def accuracy(r):
    fields=['rhat','bulk','tail','divergences','max_z','max_mean_sd','max_sd_error']
    if any(r.get(k) is None for k in fields):return False
    if not np.isfinite([r[k] for k in fields]).all():return False
    return bool(r['rhat']<=1.01 and r['bulk']>=400 and r['tail']>=400 and r['divergences']==0 and r['max_z']<=4.5 and r['max_mean_sd']<=.1 and r['max_sd_error']<=.1)

def paired(a,b,indices):
    logs=np.log(np.asarray(a)/np.asarray(b))
    ci=np.quantile(np.exp(logs[indices].mean(axis=1)),[.025,.975])
    return dict(geometric_mean=float(np.exp(logs.mean())),exploratory_95_percent_ci=ci.tolist(),paired_ratios=np.exp(logs).tolist())

def main():
    rows=[];inputs={}
    for i in range(1,5):
        root=STUDY/'local_recovery'/f'nativescreen{i:02d}'
        for p in [root/'SUMMARY.json',root.parent/(root.name+'_archive')/'VERIFICATION.json']:
            inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        assert json.loads((root.parent/(root.name+'_archive')/'VERIFICATION.json').read_text())['passed']
        s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and s['seed']==SEEDS[i-1]
        assert len(s['rows'])==42;rows+=s['rows']
    index={(r['model'],r['arm'],r['seed']):r for r in rows}
    assert len(index)==168 and set(index)=={(m,a,s) for m in MODELS for a in ARMS for s in SEEDS}
    for r in rows:
        assert accuracy(r)==r['passed']
        if r['passed']:
            assert r['calls']>0 and r['seconds']>0
            assert r['efficiency']==r['bulk']/r['calls'] and r['time_efficiency']==r['bulk']/r['seconds']
    boot=np.random.default_rng(940699999).integers(0,4,size=(10000,4))
    losses=[dict(model=m,seed=s) for m in MODELS for s in SEEDS if index[m,'walnuts_auto',s]['passed'] and not index[m,'scaled_fast',s]['passed']]
    results=[]
    for m in MODELS:
        passes={a:sum(index[m,a,s]['passed'] for s in SEEDS) for a in ARMS};comparisons={}
        for a in ARMS:
            if a=='scaled_fast':continue
            comparisons[a]=None
            if passes['scaled_fast']==passes[a]==4:
                comparisons[a]={k:paired([index[m,'scaled_fast',s][k] for s in SEEDS],[index[m,a,s][k] for s in SEEDS],boot) for k in ['efficiency','time_efficiency']}
        native=[a for a in ARMS if a.startswith('native_') and passes[a]==4]
        controls=['walnuts_auto']+native
        signal=bool(m not in ['arK-arK','sblrc-blr'] and not losses and native and passes['scaled_fast']==4 and all(comparisons[a] is not None and all(v['geometric_mean']>=1.2 for v in comparisons[a].values()) for a in controls))
        results.append(dict(model=m,passes=passes,fast_scaled_vs=comparisons,fully_qualified_native=native,promising_efficiency_signal=signal))
    out=dict(scope='Exploratory exposed-model screen, not application validation or simultaneous inference.',inputs=inputs,paired_accuracy_losses=losses,models=results,promising_efficiency_signal=any(r['promising_efficiency_signal'] for r in results))
    (STUDY/'NATIVE-SCREEN-ANALYSIS.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    lines=['# Native comparison screen results','',out['scope'],'','Passes out of four fresh seeds:','', '| Target | '+ ' | '.join(ARMS)+' |','|---|'+'---:|'*7]
    for r in results:lines.append('| '+r['model']+' | '+' | '.join(str(r['passes'][a]) for a in ARMS)+' |')
    lines+=['','Promising efficiency screen: '+str(out['promising_efficiency_signal'])+'.','Paired accuracy losses versus automatic: '+str(len(losses))+'.','','Fast scaled / control geometric ESS-per-gradient and ESS-per-post-import-second ratios:','']
    for r in results:
        lines.append('- '+r['model']+': '+ '; '.join(a+' '+('/'.join(f"{v[k]['geometric_mean']:.3f}" for k in ['efficiency','time_efficiency']) if v is not None else 'unqualified') for a,v in r['fast_scaled_vs'].items()))
    lines+=['','Unqualified pairs have no efficiency claim. JSON preserves all paired ratios and exploratory bootstrap intervals. Native default starts and schedules differ from WALNUTS; these are workflow comparisons. Timing excludes imports and common reference diagnostics. The ARMA exposed replay reproduced native failures without instrumentation. No deployment or application value is established.']
    (STUDY/'NATIVE-SCREEN-REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(promising_efficiency_signal=out['promising_efficiency_signal'],paired_accuracy_losses=losses)))

if __name__=='__main__':main()
