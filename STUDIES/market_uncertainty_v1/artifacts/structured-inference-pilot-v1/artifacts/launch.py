import json,hashlib,subprocess,sys,os,time,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[2];folder=Path(__file__).resolve().parent;out=folder/'experiment-v1';out.mkdir();python=str(Path(sys.executable).resolve());study=root/'STUDIES/options_flow_v1';package=root/'target/python-flow-worktree/integrations/python/python'
paths=[*folder.glob('*.py'),study/'hardware_control.py',study/'reference_bank_allocation.py',package/'owalnuts/__init__.py',package/'owalnuts/_owalnuts.pyd'];bindings={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};config=dict(scope='Exploratory synthetic algorithm route, not market validation or oWALNUTS speed qualification',periods=512,missing_fraction=.2,chains=4,warmup=1000,draws=4000,arms=['gibbs','numpyro','numpyro-nc','owalnuts'],timeout_per_arm=180,memory_bytes=8*1024**3,bindings=bindings,development_seeds=dict(data=29,gibbs_chains=[4101,4102,4103,4104],hmc_warmup=4101,numpyro_retained=4111,predictive=131111))
(out/'config.json').write_text(json.dumps(config,indent=2))
with zipfile.ZipFile(out/'source.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
 for i,p in enumerate(paths):z.write(p,f'{i:03d}-'+p.name)
records=[];start=time.perf_counter()
for arm in config['arms']:
 command=[python,str(study/'hardware_control.py'),'--cpus','0','--record',str(out/(arm+'-hardware.json')),'--timeout','180','--',python,str(folder/'run.py'),'--arm',arm,'--out',str(out/arm)]
 tick=time.perf_counter()
 with (out/(arm+'.log')).open('x') as log:rc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONPATH=str(package),PYTHONNOUSERSITE='1')).returncode
 row=dict(arm=arm,returncode=rc,outer_seconds=time.perf_counter()-tick,command=command);records.append(row);print(json.dumps(row),flush=True)
 (out/(arm+'-exit.json')).write_text(json.dumps(row,indent=2))
 if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in bindings.items()):raise ValueError('Bound source/runtime changed during experiment')
(out/'execution.json').write_text(json.dumps(dict(arms=records,total_seconds=time.perf_counter()-start),indent=2))
