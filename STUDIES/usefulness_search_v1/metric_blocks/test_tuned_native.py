import hashlib,json,sys,tomllib
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'tuned_native_test01';root.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
s=json.loads((l/'tuned_native_build01/SUMMARY.json').read_text());assert s['passed'];builds={b['package']:b for b in s['rows']};rows=[];locks=[]
for n,b in builds.items():
    assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256'];lock=tomllib.loads((p/n/'Cargo.lock').read_text());locks.append({v['name']:(v['version'],v.get('source'),v.get('checksum')) for v in lock['package'] if v.get('source')})
assert locks[0]==locks[1]
for representation in ['direct','latent']:
    for adaptation in ['diag','low_rank']:
        for arm in ['original','enabled']:
            old=l/'banana_recycling_test01'/f'{representation}-{adaptation}-{arm}';out=root/old.name;out.mkdir();name='tuned_native_pristine_runner' if arm=='original' else 'tuned_native_recycling_runner';r=execute([builds[name]['binary'],str(old/'INPUT.json'),str(out/'RAW.json')],str(root),180,out,2*1024**3,64*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
            a=json.loads((old/'RAW.json').read_text());b=json.loads((out/'RAW.json').read_text())
            for v in [a,b]:
                for c in v['chains']:c.pop('seconds')
            assert a==b;rows.append(dict(case=out.name,exact_default_replay=True))
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,builds=builds),indent=2)+'\n');print(json.dumps(rows))
