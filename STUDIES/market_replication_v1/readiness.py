"""Fixed E61 literal engineering replay on April calendar, no market data."""
import argparse,json,time,subprocess
from pathlib import Path
import numpy as np
from worker import admit,exclusive,month_spec,terminal_accounting,batch_summary
from reuse import calendar
from data_contract import MONTHS

def literal_returns(n):return np.resize(np.array([.001,-.004,.003,.002,-.0005,.0007,-.0022,.0015],dtype=float),n+251)

def run(stage,manifest,root):
    spec=admit(manifest,expected_status='development_authorized');root=Path(root);root.mkdir(parents=True,exist_ok=True)
    begin=root/f'readiness-{stage}-start.json';final=root/f'readiness-{stage}-final.json'
    if begin.exists() or final.exists():raise FileExistsError('No readiness retry')
    started=time.monotonic();state=dict(stage=stage,status='running',scope='Fixed E61 literal and deliberately reused development seeds; no market data')
    exclusive(begin,state);month='2026-04';selected=month_spec(spec,month);m=calendar(month,spec['e62_root']);panel=root/month;panel.mkdir(exist_ok=True);y=literal_returns(selected['origins'])
    try:
        if stage=='candidate':
            subprocess.run([spec['python'],'-m','unittest','discover','-s',spec['ops_root'],'-p','test_*.py','-v'],check=True,timeout=45)
            state['ops_fixture_preflight']='passed'
            result=m['worker'].candidate(selected,y,panel,updates=32)
            if result['status']!='complete' or result['native_completed']!=32 or result['score_counts']['ok']!=32:raise ValueError('Literal candidate incomplete')
        elif stage=='baselines':
            result=m['baseline'].run(y,panel/'baselines',deadline=started+90,planned_ticks=32,development=True)
            for arm in ['rolling_t5','ewma_t5']:
                if any(json.loads((panel/'baselines'/arm/f'tick-{tick:04d}.json').read_bytes())['status']!='ok' for tick in range(1,33)):raise ValueError('Literal baseline unavailable')
        elif stage=='reference':
            result=m['reference'].run(selected,y,panel,0)
            if result['status']!='complete' or (result.get('candidate_precision')or{}).get('status')!='available':raise ValueError('Literal reference incomplete')
            state['reference_diagnostics_pass']=result['reference_diagnostics_pass']
        elif stage=='report':
            jobs=[dict(phase=p,index=i,status='not_started') for p,count in [('candidate',1),('baselines',1),('reference',8),('report',1)] for i in range(count)]
            for row in MONTHS:
                modules=calendar(row['month'],spec['e62_root']);folder=root/row['month'];folder.mkdir(exist_ok=True);n=row['origins']
                rows=modules['ledger'].build(folder)
                starts=lambda length,count:np.zeros((count,int(np.ceil(n/length))),dtype=int)
                summary=modules['report'].summarize(rows,replicates=2,seed=17,starts_provider=starts);summary['month']=row['month']
                expected={'ok':32,'not_started':n-32} if row['month']=='2026-04' else {'not_started':n}
                if summary['status_counts']!={a:expected for a in ['candidate','rolling_t5','ewma_t5']}:raise ValueError('Literal full-calendar denominator mismatch')
                if any(v['full_mean']is not None for v in summary['paired'].values()):raise ValueError('Incomplete literal panel got full mean')
                exclusive(folder/'summary.json',summary);validation=terminal_accounting(spec,row['month'],folder,jobs)
                if not validation['accounting_complete'] or validation['execution_complete']:raise ValueError('Literal terminal accounting mismatch')
            result=batch_summary(spec,root)
            if any(v['full_origin_weighted_mean']is not None for v in result['paired'].values()):raise ValueError('Incomplete aggregate falsely available')
        else:raise ValueError('Unknown literal stage')
        admit(manifest,expected_status='development_authorized');state['status']='complete'
    except Exception as error:state.update(status='failed',error=repr(error))
    state['elapsed_seconds']=time.monotonic()-started;exclusive(final,state);return state

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['candidate','baselines','reference','report']);parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    result=run(args.stage,args.manifest,args.out);raise SystemExit(0 if result['status']=='complete' else 1)
