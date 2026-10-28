"""All 24 original/new references; retain failures, no candidate replacement."""
import argparse,hashlib,json,math
from pathlib import Path

MONTHS=('2025-12','2026-01','2026-02')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def metrics(r):
    if r.get('status')!='complete':return dict(status=r.get('status'),error=r.get('reason'))
    values=[v for d in r['diagnostics'].values() for v in d.values()]
    expected=(all(math.isfinite(v) for v in values)
              and all(d['rhat']<=1.01 and d['bulk_ess']>=1000 and d['tail_ess']>=1000 for d in r['diagnostics'].values())
              and sum(r['metadata']['divergences'])==0
              and r['precision']['logpdf_delta_mcse']<=.01 and r['precision']['pit_mcse']<=.005)
    if expected != r['reference_diagnostics_pass']:raise ValueError('Diagnostic gate disagreement')
    return dict(status=r['status'],passed=r['reference_diagnostics_pass'],
                logpdf=r['score']['logpdf'],pit=r['score']['pit'],
                logpdf_mcse=r['precision']['logpdf_delta_mcse'],pit_mcse=r['precision']['pit_mcse'],
                divergences=sum(r['metadata']['divergences']),
                max_rhat=max(x['rhat'] for x in r['diagnostics'].values()),
                min_bulk_ess=min(x['bulk_ess'] for x in r['diagnostics'].values()),
                min_tail_ess=min(x['tail_ess'] for x in r['diagnostics'].values()))

def report(root,original):
    root=Path(root);original=Path(original)
    final=json.loads((root/'campaign01/FINAL.json').read_bytes())
    supervision=json.loads((root/'SUPERVISION.json').read_bytes())
    seal={}
    for line in (original/'ARTIFACTS.sha256').read_text().splitlines():
        digest,name=line.split(maxsplit=1);seal[name.lstrip('*')]=digest
    rows=[]
    for j in range(24):
        m=MONTHS[j//8];i=j%8
        oldpath=original/f'campaign01/batch/inference/{m}/references/{i:02d}/reference.json'
        if sha(oldpath)!=seal.get(oldpath.relative_to(original).as_posix()):raise ValueError('Original evidence drift')
        newpath=root/f'campaign01/job-{j:02d}/results/{m}/references/{i:02d}/reference.json'
        old=json.loads(oldpath.read_bytes());new=json.loads(newpath.read_bytes()) if newpath.exists() else dict(status='unavailable')
        if new.get('status')=='complete' and (new['index'],new['tick'])!=(old['index'],old['tick']):raise ValueError('Reference identity mismatch')
        a,b=metrics(old),metrics(new)
        row=dict(job=j,month=m,index=i,tick=old['tick'],original=a,extended=b,
                 original_sha256=sha(oldpath),extended_sha256=sha(newpath) if newpath.exists() else None,
                 monitor=final['jobs'][j])
        if a['status']==b['status']=='complete':
            row['extended_minus_original']=dict(logpdf=b['logpdf']-a['logpdf'],pit=b['pit']-a['pit'])
        rows.append(row)
    return dict(planned=24,original_pass=sum(r['original'].get('passed',False) for r in rows),
                extended_pass=sum(r['extended'].get('passed',False) for r in rows),
                completed=sum(r['extended']['status']=='complete' for r in rows),rows=rows,
                supervision=supervision,elapsed_seconds=final['elapsed_seconds'],output_bytes=final['output_bytes'],
                scope='Exploratory all-point new fits; does not replace E66 or qualify the entire posterior path')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('original');p.add_argument('out');a=p.parse_args()
    v=report(a.root,a.original)
    with Path(a.out).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
    print(json.dumps({k:v[k] for k in ('planned','original_pass','extended_pass','completed','elapsed_seconds','output_bytes')}))
