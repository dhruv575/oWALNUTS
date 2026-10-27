"""Development-only literal stage entry. Never calls the study generator."""
import argparse,json,math,time
from pathlib import Path
import numpy as np
from evidence import atomic
import worker

def literal_data():
 return dict(stream=0,parameters=dict(mu=2*math.log(.005),log_sigma=math.log(.2),beta=0.),seeds=dict(data=None,initial=993711000,warm=993712000),y=np.resize(np.array([.001,-.004,.003,.002,-.0005,.0007,-.0022,.0015],dtype=np.float64),283),h=np.full(283,2*math.log(.005),dtype=np.float64))

def run(stage,manifest,root):
 spec=worker.admit(manifest,stage,expected_status='development_authorized');root=Path(root);record=root/('readiness-'+stage+'.json')
 if record.exists():raise FileExistsError('No readiness retries')
 started=time.monotonic();result=dict(stage=stage,status='running',scope='literal development fixture, never calibration evidence')
 atomic(record,result)
 try:
  if stage=='candidate':out=worker.candidate(spec,root,0,data_override=literal_data())
  elif stage=='sides':out=worker.sides(spec,root,0)
  elif stage=='reference':out=worker.reference(spec,root,0,sample_seed_override=993713000)
  else:raise ValueError('Unknown stage')
  if out['status']!='complete':raise ValueError('Literal worker did not complete: '+str(out))
  if stage=='candidate':
   r=json.loads((root/'stream-00/candidate.json').read_text())
   if r['valid_ticks']!=32 or len(r['rows'])!=32:raise ValueError('Candidate denominator')
  elif stage=='sides':
   r=json.loads((root/'stream-00/side.json').read_text())
   if len(r['rows'])!=32 or not all(row[a+'_status']=='ok' for row in r['rows'] for a in ('baseline','oracle')):raise ValueError('Side denominator')
  else:
   r=json.loads((root/'sentinel-00/reference.json').read_text())
   if (r.get('candidate_precision') or {}).get('status')!='available':raise ValueError('Candidate MCSE unavailable')
   if r.get('candidate_integrity_error'):raise ValueError('Candidate arrays integrity')
   result['reference_diagnostics_pass']=r['reference_diagnostics_pass']
  worker.admit(manifest,stage,expected_status='development_authorized');result.update(status='complete',postrun_bindings_match=True)
 except Exception as exc:result.update(status='failed',error=repr(exc))
 finally:result['elapsed_seconds']=time.monotonic()-started;atomic(record,result)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['candidate','sides','reference']);p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args();r=run(a.stage,a.manifest,a.out);raise SystemExit(0 if r['status']=='complete' else 1)
