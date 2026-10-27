"""Independent causal baseline phase; one immutable row per arm/origin."""
import json,math,time
from pathlib import Path
import numpy as np
from baselines_snapshot import fit_t5,score_distribution,check_deadline,FLOOR
from data_contract import inputs,ORIGINS

def save(path,value):
    with Path(path).open('x',encoding='utf8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n')

def ewma_step(variance,observation,initial):
    variance=.94*variance+.06*(observation-initial['location'])**2
    scale=float(np.sqrt(3*variance/5))
    return variance,dict(status='ok',location=initial['location'],scale=max(FLOOR,scale),df=5,
        variance=variance,floor_hit=scale<FLOOR)

def run(y,out,deadline=None,fit_function=fit_t5,planned_ticks=ORIGINS,development=False):
    """Production uses1488; shorter supplied counts are deterministic fixtures only."""
    if planned_ticks!=ORIGINS and fit_function is fit_t5 and not (development and planned_ticks==32):raise ValueError('Production panel cannot shrink')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    for arm in ['rolling_t5','ewma_t5']:(out/arm).mkdir()
    (out/'started').mkdir()
    started=time.monotonic();state=dict(status='running',planned_origins=ORIGINS,completed_ticks=0)
    save(out/'start.json',dict(state,started_unix=time.time()))
    initial=None;variance=None
    try:
        check_deadline(deadline);t=time.perf_counter()
        try:initial=fit_function(np.asarray(y[:250]).copy(),deadline)
        except TimeoutError:raise
        except Exception as error:initial=dict(status='unavailable',error=type(error).__name__,reason=str(error))
        save(out/'ewma-initial-fit.json',dict(fit=initial,seconds=time.perf_counter()-t))
        if initial['status']=='ok':variance=(5/3)*initial['scale']**2
        for tick in range(1,planned_ticks+1):
            check_deadline(deadline);v=inputs(y,tick)
            for arm in ['rolling_t5','ewma_t5']:
                row=dict(tick=tick,arm=arm,origin_ms=v['origin_ms'],label_available_ms=v['label_available_ms'],status='unavailable')
                save(out/'started'/f'{arm}-tick-{tick:04d}.json',dict(tick=tick,arm=arm,started_unix=time.time()))
                t=time.perf_counter()
                try:
                    if arm=='rolling_t5':fit=fit_function(v['window'].copy(),deadline)
                    elif variance is None:fit=dict(status='unavailable',reason='initial fit unavailable')
                    else:variance,fit=ewma_step(variance,v['observation'],initial)
                    row['fit_seconds']=time.perf_counter()-t
                    row['fit']=fit
                    if fit['status']=='ok':
                        score_start=time.perf_counter()
                        try:row.update(status='ok',**score_distribution(fit['location'],fit['scale'],fit['df'],v['label']))
                        finally:row['score_seconds']=time.perf_counter()-score_start
                except TimeoutError:raise
                except Exception as error:row.update(status='unavailable',error=type(error).__name__,reason=str(error))
                row['forecast_seconds']=time.perf_counter()-t
                save(out/arm/f'tick-{tick:04d}.json',row)
            state['completed_ticks']=tick
        state['status']='complete'
    except BaseException as error:
        state.update(status='failed',error=type(error).__name__,reason=str(error));raise
    finally:
        state.update(elapsed_seconds=time.monotonic()-started,ended_unix=time.time())
        save(out/'final.json',state)
    return state
