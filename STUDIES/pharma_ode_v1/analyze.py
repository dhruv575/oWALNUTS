"""Frozen selection, reference qualification and all-target reporting."""
import json,sys
from pathlib import Path
import numpy as np
from backend import Backend,ROOT
from worker import CASES
from features import features,summarize,heldout

def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def rows(root):
    root=Path(root);out=[]
    for i,(phase,case,config,rep) in enumerate(read(root/'MANIFEST.json')['jobs']):
        p=root/f'{i:03d}'/'result';r=read(p/'RESULT.json') if (p/'RESULT.json').exists() else dict(phase=phase,case=case,config=config,rep=rep,status='missing_or_censored')
        r['folder']=str(p);out.append(r)
    return out
def tolerance(summary,p,n):return np.r_[.1*np.array(summary['sd'][:p]),np.full(n,.03),.02,.02]
def tuning_key(r):
    if r['status']!='ok':return (2,float('inf'),r['config'])
    s=r['summary']
    if s['diagnostic_pass']:return (0,r['seconds'],r['config'])
    mc=np.array([float('inf') if x is None else x for x in s['mcse']]);sd=np.array(s['sd'])
    return (1,float(np.max(mc/np.maximum(sd,1e-15))),r['config'])
def accuracy(r,ref,p,n):
    if r['status']!='ok' or not ref['qualified']:return dict(pass_all=False,reason='failed run or unqualified reference')
    s=r['summary'];rs=ref['summary'];tol=tolerance(rs,p,n);err=np.abs(np.array(s['mean'])-rs['mean']);rm=np.array(rs['mcse']);mc=np.array([float('inf') if x is None else x for x in s['mcse']])
    bound=tol+3*rm
    return dict(pass_all=bool(s['diagnostic_pass'] and np.all(err<=bound) and np.all(mc<=tol/2)),mean_pass=bool(np.all(err<=bound)),mcse_pass=bool(np.all(mc<=tol/2)),max_error_ratio=float(np.max(err/bound)),forecast_error_ratio=float(np.max(err[p:]/bound[p:])),max_mcse_ratio=None if not np.isfinite(mc).all() else float(np.max(mc/(tol/2))))
def qualify(case,rr):
    if len(rr)!=2 or any(r['status']!='ok' for r in rr):return dict(qualified=False,reason='reference run failed or censored')
    data=read(ROOT/'data'/f'{case}.json');meta=read(ROOT/'data/CASES.json')[case]
    loaded=[np.load(Path(r['folder'])/'draws.npz') for r in rr];q=np.concatenate([a['q'] for a in loaded]);pred=np.concatenate([a['pred'] for a in loaded]);p=data['P'];n=data['Npred']
    f=features(q.reshape(-1,p),pred.reshape(-1,n),meta['threshold']).reshape(*q.shape[:2],-1)
    s=summarize(f,sum(r['divergences'] for r in rr),sum(r['depth_hits'] for r in rr),2000)
    tol=tolerance(s,p,n);mc=np.array([float('inf') if x is None else x for x in s['mcse']]);agreement=bool(np.all(np.abs(np.array(rr[0]['summary']['mean'])-rr[1]['summary']['mean'])<=np.maximum(3*mc,tol/2)))
    audit=dict(points=0,max_log_prediction_difference=0.,max_scaled_gradient_difference=0.,errors=[])
    base=Backend(data);tight=Backend(dict(data,tol=1e-10));rk=Backend(dict(data,tol=1e-10,solver=1))
    try:
        for a in loaded:
            flat=a['q'].reshape(-1,p)
            for i in np.linspace(0,len(flat)-1,16,dtype=int):
                try:
                    point=flat[i];_,g=base.value(point);prediction=base.predict(point)
                    for other in (tight,rk):
                        _,gg=other.value(point);pp=other.predict(point)
                        audit['max_log_prediction_difference']=max(audit['max_log_prediction_difference'],float(np.max(np.abs(pp-prediction))))
                        audit['max_scaled_gradient_difference']=max(audit['max_scaled_gradient_difference'],float(np.max(np.abs(gg-g)/(1+np.abs(g)))))
                    audit['points']+=1
                except Exception as e:audit['errors'].append(repr(e))
    finally:
        for b in (base,tight,rk):b.close()
    audit['pass']=bool(not audit['errors'] and audit['max_log_prediction_difference']<=.003 and audit['max_scaled_gradient_difference']<=.001)
    return dict(qualified=bool(s['diagnostic_pass'] and agreement and audit['pass']),summary=s,separate_mean_agreement=agreement,numerical_audit=audit,heldout=heldout(q,pred,meta['holdout_concentration']),reference_seconds=sum(r['seconds'] for r in rr))
