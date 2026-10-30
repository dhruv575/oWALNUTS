import hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
import fisher_high_precision,fisher_qr_mp
from scaled_policy import prepare as original_prepare
from scaled_policy_qr import prepare as fast_prepare
from native_common import STUDY,LOCAL,MODELS,ARMS,model_files,counter_handle,counter_read,native_model,native_run

model=sys.argv[1];seed=int(sys.argv[2]);root=Path(sys.argv[3]);so,data,source=model_files(model)
qualified=LOCAL/'nativemodels01'/model;qualification=json.loads((qualified/'SUMMARY.json').read_text());assert qualification['passed']
shim=qualified/'counted_model.so';assert hashlib.sha256(shim.read_bytes()).hexdigest()==qualification['inputs'][str(shim)]
binary=LOCAL/'inputs/online-binary';refs=json.loads((LOCAL/'localscaled01/REFERENCES.json').read_text());ref=refs[model];assert ref['passed']
sources=[STUDY/n for n in ['native_screen_worker.py','native_common.py','scaled_policy.py','scaled_policy_qr.py','fisher_high_precision.py','fisher_qr_mp.py','hybrid_gate.py','selector.py','selector_full_shape.py','NATIVE-COMPARISON-SCREEN.md']]+[so,data,source,shim,binary,LOCAL/'localscaled01/REFERENCES.json',so.parent/'SUMMARY.json']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
d=len(json.loads((so.parent/'SUMMARY.json').read_text())['points'][0])
starts=np.random.default_rng(seed).uniform(-2,2,(4,d)).tolist();base=dict(model=str(so),data=str(data),starts=starts,seed=seed,warmup=250,draws=100,arm='diag')
def binary_run(folder,args):
    (folder/'INPUT.json').write_text(json.dumps(args,indent=2)+'\n');ip=folder/'INPUT.json';op=folder/'RESULT.json'
    subprocess.run([str(binary),str(ip),str(op)],check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    result=json.loads(op.read_text());q=np.asarray(result['draws']);assert np.isfinite(q).all();return result,q
pilot_folder=root/'pilot';pilot_folder.mkdir();t=time.perf_counter();pilot,pilot_q=binary_run(pilot_folder,base);pilot_seconds=time.perf_counter()-t
assert pilot_q.shape==(4,100,d)
(pilot_folder/'TIMING.json').write_text(json.dumps(dict(post_import_operation_seconds=pilot_seconds),indent=2)+'\n')
order=ARMS.copy();rotation=(seed-940600001+MODELS.index(model))%len(order);order=order[rotation:]+order[:rotation]
rows=[];results={}
for arm in order:
    folder=root/arm;folder.mkdir();t=time.perf_counter()
    try:
        if arm.startswith('native_'):
            c=counter_handle(shim);c.ow_reset_target_calls();compiled=native_model(shim,data,source)
            result,stats,settings=native_run(compiled,seed,arm.removeprefix('native_'));counts=counter_read(c);elapsed=time.perf_counter()-t
            assert all(counts[k]==0 for k in ['value','hessian','hvp']) and counts['gradient']>=result['native_steps']
            q=result['draws'];result=dict(result,draws=q.tolist());calls=counts['gradient'];selection=None
            np.savez_compressed(folder/'NATIVE-STATS.npz',**stats);(folder/'SETTINGS.json').write_text(json.dumps(settings,indent=2)+'\n');(folder/'RESULT.json').write_text(json.dumps(result,allow_nan=False)+'\n')
            timing=dict(operation_seconds=elapsed,shared_pilot_seconds=0.,stage_operation_seconds=elapsed,api_calls=counts)
        else:
            policy='auto' if arm=='walnuts_auto' else ('fisher' if arm=='fisher_fast' else 'scaled')
            prepare=original_prepare if arm=='scaled_original' else fast_prepare
            if policy=='auto':
                detail=prepare(pilot_q,None,policy);counts=dict(value=0,gradient=0,hessian=0,hvp=0)
            else:
                c=counter_handle(shim);c.ow_reset_target_calls();target=bs.StanModel(str(shim),data=data.read_text(),seed=1)
                detail=prepare(pilot_q,target,policy);counts=counter_read(c)
            assert counts==dict(value=0,gradient=detail['calls'],hessian=0,hvp=0)
            args=dict(base,starts=pilot_q[:,-1,:].tolist(),seed=seed+100000,warmup=750,draws=2000,arm=detail['mode'])
            if detail['mass'] is not None:args['mass']=np.asarray(detail['mass']).ravel().tolist()
            result,q=binary_run(folder,args);stage_seconds=time.perf_counter()-t;elapsed=pilot_seconds+stage_seconds
            calls=pilot['target_calls']+counts['gradient']+result['target_calls'];selection={k:detail[k] for k in ['branch','gate','selection','scaled_selection'] if k in detail}
            (folder/'POLICY.json').write_text(json.dumps(detail,indent=2,allow_nan=False)+'\n');timing=dict(operation_seconds=elapsed,shared_pilot_seconds=pilot_seconds,stage_operation_seconds=stage_seconds,api_calls=counts,pilot_calls=pilot['target_calls'],sampler_calls=result['target_calls'])
        assert q.shape==(4,2000,d) and np.isfinite(q).all()
        (folder/'TIMING.json').write_text(json.dumps(timing,indent=2)+'\n');results[arm]=(result,q)
        rows.append(dict(model=model,seed=seed,arm=arm,calls=calls,seconds=elapsed,selection=selection,timing=timing))
    except Exception:
        error=traceback.format_exc();(folder/'ERROR.txt').write_text(error);rows.append(dict(model=model,seed=seed,arm=arm,passed=False,error=error,failed_operation_seconds=time.perf_counter()-t))
    (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')

# Shared diagnostic work follows all arm clocks.
target=bs.StanModel(str(so),data=data.read_text(),seed=1)
def cname(n):
    p=n.split('.');return p[0]+'['+','.join(p[1:])+']' if len(p)>1 and all(s.isdigit() for s in p[1:]) else n
names=[cname(n) for n in target.param_names(include_tp=True,include_gq=False)];ix=[names.index(n) for n in ref['names']];assert len(target.param_unc_names())==d
for row in rows:
    if row['arm'] not in results:continue
    result,q=results[row['arm']];a=np.asarray([target.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,d)]).reshape(4,2000,-1)
    ds=az.convert_to_dataset({'p':a});mean=a.mean((0,1));sd=a.reshape(-1,a.shape[-1]).std(0,ddof=1);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);rh=np.asarray(az.rhat(ds,method='rank').p);mcse=np.asarray(az.mcse(ds,method='mean').p)
    z=np.abs(mean-ref['mean'])/np.sqrt(mcse**2+np.asarray(ref['mcse'])**2);delta=np.abs(mean-ref['mean'])/ref['sd'];se=np.abs(sd/ref['sd']-1)
    passed=all(np.isfinite(v).all() for v in [mean,sd,bulk,tail,rh,mcse,z,delta,se]) and max(rh)<=1.01 and min(bulk)>=400 and min(tail)>=400 and result['retained_divergences']==0 and max(z)<=4.5 and max(delta)<=.1 and max(se)<=.1
    row.update(passed=bool(passed),rhat=float(max(rh)),bulk=float(min(bulk)),tail=float(min(tail)),divergences=result['retained_divergences'],max_z=float(max(z)),max_mean_sd=float(max(delta)),max_sd_error=float(max(se)),efficiency=float(min(bulk)/row['calls']),time_efficiency=float(min(bulk)/row['seconds']),functionals={k:v.tolist() for k,v in dict(mean=mean,sd=sd,bulk=bulk,tail=tail,rhat=rh,mcse=mcse).items()})
def clean(v):
    if isinstance(v,float) and not np.isfinite(v):return None
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,list):return [clean(x) for x in v]
    return v
rows=clean(rows)
summary=dict(rows=rows,order=order,pilot_seconds=pilot_seconds,inputs=hashes,unchanged=all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p)] for p in sources),timing_scope='Post-import through unconstrained draws and core diagnostics ready; model construction/fitting and WALNUTS subprocess transport included; reference diagnostics/evidence writes excluded.')
(root/'SUMMARY.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');assert summary['unchanged'];print(json.dumps([dict(arm=r['arm'],passed=r['passed']) for r in rows]))
