import hashlib, json, shutil, sys, time
from pathlib import Path
import numpy as np
import arviz as az
from selector import select
root = Path(__file__).resolve().parent
binary = root/'source/STUDIES/metric_autoselect_confirmation_v1/target/release/online'
assert json.loads((root/'BUILD.json').read_text())['exit_code'] == 0
out = root/'runs'; out.mkdir(exist_ok=False)
durable = Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/online01')
durable.mkdir(exist_ok=False)
paths = [root/n for n in ['run_online.py', 'online.rs', 'selector.py', 'ONLINE-PREFLIGHT.md']]+[binary]
inputs = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(root/'RUN-INPUTS.json').write_text(json.dumps(inputs, indent=2)+'\n')
sys.path.insert(0, '/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
starts = [[1,-1,1], [-1,1,-1], [2,2,0], [-2,-2,0]]
rows = []
def job(name, inp):
    folder = out/name; folder.mkdir()
    (folder/'INPUT.json').write_text(json.dumps(inp, indent=2)+'\n')
    r = execute([str(binary), str(folder/'INPUT.json'), str(folder/'RESULT.json')],
                str(root), 180, folder, 2*1024**3, 64*1024**2,
                folder/'worker.log', output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r, indent=2)+'\n')
    shutil.copytree(folder, durable/name)
    assert r['exit_code'] == 0 and r['group_drained'], (name,r)
    return json.loads((folder/'RESULT.json').read_text())

def summary(result, p):
    x = np.array(result['draws']); cov = np.linalg.inv(p); sd = np.sqrt(np.diag(cov))
    data = az.from_dict(posterior={'q': x})
    rhat = float(az.rhat(data).to_array().max())
    bulk = float(az.ess(data, method='bulk').to_array().min())
    tail = float(az.ess(data, method='tail').to_array().min())
    flat = x.reshape(-1,3); white = flat @ np.linalg.cholesky(p)
    mean_error = float(np.max(np.abs(flat.mean(0))/sd))
    sd_error = float(np.max(np.abs(flat.std(0, ddof=1)/sd-1)))
    second_error = float(np.linalg.norm(white.T@white/len(white)-np.eye(3), ord=2))
    passed = rhat<=1.01 and min(bulk,tail)>=400 and mean_error<=.12 and sd_error<=.12 and second_error<=.15
    return dict(rhat=rhat, bulk_ess=bulk, tail_ess=tail, mean_error_sd=mean_error,
                relative_sd_error=sd_error, whitened_second_error=second_error, passed=passed)

begin = time.monotonic()
for model, corr in [('independent',0.), ('correlated',.98)]:
    p = np.eye(3); p[0,1] = p[1,0] = corr
    for seed in range(928300001,928300005):
        prefix = f'{model}-{seed}'
        base = dict(precision=p.tolist(), starts=starts, seed=seed, warmup=1100, draws=2000)
        pilot = job(prefix+'-pilot', dict(base, warmup=250, draws=100, arm='diag'))
        x = np.array(pilot['draws']); v = np.maximum(x.var(axis=1,ddof=1).mean(axis=0),1e-8)
        coarse=[]; fine=[]; calls=0
        probe_start=time.monotonic()
        for chain in x:
            for q in chain[[0,24,49,99]]:
                matrices=[]
                for step in [1e-4,5e-5]:
                    h=np.empty((3,3))
                    for j in range(3):
                        delta=np.eye(3)[j]*step*(1+abs(q[j]))
                        gp=-p@(q+delta); gm=-p@(q-delta); calls+=2
                        h[:,j]=-(gp-gm)/(2*delta[j])
                    matrices.append(h)
                coarse.append(matrices[0]); fine.append(matrices[1])
        c, selection=select(coarse,fine,v)
        mass=np.linalg.inv(c)
        expected=selection['blocks']==([[0,1]] if corr else [])
        probe_seconds=time.monotonic()-probe_start
        (out/(prefix+'-SELECTION.json')).write_text(json.dumps(dict(
            variances=v.tolist(), coarse=np.array(coarse).tolist(), fine=np.array(fine).tolist(),
            covariance=c.tolist(), mass=mass.tolist(), selection=selection,
            expected=expected, probe_calls=calls, probe_seconds=probe_seconds),indent=2)+'\n')
        arm='fixed_dense' if selection['blocks'] else 'fixed_diag'
        candidate=job(prefix+'-candidate',dict(base, starts=x[:,-1,:].tolist(), seed=seed+100000,
            warmup=750,arm=arm,mass=mass.ravel().tolist() if selection['blocks'] else np.diag(mass).tolist()))
        rows.append(dict(model=model,seed=seed,arm='candidate',selection=selection,selection_expected=expected,
            **summary(candidate,p),target_calls=pilot['target_calls']+calls+candidate['target_calls'],
            seconds=pilot['seconds']+probe_seconds+candidate['seconds']))
        for arm in ['diag','dense']:
            r=job(prefix+'-'+arm,dict(base,arm=arm))
            rows.append(dict(model=model,seed=seed,arm=arm,**summary(r,p),target_calls=r['target_calls'],seconds=r['seconds']))
        (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
result=dict(rows=rows,seconds=time.monotonic()-begin,inputs=inputs,
            unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items()),
            candidate_passed=all(r['passed'] and r['selection_expected'] for r in rows if r['arm']=='candidate'))
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
for p in root.glob('*.json'): shutil.copy2(p,durable/p.name)
for p in out.glob('*-SELECTION.json'): shutil.copy2(p,durable/p.name)
print(json.dumps(result))
