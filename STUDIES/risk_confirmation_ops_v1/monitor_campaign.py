"""Read-only remote operational pulse; no outcomes, scheduling changes or lifecycle calls."""
import argparse,base64,json,subprocess,time
from pathlib import Path
SCRIPT=r'''
from pathlib import Path
from datetime import datetime,timezone
import collections,json
r=Path('/home/ubuntu/lanes/risk-confirmation-20261027');b=r/'campaign01/batch'
out=dict(utc=datetime.now(timezone.utc).isoformat(),native_records={m:len(list((b/'inference'/m/'candidate/records').glob('*.json'))) for m in ('2025-12','2026-01','2026-02')},completed_reference_files=len(list((b/'inference').glob('*/references/*/reference.json'))),candidate_tail_rows=len(list((b/'tails/rows').glob('*/*.json'))),reference_tail_rows=len(list((b/'tails/references').glob('*/*.json'))),completed_monitors=len(list(b.glob('monitor-*.json'))),terminal=(r/'campaign01/BATCH-SUPERVISION.json').exists())
util=r/'campaign01/utilization.jsonl'
if util.exists():
 try:
  with util.open() as f:last=json.loads(collections.deque(f,maxlen=1)[0])
  out.update(phase=last['phase'],elapsed_seconds=last['elapsed_seconds'],reserved_cores=last['reserved_cores'],sampled_reserved_cpu_fraction=last['normalized_reserved_cpu_fraction'],owned_rss=sum(p['rss'] for p in last['processes']))
 except (ValueError,IndexError):out['utilization_pending']=True
if out['terminal']:
 v=json.loads((r/'campaign01/BATCH-SUPERVISION.json').read_bytes());out['terminal_flags']={k:v.get(k) for k in ('status','exit_code','group_drained','remaining_owned_pids','evidence_complete','execution_complete','elapsed_seconds','peak_rss','final_output_bytes','accounting_error')}
print(json.dumps(out))
'''

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ip',required=True);p.add_argument('--key',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    encoded=base64.b64encode(SCRIPT.encode()).decode();start=time.monotonic()
    with Path(a.out).open('x',encoding='utf-8') as log:
        while time.monotonic()-start<4500:
            try:
                raw=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','HostKeyAlias=18.188.57.71','-i',a.key,'ubuntu@'+a.ip,'echo '+encoded+' | base64 -d | python3 -'],timeout=25);v=json.loads(raw)
            except Exception as exc:v=dict(monitor_error=repr(exc),unix_seconds=time.time())
            line=json.dumps(v);log.write(line+'\n');log.flush();print(line,flush=True)
            if v.get('terminal'):break
            time.sleep(60)
