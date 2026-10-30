import hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'funnel_cross01';root.mkdir(exist_ok=False)
assert json.loads((local/'funnel_cross_test01/SUMMARY.json').read_text())['passed']
build=json.loads((local/'funnel_cross_build01/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
sys.path.insert(0,str(local/'inputs'));from resource_monitor import execute
paths=[Path(__file__),study/'FUNNEL-CROSS-PROTOCOL.md',study/'funnel_cross_runner/src/main.rs',study/'analyze_funnel_cross.py',study/'analyze_funnel_error_guard.py']
configs=[];settings=[]
for k in range(4):
    seed=941000001+k;default_path=local/f'funnel_error_guard01/centered-default-{seed}/RAW.json';paths.append(default_path)
    default=json.loads(default_path.read_text());starts=np.asarray(default['columns'])[:,:,-1].T.tolist()
    for pilot in ['default','permissive']:
        path=local/f'funnel_error_guard01/centered-{pilot}-{seed}/RAW.json';paths.append(path);raw=json.loads(path.read_text())
        chains=[]
        for i,c in enumerate(raw['chains_data']):
            assert c['final_step_size']==c['warmup_end_step_size'] and c['final_max_error']==(1 if pilot=='default' else 1000)
            mass=c['mass_diagonal'];assert len(mass)==10 and np.all(np.isfinite(mass)) and min(mass)>0
            chains.append(dict(start=starts[i],mass=mass,step_size=c['final_step_size'],seed=941100001+10*k+i))
            settings.append(dict(pilot_seed=seed,pilot=pilot,chain=i,step_size=c['final_step_size'],mass=mass))
        for error in [1.,1000.]:
            configs.append(dict(pilot_seed=seed,pilot=pilot,max_error=error,pilot_target_calls=raw['target_calls_total'],spec=dict(target='funnel',metric='diagonal',draws=22000,levels=8,max_error=error,chains=chains)))
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n');(root/'SETTINGS.json').write_text(json.dumps(settings,indent=2)+'\n')
rows=[]
for config in configs:
    assert shutil.disk_usage(root).free>1024**3
    folder=root/f"{config['pilot_seed']}-{config['pilot']}-E{config['max_error']}";folder.mkdir();inp=folder/'INPUT.json';inp.write_text(json.dumps(config['spec'])+'\n')
    r=execute([str(binary),str(inp),str(folder/'RAW.json')],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    row={k:v for k,v in config.items() if k!='spec'};row.update(folder=folder.name,completed=r['exit_code']==0 and r['group_drained']);rows.append(row)
    (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,inputs=hashes,unchanged=True,binary=build),indent=2)+'\n')
