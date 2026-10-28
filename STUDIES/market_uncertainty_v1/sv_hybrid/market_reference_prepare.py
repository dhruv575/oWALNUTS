"""Bind the existing validated target/runtime to every fixed market input."""
import argparse,copy,json,shutil
from pathlib import Path
from literal_reference import sha,write,validate

def prepare(root,parent,windows,audit):
    root=Path(root).resolve();root.mkdir(exist_ok=False)
    prior=json.loads(Path(parent).read_bytes());panel=json.loads(Path(windows).read_bytes())
    record=json.loads(Path(audit).read_bytes());seeds=record['reserved_seeds']
    if record['status']!='passed' or record['collisions'] or len(seeds)!=48 or len(set(seeds))!=48:raise ValueError('48 audited seeds required')
    if len(panel['windows'])!=24:raise ValueError('24 fixed windows required')
    for name in ('stan','adapter','capture','sdk_makefile','runtime_inventory'):
        item=prior['bindings'][name]
        if sha(item['path'])!=item['sha256']:raise ValueError('Parent binding drift')
    shutil.copyfile(parent,root/'PARENT.json');shutil.copyfile(windows,root/'WINDOW-PARENT.json');shutil.copyfile(audit,root/'SEED-AUDIT.json')
    source=Path(__file__).resolve().parent;manifests=[]
    for i,window in enumerate(panel['windows']):
        if sha(window['file'])!=window['sha256']:raise ValueError('Window drift')
        if seeds[2*i+1]!=seeds[2*i]+1:raise ValueError('Sampling/initialization seed pair required')
        a=root/f'audit-{i:02d}.json'
        write(a,dict(status='passed',collisions=[],reserved_seeds=seeds[2*i:2*i+2],parent_sha256=sha(root/'SEED-AUDIT.json')))
        spec=copy.deepcopy(prior)
        spec.update(scope='fixed_market_reference',spot=i,window_metadata=window,
                    sampling=dict(chains=4,draws=8000,tune=4000,cores=4),
                    limits=dict(seconds=1800,rss_bytes=4*1024**3,output_bytes=1024**3),seed=seeds[2*i],
                    seed_audit=dict(path=str(a),sha256=sha(a),reserved_seeds=seeds[2*i:2*i+2]))
        spec.pop('comparator_archive_sha256',None);spec.pop('comparator_scope',None)
        spec['preparer_sha256']=sha(__file__)
        for name,path in [('worker',source/'literal_reference.py'),('monitor',source/'resource_monitor.py'),('window',Path(window['file']))]:
            spec['bindings'][name]=dict(path=str(path),sha256=sha(path))
        validate(spec);path=root/f'manifest-{i:02d}.json';write(path,spec)
        manifests.append(dict(path=str(path),sha256=sha(path)))
    write(root/'PANEL.json',dict(status='frozen_authorized',manifests=manifests,
          sources={str(p):sha(p) for p in [*source.glob('*.py'),root/'PARENT.json',root/'WINDOW-PARENT.json',root/'SEED-AUDIT.json']}))
    return dict(manifests=24,panel_sha256=sha(root/'PANEL.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('parent');p.add_argument('windows');p.add_argument('audit');a=p.parse_args()
    print(json.dumps(prepare(a.root,a.parent,a.windows,a.audit)))
