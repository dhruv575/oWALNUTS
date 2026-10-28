"""Fixed literal engineering replay, including four concurrent full references."""
import argparse,json,shutil,time
from pathlib import Path
import numpy as np
from worker import admit,exclusive,inference,seal_inference,tail_spec,terminal_accounting,batch_summary
from data_contract import MONTHS
def literal_returns(n):return np.resize(np.array([.001,-.004,.003,.002,-.0005,.0007,-.0022,.0015]),n+251)
def run(stage,manifest,out,slot=0):
    spec=admit(manifest,expected_status='development_authorized');out=Path(out);out.mkdir(parents=True,exist_ok=True);month=MONTHS[0]['month'];y=literal_returns(MONTHS[0]['origins']);root=out/'literal';name=stage+(f'-{slot:02d}' if stage=='reference' else '')
    started=time.monotonic();state=dict(stage=stage,slot=slot,status='running',scope='Reused development seeds and fixed literals; no new market values')
    exclusive(out/f'{name}-start.json',state)
    try:
        if stage in ('native','baselines'):
            result=inference(spec,stage,month,0,root,y=y,updates=32)
            if result['status']!='complete':raise ValueError('Literal inference failed')
            if stage=='native' and (result['result']['native_completed']!=32 or result['result']['score_counts']['ok']!=32):raise ValueError('Literal native count mismatch')
            if stage=='baselines':
                for arm in ('rolling_t5','ewma_t5'):
                    for t in range(1,33):
                        if json.loads((root/'inference'/month/'baselines'/arm/f'tick-{t:04d}.json').read_bytes())['status']!='ok':raise ValueError('Literal baseline failure')
            state['result']=result
        elif stage=='reference':
            if slot not in range(4):raise ValueError('Four fixed literal slots')
            replay=root if slot==0 else out/'reference-replays'/f'{slot:02d}'
            if slot:
                dest=replay/'inference'/month/'candidate';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(root/'inference'/month/'candidate',dest)
            result=inference(spec,'reference',month,0,replay,y=y)
            if result['status']!='complete' or (result['result'].get('candidate_precision')or{}).get('status')!='available':raise ValueError('Full literal reference failed')
            record=replay/'inference'/month/'references/00/reference.json';value=json.loads(record.read_bytes());draws=np.load(record.parent/value['compact']['file'],allow_pickle=False)
            if draws.shape!=(4,4000,4):raise ValueError('Full reference retained shape changed')
            state.update(reference_record=str(record),reference_shape=list(draws.shape),reference_diagnostics_pass=value['reference_diagnostics_pass'],compiler_captures=value['compiler_captures'])
        elif stage=='tails':
            from tail_inputs import Archive
            from tail_worker import startup,reference_row
            from tail_evaluator import tails,baseline,score
            state['seal']=seal_inference(spec,root);selected=tail_spec(spec,root);archive=Archive(selected);backend,density,state['startup_seconds']=startup(spec,reference=True)
            destination=root/'tails';candidate=archive.candidate(month,1);q=tails(candidate,backend,time.perf_counter()+spec['bounds']['origin_seconds']);q['risk']=score(q,float(y[251]));q['postprocess_seconds']=q['quantile_seconds'];row=dict(month=month,tick=1,label=float(y[251]),arms={'candidate':q})
            for arm in ('rolling_t5','ewma_t5'):
                begin=time.perf_counter();value=baseline(archive.baseline(month,1,arm));value['risk']=score(value,float(y[251]));value['postprocess_seconds']=time.perf_counter()-begin;row['arms'][arm]=value
            exclusive(destination/'rows'/month/'000001.json',row)
            reference=reference_row(archive,selected,backend,density,destination,month,0,1);exclusive(destination/'references'/month/'000001.json',reference)
            if reference['status']!='ok' or any(reference[k]['status']!='available' for k in ('candidate_precision','reference_precision')):raise ValueError('Shared-deadline literal tail pipeline unavailable')
            state.update(candidate_draws=1600,reference_draws=16000,reference_pipeline_seconds=reference['postprocess_seconds'],input_integrity=archive.verify_used())
        elif stage=='report':
            import tail_report
            for m in MONTHS:
                result=tail_report.run(spec,root/'tails',m['month'])
                if result['full_scientific_panel'] or any(v['mean_advantage']is not None for v in result['comparisons'].values()):raise ValueError('Partial literal panel falsely complete')
            terminal=terminal_accounting(spec,root,[]);aggregate=batch_summary(spec,root)
            if not terminal['accounting_complete'] or not terminal['artifact_integrity']['integrity_ok'] or aggregate['status']!='incomplete':raise ValueError('Calendar accounting failed')
            refs=[json.loads((out/f'reference-{i:02d}-final.json').read_bytes()) for i in range(4)]
            if any(v['status']!='complete' or v['reference_shape']!=[4,4000,4] for v in refs):raise ValueError('Four reference stages not complete')
            stages=[json.loads((out/f'{p}-final.json').read_bytes()) for p in ('native','baselines','tails')]
            if any(v['status']!='complete' for v in stages):raise ValueError('Required literal stages incomplete')
            state['readiness_summary']=dict(status='complete',native=32,references=4,reference_shape=[4,4000,4],candidate_tail_draws=1600,reference_tail_draws=16000,calendar_accounting=True)
        else:raise ValueError('Unknown stage')
        admit(manifest,expected_status='development_authorized');state['status']='complete'
        if 'readiness_summary'in state:exclusive(out/'readiness-final.json',state['readiness_summary'])
    except Exception as error:state.update(status='failed',error=repr(error))
    state['elapsed_seconds']=time.monotonic()-started;exclusive(out/f'{name}-final.json',state);return state
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['native','baselines','reference','tails','report']);p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);p.add_argument('--slot',type=int,default=0);a=p.parse_args();r=run(a.stage,a.manifest,a.out,a.slot);raise SystemExit(0 if r['status']=='complete' else 1)
