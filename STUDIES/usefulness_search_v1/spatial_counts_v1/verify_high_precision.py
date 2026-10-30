import hashlib,json
from pathlib import Path
import numpy as np
base=Path(__file__).resolve().parent;root=base/'high_precision_remote01';prefix='/home/ubuntu/lanes/spatial-counts-high-precision-20261030/'
for n,h in json.loads((root/'INPUT-HASHES.json').read_text()).items():
    assert n.startswith(prefix);assert hashlib.sha256((root/n[len(prefix):]).read_bytes()).hexdigest()==h,n
s=json.loads((root/'results/SUMMARY.json').read_text());assert s['completed'] and s['passed'] and sorted(x['point'] for x in s['rows'])==list(range(8));points=[];maxad=0.;maxagreement=0.
for row in sorted(s['rows'],key=lambda x:x['point']):
    i=row['point'];supervised=json.loads((root/f'results/{i}/SUPERVISION.json').read_text());assert supervised['exit_code']==0 and supervised['group_drained'];assert row==json.loads((root/f'results/{i}/SUMMARY.json').read_text());assert row['passed'] and all(row['checks'].values()) and row['f_error']<=1e-5 and row['density_error']<=1e-5
    q=np.random.default_rng(952100001).normal(scale=.25,size=(8,205))[i];assert np.array_equal(q,row['point_values']);points.append(row['point_values'])
    for item in row['rows']:
        coarse,fine=[float(x['derivative']) for x in item['estimates']];scale=max(1,abs(fine));agreement=abs(coarse-fine)/scale;error=abs(item['compiled_ad']-fine)/scale;assert agreement<=1e-5 and error<=1e-3 and np.isclose(agreement,item['precision_step_agreement'],rtol=1e-12,atol=1e-15) and np.isclose(error,item['ad_scaled_error'],rtol=1e-12,atol=1e-15);maxad=max(maxad,error);maxagreement=max(maxagreement,agreement)
so=base/'model01/spatial_gp_model.so';assert hashlib.sha256(so.read_bytes()).hexdigest()==hashlib.sha256((root/'spatial_gp_model.so').read_bytes()).hexdigest();result=dict(passed=True,dimension=205,functionals=405,points=points,library_sha256=hashlib.sha256(so.read_bytes()).hexdigest(),max_ad_scaled_error=maxad,max_precision_step_disagreement=maxagreement,max_f_error=max(x['f_error'] for x in s['rows']),max_density_error=max(x['density_error'] for x in s['rows']),original_double_fd_preflight_passed=False,qualification='Independent60/80-digit verification,unchanged model;original failed double finite difference retained',scope='Numerical target qualification only; no posterior or sampler claim',inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'results/SUMMARY.json',root/'INPUT-HASHES.json',base/'HIGH-PRECISION-PREFLIGHT.md',Path(__file__)]})
(base/'MODEL-QUALIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['points','inputs']}))
