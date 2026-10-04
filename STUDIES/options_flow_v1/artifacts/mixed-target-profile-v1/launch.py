import json,subprocess,sys,time,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent;config=json.loads((OUT/'config.json').read_text());tick=time.perf_counter();records=[]
for mode in ('profile','parity'):
 command=[config['python'],str(Path(config['study'])/'hardware_control.py'),'--cpus','0','--record',str(OUT/(mode+'-hardware.json')),'--timeout',str(config['timeout_seconds']),'--',config['python'],str(OUT/'profile.py'),'--config',str(OUT/'config.json'),'--mode',mode,'--out',str(OUT/(mode+'-result.json'))]
 if mode=='parity':command+=['--profile',str(OUT/'profile-result.json')]
 with (OUT/(mode+'-started.json')).open('x') as f:json.dump(dict(command=command,config_sha256=hashlib.sha256((OUT/'config.json').read_bytes()).hexdigest()),f,indent=2)
 start=time.perf_counter()
 with (OUT/(mode+'-stdout.txt')).open('x') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
 record=dict(mode=mode,returncode=r.returncode,seconds=time.perf_counter()-start,command=command);records.append(record)
 with (OUT/(mode+'-exit.json')).open('x') as f:json.dump(record,f,indent=2)
 if r.returncode:break
with (OUT/'execution.json').open('x') as f:json.dump(dict(records=records,total_seconds=time.perf_counter()-tick),f,indent=2)
sys.exit(records[-1]['returncode'])
