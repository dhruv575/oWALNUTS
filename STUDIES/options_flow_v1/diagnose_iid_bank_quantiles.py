"""Posthoc reconstruction of every iid-null allocation trial, no new seeds.

Reuses the archived generation algorithm; excludes rho!=0 or shift!=0 by
mathematical scope, never by bank success. No bootstrap is rerun. Exact bands
are simultaneous for two quantiles PER backend, not over all48backends.
"""
import argparse,hashlib,importlib.metadata,json,math,sys,zipfile
from pathlib import Path
import numpy as np
from scipy.signal import lfilter
from exact_iid_quantile_control import control
PIN='a67f4dda5eb27ef8953ce3078f12963ed5d17b9a2bdda89af0c31997dfbf9c55'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(campaign):
    root=Path(campaign);plan=load(root/'plan.json')
    if sha(root/'plan.json')!=PIN or (root/'plan.sha256').read_text().strip()!=PIN:raise ValueError('Frozen195plan mismatch')
    if plan['python']!=sys.version or plan['software']!={n:importlib.metadata.version(n) for n in ['numpy','scipy']} or sha(sys.executable)!=plan['interpreter']['sha256']:raise ValueError('Generation runtime mismatch')
    with zipfile.ZipFile(root/'study-source.zip') as z:
        for name,h in plan['source'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=h:raise ValueError('Archived generation source mismatch')
        generator=z.read('reference_bank_allocation.py').decode()
        if 'innov[0]=np.random.default_rng(c[\'init_seeds\'][i]).normal()' not in generator or 'v=lfilter([1.],[1.,-rho],innov)' not in generator:raise ValueError('Archived generator requires rereview')
    audit=load(root/'independent-audit.json');provenance=load(root/'auditor-provenance.json')
    if not audit['integrity_pass'] or sha(root/'independent-audit.json')!=provenance['audit_sha256'] or sha(root/'study-source.zip')!=provenance['source_zip_sha256']:raise ValueError('Archived audit binding mismatch')
    cells=[c for c in plan['cells'] if c['phase']=='campaign' and c['rho']==0 and c['backend_b_shift']==0]
    if len(cells)!=24:raise ValueError('All24iidnull trials required')
    rows=[];trial_rows=[]
    for c in cells:
        f=c['fits_per_backend'];n=c['lengths'][-1];draws=[]
        for seed,init in zip(c['fit_seeds'],c['init_seeds']):
            innovations=np.random.default_rng(seed).normal(size=n)*np.sqrt(1-c['rho']**2)
            innovations[0]=np.random.default_rng(init).normal()
            draws.append(lfilter([1.],[1.,-c['rho']],innovations))
        original=load(root/'results'/c['id']/'result.json');bankpath=root/'results'/c['id']/'bank.json'
        expected=next(v for k,v in audit['artifact_sha256'].items() if Path(k).resolve()==bankpath.resolve())
        if sha(bankpath)!=expected:raise ValueError('Original bank changed')
        resultpath=root/'results'/c['id']/'result.json'
        if sha(resultpath)!=next(v for k,v in audit['artifact_sha256'].items() if Path(k).resolve()==resultpath.resolve()):raise ValueError('Original result changed')
        pooled=np.concatenate(draws);ordered=np.sort(pooled);original_quantiles=[float(ordered[math.ceil(p*len(ordered))-1]) for p in [.05,.95]]
        if original_quantiles!=[b['estimate'] for b in original['bounds']]:raise ValueError('Reconstructed pooled quantiles differ from original bank')
        for index,backend in enumerate(['a','b']):
            values=np.concatenate(draws[index*f:(index+1)*f]);r=control(values.tolist(),iid_confirmed=True)
            rows.append(dict(trial_id=c['id'],backend=backend,fits=f,draws_per_fit=n,fit_seeds=c['fit_seeds'][index*f:(index+1)*f],initialization_seeds=c['init_seeds'][index*f:(index+1)*f],draws_float64_sha256=hashlib.sha256(values.astype('<f8').tobytes()).hexdigest(),**r))
        trial_rows.append(dict(id=c['id'],bank_status=original['bank_status'],bootstrap_both_truth_covered=original['both_endpoints_cover_truth'],original_bootstrap_bounds=original['bounds'],exact_pooled_control=control(pooled.tolist(),iid_confirmed=True)))
    return dict(phase='posthoc_diagnostic',qualified=False,plan_sha256=PIN,source_zip_sha256=sha(root/'study-source.zip'),runtime=plan['software'],script_sha256=sha(__file__),control_sha256=sha(Path(__file__).with_name('exact_iid_quantile_control.py')),expected_iid_null_trials=24,expected_backends=48,backend_rows=rows,trial_rows=trial_rows,backend_misses=[{'trial_id':r['trial_id'],'backend':r['backend']} for r in rows if not r['both_or_all_covered']],pooled_misses=[r['id'] for r in trial_rows if not r['exact_pooled_control']['both_or_all_covered']],limitations=['Posthoc reconstruction of existing streams, no new prospective decisions or sampling campaign.','All24iidnull trials retained regardless of original resolution/coverage. Shifted/dependent cases mathematically ineligible for this iid-normal control.','Two-endpoint Bonferroni guarantee is per backend/control only; no simultaneous guarantee across48backend controls or24pooled controls.','Comparisons illustrate finite-fit bootstrap uncertainty; no calibration conclusion from selected misses.'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--campaign',required=True);p.add_argument('--out',required=True);a=p.parse_args();r=run(a.campaign)
    with Path(a.out).open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
