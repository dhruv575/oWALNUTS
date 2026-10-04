"""Recompute descriptive summaries from every saved block; no target execution."""
import argparse,hashlib,json,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=a.directory
s=dict(qualified=False,scope='Corrected-runtime target-only experiment; no MCMC or workflow claim',processes={});blocks=[];ratios=[]
for order in ['AB','BA']:
 path=r/f'benchmark-{order}.json';x=json.loads(path.read_text());b=x['blocks'];blocks+=b
 paired=[next(z['seconds_per_call'] for z in b if z['block']==i and z['implementation']=='baseline')/next(z['seconds_per_call'] for z in b if z['block']==i and z['implementation']=='candidate') for i in range(6)];ratios+=paired
 s['processes'][order]=dict(compile_seconds=x['compile_seconds'],median_microseconds={n:statistics.median(z['seconds_per_call'] for z in b if z['implementation']==n)*1e6 for n in ['baseline','candidate']},paired_ratios=paired,median_paired_ratio=statistics.median(paired),checks=len(x['checks']),max_value_error=max(z['value_error'] for z in x['checks']),max_gradient_error=max(z['gradient_max_error'] for z in x['checks']),runtime=x['runtime'],result_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
s.update(pooled_median_microseconds={n:statistics.median(z['seconds_per_call'] for z in blocks if z['implementation']==n)*1e6 for n in ['baseline','candidate']},pooled_median_paired_ratio=statistics.median(ratios),paired_ratio_range=[min(ratios),max(ratios)],all_blocks=len(blocks),all_target_calls=sum(z['calls'] for z in blocks),execution=json.loads((r/'benchmark-execution.json').read_text()))
with a.out.open('x') as f:json.dump(s,f,indent=2)
