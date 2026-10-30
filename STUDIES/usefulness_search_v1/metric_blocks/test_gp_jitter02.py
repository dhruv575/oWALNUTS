import hashlib,json,sys,tomllib
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_jitter_test02';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
b=json.loads((l/'gp_jitter_build01/SUMMARY.json').read_text());assert b['passed'];bins=[b['rows'][0],json.loads((l/'gp_jitter_build02/SUMMARY.json').read_text())['rows'][0]]
for x in bins:assert hashlib.sha256(Path(x['binary']).read_bytes()).hexdigest()==x['binary_sha256']
def registry(name):return sorted((x['name'],x['version'],x.get('checksum')) for x in tomllib.loads((p/name/'Cargo.lock').read_text())['package'] if 'source' in x)
assert registry('gp_jitter_original_runner')==registry('gp_jitter_candidate02_runner')
base=json.loads((l/'gp_fresh_comparison01/walnuts_auto-946200001/INPUT.json').read_text());base.update(warmup=1100,draws=100,seed=947700001,target_accept=.9);rows=[]
for metric in ['diag','dense']:
    results=[]
    for label,index,amplitude in [('original',0,None),('omitted',1,None),('zero',1,0.),('jitter-a',1,.5),('jitter-b',1,.5)]:
        folder=r/f'{metric}-{label}';folder.mkdir();spec=dict(base,arm=metric);(folder/'INPUT.json').write_text(json.dumps(spec));command=['env','-u','OWALNUTS_RESEARCH_JITTER']
        if amplitude is not None:command.append('OWALNUTS_RESEARCH_JITTER='+str(amplitude))
        command += [bins[index]['binary'],str(folder/'INPUT.json'),str(folder/'RAW.json')]
        result=execute(command,str(r),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2));assert result['exit_code']==0 and result['group_drained'];raw=json.loads((folder/'RAW.json').read_text());results.append({k:v for k,v in raw.items() if k!='seconds'})
        for chain in raw['chain_details']:
            ds=chain['diagnostics'];base_step=chain['step_size'];assert sum(d['calls'] for d in ds)==chain['retained_calls'];assert len(ds)==100
            if amplitude:
                assert len(set(d['step'] for d in ds))>90;assert all(.5*base_step<=d['step']<=1.5*base_step for d in ds)
            else:assert all(d['step']==base_step for d in ds)
            assert all(abs(d['macro_length']-d['step']*d['leaves'])<1e-12 for d in ds)
    assert results[0]==results[1]==results[2];assert results[3]==results[4]
    for a,c in zip(results[0]['chain_details'],results[3]['chain_details']):assert a['step_size']==c['step_size'] and a['mass_updates']==c['mass_updates']
    rows.append(dict(metric=metric,exact_zero_parity=True,jitter_repeatability=True,base_tuning_unchanged=True));print(json.dumps(rows[-1]),flush=True)
(r/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,build=bins,source_hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['test_gp_jitter02.py','repair_gp_jitter.py','GP-JITTER-KERNEL-02.patch','GP-JITTER-PREFLIGHT-PROTOCOL.md']}),indent=2)+'\n')
