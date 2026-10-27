"""Fixed E61 literal engineering replay; never loads quarantined August data."""
import argparse,json,time
from pathlib import Path
import numpy as np
from worker import admit,candidate
from linear_runner_snapshot import exclusive
from run_baselines import run as baselines
from run_reference import run as reference
from ledger import build,validate_artifacts,references
from report import summarize,N

def literal_returns():
    return np.resize(np.array([.001,-.004,.003,.002,-.0005,.0007,-.0022,.0015],dtype=np.float64),1739)

def run(stage,manifest,root):
    spec=admit(manifest,expected_status='development_authorized');root=Path(root);root.mkdir(parents=True,exist_ok=True)
    begin=root/f'readiness-{stage}-start.json';final=root/f'readiness-{stage}-final.json'
    if begin.exists() or final.exists():raise FileExistsError('No readiness retry')
    started=time.monotonic();state=dict(stage=stage,status='running',scope='Fixed literal engineering replay, no August values or fresh scientific seeds')
    exclusive(begin,state)
    try:
        if stage=='candidate':
            result=candidate(spec,literal_returns(),root,updates=32)
            if result['status']!='complete' or result['native_completed']!=32 or result['score_counts']['ok']!=32:raise ValueError('Literal candidate incomplete')
        elif stage=='baselines':
            result=baselines(literal_returns(),root/'baselines',deadline=started+90,planned_ticks=32,development=True)
            for arm in ['rolling_t5','ewma_t5']:
                if any(json.loads((root/'baselines'/arm/f'tick-{tick:04d}.json').read_bytes())['status']!='ok' for tick in range(1,33)):raise ValueError('Literal baseline unavailable')
        elif stage=='reference':
            result=reference(spec,literal_returns(),root,0)
            if result['status']!='complete' or result.get('candidate_precision',{}).get('status')!='available':raise ValueError('Literal reference incomplete')
            state['reference_diagnostics_pass']=result['reference_diagnostics_pass']
        elif stage=='report':
            rows=build(root)
            fixed_starts=lambda length,count:np.zeros((count,int(np.ceil(N/length))),dtype=int)
            result=summarize(rows,replicates=2,seed=17,starts_provider=fixed_starts)
            if result['status_counts']!={arm:{'ok':32,'not_started':1456} for arm in ['candidate','rolling_t5','ewma_t5']}:raise ValueError('Literal ledger denominator mismatch')
            if any(result['paired'][name]['full_mean']is not None for name in result['paired']):raise ValueError('Missing-panel full mean falsely available')
            integrity=validate_artifacts(root)
            if not integrity['integrity_ok']:raise ValueError('Literal artifact integrity')
            exclusive(root/'literal-summary.json',result);exclusive(root/'literal-integrity.json',integrity)
        else:raise ValueError('Unknown literal stage')
        admit(manifest,expected_status='development_authorized');state['status']='complete'
    except Exception as error:state.update(status='failed',error=repr(error))
    state['elapsed_seconds']=time.monotonic()-started;exclusive(final,state);return state

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['candidate','baselines','reference','report']);parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    result=run(args.stage,args.manifest,args.out);raise SystemExit(0 if result['status']=='complete' else 1)
