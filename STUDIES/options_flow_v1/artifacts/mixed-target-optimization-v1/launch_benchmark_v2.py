import json,subprocess,time,sys
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args()
HOME=Path(__file__).resolve().parent;CONFIG=Path(a.config).resolve();c=json.loads(CONFIG.read_text());OUT=Path(a.out).resolve();OUT.mkdir();tick=time.perf_counter();records=[]
for order in ['AB','BA']:
 cmd=[c['python'],str(Path(c['study'])/'hardware_control.py'),'--cpus','0','--record',str(OUT/('benchmark-'+order+'-hardware.json')),'--timeout',str(c['timeout_seconds']),'--',c['python'],str(HOME/'benchmark.py'),'--config',str(CONFIG),'--order',order,'--out',str(OUT/('benchmark-'+order+'.json'))]
 with (OUT/('benchmark-'+order+'-started.json')).open('x') as f:json.dump(dict(command=cmd),f,indent=2)
 t=time.perf_counter()
 with (OUT/('benchmark-'+order+'-stdout.txt')).open('x') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 records.append(dict(order=order,returncode=result.returncode,seconds=time.perf_counter()-t,command=cmd))
 with (OUT/('benchmark-'+order+'-exit.json')).open('x') as f:json.dump(records[-1],f,indent=2)
 if result.returncode:break
with (OUT/'benchmark-execution.json').open('x') as f:json.dump(dict(records=records,total_seconds=time.perf_counter()-tick),f,indent=2)
sys.exit(records[-1]['returncode'])
