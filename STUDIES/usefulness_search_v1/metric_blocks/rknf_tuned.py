import ast,hashlib,json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'rknf_tuned01';r.mkdir(exist_ok=False)
old=json.loads((l/'rknf_leaf_screen01/SUMMARY.json').read_text())
for name in ['two_stage_screen.py','rknf_leaf_screen.py']:
    source=(p/name).read_bytes();assert hashlib.sha256(source).hexdigest()==old['source_hashes'][name]
    for node in ast.parse(source).body:
        if isinstance(node,ast.FunctionDef):exec(compile(ast.Module(body=[node],type_ignores=[]),name,'exec'))
def scored(q,mom,var,h,kind,c,mode,tol):
    a=leaf(q,mom,h,kind,c,mode,tol)
    with np.errstate(all='ignore'):a['score']=np.where(a['valid'],np.exp(np.minimum(0,-a['deltaH']))*np.mean((a['q']-q)**2/var,axis=1),0.)
    assert np.isfinite(a['score']).all()
    return a
rows=[];verification_calls=0
for ti,(kind,c,d,h) in enumerate([('gaussian',0.,24,1.),('banana',5.,24,.1),('funnel',0.,10,.5)]):
    cq,cp,var=phase(4096,947400001+ti,kind,c,d);np.savez_compressed(r/f'calibration-input-{ti}.npz',q=cq,p=cp,variance=var);cal=[];selected={}
    for mode,scale in [('H',1.),('RKNF',old['rows'][ti]['rknf_delta'])]:
        for k in range(-4,5):
            tol=scale*2**k;a=scored(cq,cp,var,h,kind,c,mode,tol);cal.append(dict(mode=mode,tolerance=tol,score_per_call=float(a['score'].mean()/a['work'].mean()),total_calls=int(a['work'].sum())))
            np.savez_compressed(r/f'calibration-output-{ti}-{mode}-{k}.npz',score=a['score'],work=a['work'],valid=a['valid'],level=a['level'])
        selected[mode]=max([x for x in cal if x['mode']==mode],key=lambda x:(x['score_per_call'],-x['tolerance']))['tolerance']
    (r/f'CALIBRATION-{ti}.json').write_text(json.dumps(dict(rows=cal,selected=selected),indent=2)+'\n')
    q,mom,var=phase(16384,947500001+ti,kind,c,d);np.savez_compressed(r/f'validation-input-{ti}.npz',q=q,p=mom,variance=var);arms=[]
    for mode in ['H','RKNF']:
        a=scored(q,mom,var,h,kind,c,mode,selected[mode]);np.savez_compressed(r/f'validation-output-{ti}-{mode}.npz',**a);ix=np.flatnonzero(a['valid'])[:256];assert len(ix)==256
        back=leaf(a['q'][ix],-a['p'][ix],h,kind,c,mode,selected[mode]);verification_calls+=int(back['work'].sum());assert back['valid'].all() and np.array_equal(back['level'],a['level'][ix]);assert np.max(abs(back['q']-q[ix]))<1e-7 and np.max(abs(back['p']+mom[ix]))<1e-7;arms.append(a)
    ratio=float((arms[1]['score'].mean()/arms[1]['work'].mean())/(arms[0]['score'].mean()/arms[0]['work'].mean()));rng=np.random.default_rng(947600001+ti);ratios=[]
    for _ in range(20):
        ix=rng.integers(0,len(q),(100,len(q)));ratios.extend(((arms[1]['score'][ix].mean(1)/arms[1]['work'][ix].mean(1))/(arms[0]['score'][ix].mean(1)/arms[0]['work'][ix].mean(1))).tolist())
    row=dict(target=kind,selected=selected,ratio=ratio,interval=np.quantile(ratios,[.025,.975]).tolist(),calibration_calls={m:sum(x['total_calls'] for x in cal if x['mode']==m) for m in selected},arms={m:dict(mean_calls=float(a['work'].mean()),mean_score=float(a['score'].mean()),reverse_rejection_fraction=float(a['reverse_rejected'].mean()),exhaustion_fraction=float((a['level']<0).mean())) for m,a in zip(['H','RKNF'],arms)});rows.append(row);print(json.dumps(row),flush=True)
passed=rows[1]['interval'][0]>1.1 and rows[1]['arms']['RKNF']['reverse_rejection_fraction']<rows[1]['arms']['H']['reverse_rejection_fraction'] and rows[2]['ratio']>=.9
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,passed=passed,rows=rows,verification_calls=verification_calls,source_hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['rknf_tuned.py','RKNF-TUNED-PROTOCOL.md','rknf_leaf_screen.py','two_stage_screen.py']}),indent=2,allow_nan=False)+'\n')
