"""Exposed full-budget instrumentation diagnostic; not fresh evidence."""
import json,sys
from pathlib import Path
import numpy as np
from native_common import STUDY,LOCAL,model_files,native_model,native_run

root=LOCAL/'nativearma_replay01'
if len(sys.argv)==1:
    root.mkdir(exist_ok=False)
    sys.path.insert(0,str(LOCAL/'inputs'))
    from resource_monitor import execute
    r=execute([sys.executable,str(Path(__file__)),'worker'],str(root),180,root,2*1024**3,64*1024**2,root/'worker.log',output_scan_interval=2)
    (root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    assert r['exit_code']==0 and r['group_drained']
else:
    so,data,source=model_files('arma-arma11');rows=[]
    for mode in ['draw_diag','diag','low_rank']:
        results=[]
        for label,path in [('plain',so),('counted',LOCAL/'nativemodels01/arma-arma11/counted_model.so')]:
            result,stats,settings=native_run(native_model(path,data,source),940600001,mode)
            np.savez_compressed(root/(mode+'-'+label+'.npz'),draws=result['draws'],**stats)
            results.append(result)
        a,b=results
        rows.append(dict(mode=mode,exact_draws=bool(np.array_equal(a['draws'],b['draws'])),plain_divergences=a['retained_divergences'],counted_divergences=b['retained_divergences']))
    (root/'SUMMARY.json').write_text(json.dumps(dict(scope=__doc__,rows=rows),indent=2)+'\n')
