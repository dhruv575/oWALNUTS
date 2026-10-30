import hashlib,json,sys,tomllib
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_wal_driver_test02';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
b=json.loads((l/'gp_wal_build02/SUMMARY.json').read_text());assert b['passed'];bins=b['rows']
for x in bins:assert hashlib.sha256(Path(x['binary']).read_bytes()).hexdigest()==x['binary_sha256']
def registry(name):return sorted((x['name'],x['version'],x.get('checksum')) for x in tomllib.loads((p/name/'Cargo.lock').read_text())['package'] if 'source' in x)
assert registry('gp_wal_pristine_runner')==registry('gp_wal_tuned_runner')
base=json.loads((l/'gp_fresh_comparison01/walnuts_auto-946200001/INPUT.json').read_text());base.update(warmup=1100,draws=100);rows=[]
for metric in ['auto','dense']:
    results=[]
    for label,index,accept in [('original',0,None),('omitted',1,None),('explicit',1,.8)]:
        folder=r/f'{metric}-{label}';folder.mkdir();spec=dict(base,arm=metric)
        if accept is not None:spec['target_accept']=accept
        (folder/'INPUT.json').write_text(json.dumps(spec));result=execute([bins[index]['binary'],str(folder/'INPUT.json'),str(folder/'RAW.json')],str(r),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2));assert result['exit_code']==0 and result['group_drained'];raw=json.loads((folder/'RAW.json').read_text());results.append({k:v for k,v in raw.items() if k!='seconds'})
    assert results[0]==results[1]==results[2];rows.append(dict(metric=metric,exact_parity=True))
(r/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,build=b),indent=2)+'\n');print(json.dumps(rows))
