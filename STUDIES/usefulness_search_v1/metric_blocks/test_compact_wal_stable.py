import hashlib,json,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'compact_wal_stable_test01';r.mkdir(exist_ok=False)
sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
s=json.loads((l/'compact_wal_stable_build01/SUMMARY.json').read_text());assert s['passed'];builds={b['package']:b for b in s['rows']};rows=[]
for target in ['analytic_rotated_gaussian','noncentered','funnel']:
    old=l/'compact_validation01'/(target+'-00')
    for arm,name in [('original','compact_original_runner'),('observed','compact_recycling_runner')]:
        b=builds[name];assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
        out=r/(target+'-'+arm);out.mkdir();result=execute([b['binary'],str(old/f'INPUT-{arm}.json'),str(out/'RAW.json')],str(r),180,out,2*1024**3,64*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');assert result['exit_code']==0 and result['group_drained']
        a=json.loads((old/f'RAW-{arm}.json').read_text());c=json.loads((out/'RAW.json').read_text())
        for data in [a,c]:
            for chain in data['chains']:chain.pop('seconds')
        assert a==c,(target,arm);rows.append(dict(target=target,arm=arm,exact_compiler_replay=True))
(r/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,builds=builds),indent=2)+'\n');print(json.dumps(rows))
