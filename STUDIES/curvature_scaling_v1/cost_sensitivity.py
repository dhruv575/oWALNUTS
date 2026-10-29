"""Conditional cost model only; this does not simulate an expensive likelihood."""
import json,statistics,sys
from pathlib import Path

def project(nuts,walnuts,extra):
    return (nuts['kernel']+extra*nuts['calls'])/(walnuts['kernel']+extra*walnuts['calls'])

def run(folder):
    folder=Path(folder);s=json.loads((folder/'SUMMARY.json').read_text())['5'];scenarios=[]
    for extra in [0,1e-7,5e-7,1e-6,5e-6,1e-5]:
        values=[project(n,w,extra) for n,w in zip(s['methods']['nuts']['ladders'],s['methods']['walnuts']['ladders']) if n['reached'] and w['reached']]
        scenarios.append(dict(hypothetical_extra_seconds_per_call=extra,median_nuts_over_walnuts=statistics.median(values),paired_ratios=values))
    result=dict(scope='Conditional additive-cost sensitivity, not measured expensive-likelihood performance. Assumes unchanged trajectories and identical extra time per target call for both engines. No real application claim. Selected case d24 b5 only.',case=5,scenarios=scenarios)
    (folder/'COST-SENSITIVITY.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())

if __name__=='__main__':run(sys.argv[1])