def initial(root):
    rr=rows(root);selected={case:{e:min([r for r in rr if r['phase']=='calibrate' and r['case']==case and r['config'].startswith(e+'_')],key=tuning_key)['config'] for e in ('walnuts','nuts')} for case in CASES[:4]}
    write(ROOT/'SELECTION.json',dict(selected=selected,rule='calibration only; diagnostic pass, then time; otherwise max MCSE/SD'))
    refs={}
    for case in CASES:
        refs[case]=qualify(case,[r for r in rr if r['phase']=='reference' and r['case']==case]);write(ROOT/'REFERENCES.json',refs);print(case,refs[case]['qualified'],flush=True)
    write(ROOT/'INITIAL-ROWS.json',rr)
def paired(w,n,key):
    ratios=[n[i][key]/w[i][key] for i in sorted(set(w)&set(n))]
    if not ratios:return dict(pairs=0,geomean=None,bootstrap95=None)
    logs=np.log(ratios);rng=np.random.default_rng(895000000);boot=np.exp(rng.choice(logs,(10000,len(logs)),replace=True).mean(axis=1))
    return dict(pairs=len(ratios),geomean=float(np.exp(logs.mean())),bootstrap95=np.quantile(boot,[.025,.975]).tolist(),ratios=ratios)
def final(root):
    rr=rows(root);refs=read(ROOT/'REFERENCES.json');initial_rows=read(ROOT/'INITIAL-ROWS.json');out={}
    for case in CASES[:4]:
        data=read(ROOT/'data'/f'{case}.json');ref=refs[case];engines={}
        for e in ('walnuts','nuts'):
            runs=[r for r in rr if r['case']==case and r['config'].startswith(e+'_')]
            for r in runs:r['accuracy']=accuracy(r,ref,data['P'],data['Npred'])
            engines[e]=dict(completed=sum(r['status']=='ok' for r in runs),diagnostic_pass=sum(r.get('summary',{}).get('diagnostic_pass',False) for r in runs),accuracy_pass=sum(r['accuracy']['pass_all'] for r in runs))
        good={e:{r['rep']:r for r in rr if r['case']==case and r['config'].startswith(e+'_') and r['accuracy']['pass_all']} for e in engines}
        speed=paired(good['walnuts'],good['nuts'],'seconds');cold=paired(good['walnuts'],good['nuts'],'total_seconds')
        out[case]=dict(reference_qualified=ref['qualified'],engines=engines,kernel_speedup=speed,total_speedup=cold,sampler_gate=bool(engines['walnuts']['accuracy_pass']>=7 and engines['walnuts']['accuracy_pass']>=engines['nuts']['accuracy_pass'] and speed['pairs'] and speed['geomean']>=1.5 and speed['bootstrap95'][0]>1))
    laplace={}
    for r in initial_rows:
        if r['phase']=='laplace':
            data=read(ROOT/'data'/f"{r['case']}.json");laplace[r['case']]=dict(status=r['status'],accuracy=accuracy(r,refs[r['case']],data['P'],data['Npred']),heldout=r.get('heldout'),seconds=r.get('seconds'),total_seconds=r.get('total_seconds'))
    write(ROOT/'ROWS.json',rr);write(ROOT/'SUMMARY.json',dict(targets=out,laplace=laplace,references=refs,selection=read(ROOT/'SELECTION.json'),scope='Three subjects; two heldout observations each; descriptive pilot only'))
    print(json.dumps(out,indent=2))
if __name__=='__main__':{'initial':initial,'final':final}[sys.argv[1]](sys.argv[2])
