import hashlib,json,os,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'momentum_pool_test02';r.mkdir(exist_ok=False)
sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
os.environ['PATH']='/home/dhruv/.cargo/bin:'+os.environ['PATH'];os.environ['CARGO_TARGET_DIR']='/home/dhruv/.cache/owalnuts/native-recycling01'
source=l/'momentum_pool_source01'
for label,cmd in [('lock',['cargo','+stable','generate-lockfile','--offline']),('library',['cargo','+stable','test','--release','--offline','--locked','--lib','-j','1'])]:
    result=execute(cmd,str(source),300,r,4*1024**3,64*1024**2,r/(label+'.log'),output_scan_interval=2);(r/(label+'-SUPERVISION.json')).write_text(json.dumps(result,indent=2));assert result['exit_code']==0 and result['group_drained'],label
build=json.loads((l/'momentum_pool_build01/SUMMARY.json').read_text());assert build['passed'];rows=[]
for b in build['rows']:
    assert hashlib.sha256(Path(b['binary']).read_bytes()).hexdigest()==b['binary_sha256']
for target,metric in [(t,m) for t in ['banana_direct','banana_latent'] for m in ['identity','diagonal']]+[('funnel','diagonal')]:
    old=l/'cold_recycling_test01'/f'{target}-{metric}-original';prior=json.loads((old/'RAW.json').read_text());spec=json.loads((old/'INPUT.json').read_text());spec['profile_allocations']=True
    for b in build['rows']:
        folder=r/f'{target}-{metric}-{b["package"]}';folder.mkdir();(folder/'INPUT.json').write_text(json.dumps(spec));result=execute([b['binary'],str(folder/'INPUT.json'),str(folder/'RAW.json')],str(r),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2));assert result['exit_code']==0 and result['group_drained'];data=json.loads((folder/'RAW.json').read_text());assert len(prior['chains'])==len(data['chains'])
        for a,c in zip(prior['chains'],data['chains']):
            for k in a:
                if k!='seconds':assert a[k]==c[k],(target,metric,k)
        row=dict(target=target,metric=metric,package=b['package'],exact_parity=True)
        if 'probe' in b['package']:
            before=json.loads((l/'allocation_audit01'/f'{target}-{metric}-True/RAW.json').read_text());counts=[c['allocation_counts'] for c in data['chains']];oldcounts=[c['allocation_counts'] for c in before['chains']]
            def events(c):return c['alloc']+c['alloc_zeroed']+c['realloc']
            assert all(sum(c['request_size_bins'])==events(c) for c in counts)
            row.update(events_before=sum(map(events,oldcounts)),events_after=sum(map(events,counts)),bytes_before=sum(c['requested_bytes'] for c in oldcounts),bytes_after=sum(c['requested_bytes'] for c in counts))
        rows.append(row);print(json.dumps(row),flush=True)
(r/'SUMMARY.json').write_text(json.dumps(dict(passed=True,rows=rows,build=build),indent=2)+'\n')
