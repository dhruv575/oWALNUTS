"""Supplemental accounting of existing native diagnostics; no exclusions or new gates."""
import argparse,collections,json
from pathlib import Path
import numpy as np

def summarize(root):
 root=Path(root);warm=collections.Counter();initial=collections.Counter();discarded=collections.Counter();warning_counts=collections.Counter();warnings=[];guard_checks=0;restarts=[];stop_counts=collections.Counter();observed=0;array_divergences=0
 for stream in range(32):
  p=root/f'stream-{stream:02d}'/'candidate.json'
  if not p.exists():continue
  d=json.loads(p.read_text());fit=d.get('initial_fit') or {}
  for warning in fit.get('chain_warnings',[]):warning_counts[warning['check']]+=1;warnings.append(dict(stream=stream,**warning))
  for chain,c in enumerate(fit.get('chains',[])):
   initial.update(c.get('work_retained',{}));discarded.update(c.get('work_discarded',{}))
   for check in c.get('trapped_chain_checks',[]):
    guard_checks+=1
    if check['restarted']:restarts.append(dict(stream=stream,chain=chain,**{k:check[k] for k in ('transition','replacement_seed','abandoned_target_calls')}))
  for row in d.get('rows',[]):
   native=row.get('native') or {}
   for work in native.get('work',[]):warm.update(work)
   entry=row.get('score_arrays')
   if not entry:continue
   with np.load(p.parent/entry['file'],allow_pickle=False) as arrays:
    for chain in range(4):
     prefix=f'row__native__diagnostics__{chain}__';key=prefix+'divergent'
     if key not in arrays:continue
     divergences=arrays[key];stops=arrays[prefix+'stop'];observed+=len(divergences);array_divergences+=int(divergences.sum());stop_counts.update(map(int,stops))
 return dict(scope='Supplemental existing-telemetry audit; no dropped chains/rows, no new qualification gate',planned_warm_transitions=32*32*4*400,observed_warm_transitions=observed,warm_work=dict(warm),warm_divergences_from_arrays=array_divergences,work_arrays_agree=(observed==warm['transitions'] and array_divergences==warm['divergences']),stop_codes={str(k):v for k,v in sorted(stop_counts.items())},stop_labels={'0':'OuterUTurn','1':'RecursiveUTurn','2':'MaximumDepth','3':'RefinementExhausted','4':'ReverseCoarserAccepted','5':'InvalidEvaluation','255':'Other'},initial_retained_work=dict(initial),initial_discarded_warmup_work=dict(discarded),initial_warning_categories=dict(warning_counts),initial_warnings=warnings,initial_guard_checks=guard_checks,initial_guard_restarts=restarts,limitations=['Finite forecasts are not a substitute for MCMC diagnostics.','Guard restarts are the frozen declared initialization algorithm; no ad hoc reruns occurred.','These32-update streams do not resolve WP96 long-horizon drift/re-adaptation failures.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('campaign');p.add_argument('output');a=p.parse_args();d=summarize(a.campaign)
 with Path(a.output).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
