"""Summarize all successful and failed pilots; never select on speed alone."""
import json,statistics,sys
from pathlib import Path
def main(root,destination):
    root=Path(root);out=Path(destination);out.mkdir(exist_ok=True)
    groups={}
    for directory in ['physics_repair01','physics_precision01','results','repair01','grid_native01','grid_native_early01','grid_precision01']:
        rows=[]
        for f in sorted((root/directory).glob('*/artifact/SUMMARY.json')):
            d=json.loads(f.read_text())
            if 'method' not in d:continue
            st=d['stats'];rows.append(dict(path=str(f.relative_to(root)),method=d['method'],seed=d['seed'],passed=d['passed'],sampling_seconds=d['sampling_seconds'],total_seconds=d.get('total_seconds',d.get('worker_seconds')),min_bulk=min(x for x in st['bulk'] if x is not None),min_tail=min(x for x in st['tail'] if x is not None),max_rhat=max(x for x in st['rhat'] if x is not None),target_calls=d.get('target_calls',d.get('chain_info')),divergences=d.get('divergences'),depth_hits=d.get('depth_hits'),accuracy_pass=d.get('accuracy_pass'),precision_pass=d.get('precision_pass')))
        groups[directory]=rows
    failures=[]
    for f in root.rglob('SUPERVISION.json'):
        d=json.loads(f.read_text())
        if d['exit_code']!=0:failures.append(dict(path=str(f.relative_to(root)),**d))
    summary=dict(groups=groups,failures=failures,scope='Exploratory two-seed pilots; no qualified independent spatial reference; no general 10x claim')
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2))
    lines=['# Algorithmic speedup pilot results','',summary['scope'], '','| Campaign / method | Passing runs | Median sampling seconds | Median full seconds | Worst R-hat | Minimum bulk ESS |','|---|---:|---:|---:|---:|---:|']
    for group,rows in groups.items():
        attempts={}
        for f in (root/group).glob('*/SUPERVISION.json'):
            method=f.parent.name.rsplit('-',1)[0]
            if method!='prepare':attempts[method]=attempts.get(method,0)+1
        for method in sorted(set(r['method'] for r in rows)|set(attempts)):
            rr=[r for r in rows if r['method']==method]
            count=attempts.get(method,len(rr))
            if not rr:
                lines.append(f'| {group} / {method} | 0/{count} | — | — | — | — |');continue
            lines.append(f"| {group} / {method} | {sum(r['passed'] for r in rr)}/{count} | {statistics.median(r['sampling_seconds'] for r in rr):.3f} | {statistics.median(r['total_seconds'] for r in rr):.3f} | {max(r['max_rhat'] for r in rr):.3f} | {min(r['min_bulk'] for r in rr):.1f} |")
    lines+=['','Failed or capped jobs: '+str(len(failures))+'. See SUMMARY.json and original logs.','', 'Passing physics rows satisfy convergence, reference agreement and MCSE gates. Passing spatial rows satisfy only exploratory convergence gates; they do not establish posterior fidelity against a qualified independent reference. Full cost includes imports, diagnostics and, for transported physics, training plus shared preparation. Compilation is reported separately and is not included in worker times.']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main(*sys.argv[1:])
