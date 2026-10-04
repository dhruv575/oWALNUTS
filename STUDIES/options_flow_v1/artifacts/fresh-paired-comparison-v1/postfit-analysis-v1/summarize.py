import json,math,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent
r=json.loads((D/'decision-result.json').read_text());pin=json.loads((D/'analysis-pin.json').read_text());terminal=json.loads(Path(pin['terminal']).read_text());bp=json.loads(Path(pin['bank_pin']).read_text());bank=json.loads(Path(bp['bank']).read_text())
summary={'qualified':False,'reliability':r['reliability'],'runtime_ratio_point':r['reliability']['reference']['cost_per_success']/r['reliability']['public']['cost_per_success'],'runtime_ratio_interval':r['runtime_ratio_interval'],'speed_gate':r['speed_gate'],'cost_reconciliation':r['cost_reconciliation'],'accuracy':{},'checks':[],'reference_research_cost_seconds':{'fitting':15650.645,'analysis':2556.239},'limitations':r['limitations'],'unresolved_reasons':r['unresolved_reasons']}
for arm in ('public','reference'):
 rows=[x['normalized'] for x in terminal['outcomes'] if x['controller']['id'].endswith('-'+arm) and x['normalized']['outcome']=='usable']
 checks=r['accuracy'][arm]['checks'];summary['accuracy'][arm]={'pass_gate':r['accuracy'][arm]['pass_gate'],'endpoint_checks_passed':sum(x['pass_gate'] for x in checks.values()),'endpoints':len(checks)}
 for name,v in checks.items():
  b=bank['endpoints'][name];point=b.get('estimate',b.get('point'))
  errors=[(x['endpoints'][name]['estimate']-point)/b['W_low'] for x in rows] if point is not None else []
  summary['checks'].append(dict(arm=arm,endpoint=name,**v,mean_margin=min(v['mean_interval'][0]+.02,.02-v['mean_interval'][1]),rms_margin=.04-v['rms_upper'],observed_mean_error=sum(errors)/len(errors) if errors else None,observed_rms_error=math.sqrt(sum(x*x for x in errors)/len(errors)) if errors else None))
summary['inputs']={str(D/'decision-result.json'):hashlib.sha256((D/'decision-result.json').read_bytes()).hexdigest(),str(Path(pin['terminal'])):hashlib.sha256(Path(pin['terminal']).read_bytes()).hexdigest()}
with (D/'summary.json').open('x') as f:json.dump(summary,f,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in summary.items() if k not in ('checks','inputs')},indent=2))
print('MIN MARGINS',min(x['mean_margin'] for x in summary['checks']),min(x['rms_margin'] for x in summary['checks']))
