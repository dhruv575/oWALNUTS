import json,subprocess,time,sys,hashlib
from runtime_v4 import environment
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args()
task_dir=Path(__file__).resolve().parent;CONFIG=Path(a.config).resolve();config_bytes=CONFIG.read_bytes();config_sha256=hashlib.sha256(config_bytes).hexdigest();c=json.loads(config_bytes);OUT=Path(a.out).resolve();OUT.mkdir();tick=time.perf_counter();records=[]
for order in ['AB','BA']:
 if hashlib.sha256(CONFIG.read_bytes()).hexdigest()!=config_sha256:raise ValueError('Config drift before process admission')
 cmd=[c['python'],str(Path(c['study'])/'hardware_control.py'),'--cpus','0','--record',str(OUT/('benchmark-'+order+'-hardware.json')),'--timeout',str(c['timeout_seconds']),'--',c['python'],str(task_dir/'benchmark_v4.py'),'--config',str(CONFIG),'--order',order,'--out',str(OUT/('benchmark-'+order+'.json'))]
 with (OUT/('benchmark-'+order+'-started.json')).open('x') as f:json.dump(dict(command=cmd,config_sha256=config_sha256,pythonpath=environment(c)['PYTHONPATH'],python_no_user_site=environment(c)['PYTHONNOUSERSITE']),f,indent=2)
 t=time.perf_counter()
 with (OUT/('benchmark-'+order+'-stdout.txt')).open('x') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=environment(c))
 config_unchanged=hashlib.sha256(CONFIG.read_bytes()).hexdigest()==config_sha256
 records.append(dict(order=order,returncode=result.returncode,seconds=time.perf_counter()-t,command=cmd,config_sha256=config_sha256,config_unchanged=config_unchanged))
 with (OUT/('benchmark-'+order+'-exit.json')).open('x') as f:json.dump(records[-1],f,indent=2)
 if result.returncode or not config_unchanged:break
with (OUT/'benchmark-execution.json').open('x') as f:json.dump(dict(records=records,total_seconds=time.perf_counter()-tick),f,indent=2)
sys.exit(records[-1]['returncode'] if records[-1]['config_unchanged'] else 2)
