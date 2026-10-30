"""Verify scientific partitions, bounded completion and frozen provenance."""
import csv,hashlib,json,sys,collections
from pathlib import Path
root=Path(sys.argv[1]);read=lambda p:json.loads(p.read_text());sources=read(root/'source_data/SOURCES.json')
for name,meta in sources.items():assert hashlib.sha256((root/'source_data'/name).read_bytes()).hexdigest()==meta['sha256']
original=list(csv.DictReader((root/'source_data/Theoph.csv').open()));cases=read(root/'data/CASES.json');checks=[]
for sid in (1,2,3):
    subject=sorted([r for r in original if int(r['Subject'])==sid],key=lambda r:float(r['Time']));assert len(subject)==11
    for prefix in ('theoph','linear'):
        name=f'{prefix}_{sid}';d=read(root/'data'/f'{name}.json');m=cases[name]
        assert d['N']==8 and d['Npred']==10
        assert d['times']==[float(r['Time']) for r in subject[1:9]]
        assert d['concentration']==[float(r['conc']) for r in subject[1:9]]
        assert m['holdout_concentration']==[float(r['conc']) for r in subject[9:]]
        assert set(d['times']).isdisjoint(m['holdout_times'])
        assert d['c0']==float(subject[0]['conc']) and d['dose']==float(subject[0]['Wt'])*float(subject[0]['Dose'])
        assert m['threshold']==max(d['concentration'])/2
        checks.append(name)
seeds=collections.defaultdict(set);status=collections.Counter();resource=[]
for folder,count in (('initial02',53),('validation01',64)):
    run=root/folder;manifest=read(run/'MANIFEST.json');final=read(run/'FINAL.json');assert len(manifest['jobs'])==len(final['jobs'])==count and final['sources_unchanged']
    for n,h in manifest['sources'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h
    for i,job in enumerate(manifest['jobs']):
        receipt=final['jobs'][i];assert receipt['index']==i
        assert receipt.get('group_drained') or receipt['status']=='not_started_resource_admission'
        resource.append(receipt)
        p=run/f'{i:03d}/result/RESULT.json'
        if p.exists():
            r=read(p);assert [r['phase'],r['case'],r['config'],r['rep']]==job
            assert r['seed'] not in seeds[r['phase']];seeds[r['phase']].add(r['seed']);status[r['status']]+=1
        else:status['missing_or_censored']+=1
    if folder=='validation01':assert manifest['selection_sha256']==hashlib.sha256((root/'SELECTION.json').read_bytes()).hexdigest()==read(root/'SELECTION-FREEZE.json')['sha256']
for phase,a in seeds.items():
    for other,b in seeds.items():
        if phase!=other:assert a.isdisjoint(b)
result=dict(source_snapshots_verified=len(sources),holdout_partitions_verified=checks,planned_attempts=117,statuses=dict(status),all_process_groups_drained=True,source_freezes_unchanged=True,selection_freeze_verified=True,disjoint_phase_seed_counts={k:len(v) for k,v in seeds.items()},max_peak_rss_bytes=max(r.get('peak_rss',0) for r in resource),max_peak_output_bytes=max(r.get('peak_output_bytes',0) for r in resource),resource_terminations=[r for r in resource if r['status']!='exited'],seconds_by_stage={f:read(root/f/'FINAL.json')['elapsed_seconds'] for f in ('initial02','validation01')})
(root/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
