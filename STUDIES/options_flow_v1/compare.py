"""Compare only healthy paired reports; endpoint precision remains explicit."""
import argparse,json
from pathlib import Path

def compare(directory,reference_override=None):
    reports={p.name.removesuffix('-report.json'):json.loads(p.read_text()) for p in Path(directory).glob('*-report.json')}
    rows=[]
    for arm,r in reports.items():
        if arm.startswith('numpyro'):continue
        reference=reference_override or ('numpyro-fisher-shear' if arm.endswith('fisher-shear') else 'numpyro-fisher' if arm.endswith('fisher') else 'numpyro-noncentered' if arm.endswith('noncentered') else 'numpyro')
        ref=reports.get(reference)
        row={'arm':arm,'reference':reference,'comparable':False}
        if ref and r.get('status')=='completed' and ref.get('status')=='completed':
            matched=r['fixture_sha256']==ref['fixture_sha256'] and r['settings']==ref['settings']
            healthy=r.get('healthy',False) and ref.get('healthy',False)
            row.update(matched=matched,both_healthy=healthy,comparable=matched and healthy)
            row['cold_process_speedup']=ref['process_seconds']/r['process_seconds'] if row['comparable'] else None
            rows_precision={}
            for name,d in r['evaluation']['functionals'].items():
                n=ref['evaluation']['functionals'][name]
                rows_precision[name]={'owalnuts_endpoint_mcse':d['endpoint_mcse'],'reference_endpoint_mcse':n['endpoint_mcse'],
                                     'mean_difference':d['mean']-n['mean'],
                                     'combined_mean_mcse':(d['mean_mcse']**2+n['mean_mcse']**2)**.5}
            row['precision']=rows_precision
        rows.append(row)
    return {'rows':rows,'qualified':False,'interpretation':'Raw speedup is reported only for matched healthy fits; endpoint precision may differ. Time-to-target requires prespecified precision stopping checkpoints and replication. Cold totals exclude one-time Rust build, which must be reported separately.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--reference');a=p.parse_args();print(json.dumps(compare(a.directory,a.reference),indent=2))
