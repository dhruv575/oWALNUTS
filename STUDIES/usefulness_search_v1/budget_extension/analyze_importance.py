import hashlib,json,statistics,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);run=root/'importance01';manifest=json.loads((run/'MANIFEST.json').read_text());final=json.loads((run/'FINAL.json').read_text());assert final['dependencies_unchanged'] and all(r.get('group_drained') or r['status']=='not_started_disk_floor' for r in final['jobs'])
ref=json.loads((root/'audit01/AUDIT.json').read_text())['stan_public'];s=ref['new_functional_diagnostics'];assert ref['original_reference_qualified'] and s['diagnostic_pass'];d=len(s['mean'])//4;tol=np.r_[.1*np.array(s['sd'][:2*d]),np.full(2*d,.02)];bound=tol+3*np.array(s['mcse']);rows=[]
for i,(arm,n,rep) in enumerate(manifest['jobs']):
    p=run/f'{i:03d}/result/RESULT.json';r=json.loads(p.read_text()) if p.exists() else dict(arm=arm,n=n,rep=rep,status='failed_or_censored')
    r['pass']=False
    if r['status']=='ok':
        error=np.abs(np.array(r['mean'])-s['mean']);r['max_error_ratio']=float(np.max(error/bound));r['max_mcse_ratio']=float(np.max(np.array(r['mcse'])/(tol/2)))
        r['pass']=bool(r['density_accuracy_pass'] and r['weight_ess']>=400 and r['pareto_k']<.7 and r['max_error_ratio']<=1 and r['max_mcse_ratio']<=1)
    rows.append(r)
summary={}
for arm in ('mixture',):
    for n in (65536,262144):
        rr=[r for r in rows if r['arm']==arm and r['n']==n];ok=[r for r in rr if r['status']=='ok'];summary[f'{arm}_{n}']=dict(passes=sum(r['pass'] for r in rr),attempts=len(rr),completed=len(ok),median_seconds=statistics.median(r['seconds'] for r in ok) if ok else None,median_total_seconds=statistics.median(r['total_seconds'] for r in ok) if ok else None,min_weight_ess=min((r['weight_ess'] for r in ok),default=None),max_pareto_k=max((r['pareto_k'] for r in ok),default=None),max_density_discrepancy=max((r['posterior_density_max_difference'] for r in ok),default=None),density_errors=sum(r['density_errors'] for r in ok))
out=root/'importance-analysis01';out.mkdir(exist_ok=False);(out/'ROWS.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'ANALYSIS-HASH.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),manifest_sha256=hashlib.sha256((run/'MANIFEST.json').read_bytes()).hexdigest()),indent=2)+'\n');print(json.dumps(summary,indent=2))
