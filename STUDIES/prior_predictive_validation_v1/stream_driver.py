"""Failure-preserving orchestration, dependency injected; never runs on import."""
import time
import numpy as np
from generator import tick_inputs

def run_stream(data,engine_factory,evaluator,oracle,persist):
    """Evaluator contract: evaluate(compact,label)->finite cdf/logpdf plus diagnostics.
    Oracle receives only true parameters and CURRENT latent, never future latent.
    persist must durably save records/draws before proceeding; no retries.
    """
    result=dict(stream=data['stream'],planned_ticks=32,status='running',rows=[],phase='initial_fit',in_progress=None)
    engine=None;persist(result,None)
    try:
        engine=engine_factory(np.asarray(data['y'])[:250].copy(),data['seeds'])
        if isinstance(getattr(engine,'initial',None),dict):result['initial_fit']=engine.initial
        persist(result,None)
        for tick in range(1,33):
            inputs=tick_inputs(data,tick);result.update(phase='refresh',in_progress=tick);persist(result,None)
            start=time.perf_counter();row=dict(tick=tick,status='failed',candidate_status='pending',oracle_status='not_started',phase='refresh',current_index=inputs['current_index'],label_index=inputs['label_index'])
            result['rows'].append(row);draws=None
            try:
                draws,telemetry=engine.advance(inputs['observation'],400)
                a=np.asarray(draws)
                if a.shape!=(4,400,4) or not np.isfinite(a).all():raise ValueError('invalid joint compact draw shape/finiteness')
                row['native']=telemetry;row['phase']='evaluate';t=time.perf_counter()
                score=evaluator(a,inputs['label'])
                if not np.isfinite([score['cdf'],score['logpdf']]).all() or not 0<=score['cdf']<=1:raise ValueError('nonfinite/out-of-range predictive score')
                row['forecast']=score;row['candidate_status']='ok';row['evaluation_seconds']=time.perf_counter()-t
                # Direct candidate cost excludes privileged-oracle scoring and persistence.
                row['candidate_total_seconds']=time.perf_counter()-start
                row['phase']='oracle';t=time.perf_counter()
                try:
                    privileged=oracle(data['parameters'].copy(),inputs['current_latent'],inputs['label'])
                    if not np.isfinite([privileged['cdf'],privileged['logpdf']]).all() or not 0<=privileged['cdf']<=1:raise ValueError('invalid oracle output')
                    row.update(oracle=privileged,oracle_status='ok',status='ok')
                except Exception as exc:
                    row.update(oracle_status='unavailable',oracle_error=repr(exc),status='partial')
                row.update(oracle_seconds=time.perf_counter()-t,phase='complete')
            except Exception as exc:
                row.update(candidate_status='unavailable',error=repr(exc),elapsed_to_failure_seconds=time.perf_counter()-start)
                raise
            finally:
                result['in_progress']=None;persist(result,draws)
        result['status']='complete' if all(r['status']=='ok' for r in result['rows']) else 'partial'
    except Exception as exc:
        result.update(status='failed',error=repr(exc))
        if hasattr(exc,'payload'):result['failure_payload']=exc.payload
    finally:
        if engine is not None:
            try:engine.close()
            except Exception as exc:result.update(status='failed',close_error=repr(exc))
        attempted={r['tick'] for r in result['rows']}
        result['unattempted_ticks']=[i for i in range(1,33) if i not in attempted]
        result['valid_ticks']=sum(x.get('candidate_status')=='ok' for x in result['rows'])
        result['oracle_valid_ticks']=sum(x.get('oracle_status')=='ok' for x in result['rows']);persist(result,None)
    return result
