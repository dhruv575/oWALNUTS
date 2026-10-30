import hashlib,json,sys
from pathlib import Path
import numpy as np
import bridgestan as bs
from native_common import STUDY,LOCAL,model_files,build_counter,counter_handle,counter_read,native_model,native_run
model=sys.argv[1];root=Path(sys.argv[2]);so,data,source=model_files(model);shim=build_counter(model,root);counter=counter_handle(shim)
old=bs.StanModel(str(so),data=data.read_text(),seed=1);new=bs.StanModel(str(shim),data=data.read_text(),seed=1)
points=np.asarray(json.loads((so.parent/'SUMMARY.json').read_text())['points']);expected=[old.log_density_gradient(q) for q in points];counter.ow_reset_target_calls();observed=[new.log_density_gradient(q) for q in points]
assert all(np.array_equal(a[0],b[0]) and np.array_equal(a[1],b[1]) for a,b in zip(expected,observed));assert counter_read(counter)==dict(value=0,gradient=64,hessian=0,hvp=0)
rows=[]
for mode in ['draw_diag','diag','low_rank']:
    results={};counts=None
    for label,path in [('plain',so),('counted',shim)]:
        counter.ow_reset_target_calls();compiled=native_model(path,data,source);result,stats,settings=native_run(compiled,940500001,mode,tune=200,draws=100)
        if label=='counted':counts=counter_read(counter)
        np.savez_compressed(root/(mode+'-'+label+'.npz'),draws=result['draws'],**stats);results[label]=result
        (root/(mode+'-SETTINGS.json')).write_text(json.dumps(settings,indent=2)+'\n')
    a,b=results['plain'],results['counted'];same=np.array_equal(a['draws'],b['draws']) and a['retained_divergences']==b['retained_divergences']
    passed=same and counts['gradient']>=b['native_steps'] and all(counts[k]==0 for k in ['value','hessian','hvp'])
    rows.append(dict(mode=mode,passed=passed,exact_draws_and_divergences=same,calls=counts,native_steps=b['native_steps'],retained_divergences=b['retained_divergences']));assert passed
result=dict(passed=True,model=model,explicit_gradient_calls=64,rows=rows,scope='Exposed short instrumentation parity, not accuracy evidence.',inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [so,data,source,shim,Path(__file__),STUDY/'native_common.py',STUDY/'NATIVE-COMPARISON-SCREEN.md']})
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
