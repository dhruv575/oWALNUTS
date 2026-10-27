"""Artifact-only evaluator. Execution requires separately reviewed frozen inputs."""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
import time
import traceback
import arviz as az
import numpy as np
import scipy
import numba
from scipy.special import logsumexp
from baselines import check_deadline, fit_t5, nig_ar1, ewma_t5, score_distribution
from predictive_density import evaluate_observation, EXACT_PATH, EXACT_SHA

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'pool_confirm_v1'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf8')
    temporary.replace(path)

def mcse(values):
    if np.ptp(values)==0:return 0.
    value=float(np.asarray(az.mcse(values,method='mean')).item())
    return value if math.isfinite(value) else None

def predictive(source,observation,deadline):
    path=SOURCE/source['file_relative_to_wp97']
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('Draw hash mismatch')
    draws=np.frombuffer(raw,dtype='<f4').reshape(source['shape'])
    draws=draws[source['kept_chains']]
    result=evaluate_observation(draws,observation,deadline=deadline)
    logg=result.pop('logpdf_by_chain_draw');u=result.pop('pit_by_chain_draw')
    scaled=result.pop('density_mcse')['scaled_density']
    density_error=mcse(scaled)
    result['precision']=dict(logpdf_mcse=None if density_error is None else density_error/float(scaled.mean()),
        pit_mcse=mcse(u),chain_logpdf=(logsumexp(logg,axis=1)-math.log(logg.shape[1])).tolist(),
        chain_pit=u.mean(axis=1).tolist(),method='ArviZ mean MCSE; descriptive only')
    return result

def origin(dataset,entry,y,initial,deadline,checkpoint=None):
    tick=entry['tick'];n=250+tick
    result=dict(dataset=dataset,tick=tick,next_label_index=n,observed_return=float(y[n]),arms=[])
    for source in entry['sources']:
        check_deadline(deadline)
        row=dict(arm=source['arm'],seed=source['seed'],source_sha256=source['sha256'])
        result['active_arm']=dict(arm=row['arm'],seed=row['seed'])
        if checkpoint is not None:atomic(checkpoint,result)
        try:row.update(status='ok',**predictive(source,y[n],deadline))
        except TimeoutError:raise
        except Exception as error:
            row.update(status='unavailable',error=type(error).__name__,reason=str(error))
            if hasattr(error,'diagnostics'):row['numerical']=error.diagnostics
        result['arms'].append(row)
        result.pop('active_arm',None)
        if checkpoint is not None:atomic(checkpoint,result)
    for name in ['nig_ar1','rolling_t5_mle','ewma_t5']:
        check_deadline(deadline)
        row=dict(arm=name,seed=None)
        result['active_arm']=dict(arm=name,seed=None)
        if checkpoint is not None:atomic(checkpoint,result)
        try:
            fit=(nig_ar1(y[:n]) if name=='nig_ar1' else
                 fit_t5(y[n-250:n],deadline) if name=='rolling_t5_mle' else ewma_t5(y[:n],initial))
            row['fit']=fit
            if fit.get('status','ok')!='ok':row['status']='unavailable'
            else:row.update(status='ok',**score_distribution(fit['location'],fit['scale'],fit['df'],y[n]))
        except TimeoutError:raise
        except Exception as error:row.update(status='unavailable',error=type(error).__name__,reason=str(error))
        result['arms'].append(row)
        result.pop('active_arm',None)
        if checkpoint is not None:atomic(checkpoint,result)
    result['complete']=len(result['arms'])==7 and all(r['status']=='ok' for r in result['arms'])
    check_deadline(deadline)
    return result

def run(mode,out):
    out=Path(out).resolve()
    environment=json.loads((HERE/'ENVIRONMENT.json').read_text())
    actual=dict(python=sys.version,executable=sys.executable,numpy=np.__version__,scipy=scipy.__version__,arviz=az.__version__,numba=numba.__version__)
    if any(environment[key]!=value for key,value in actual.items()):raise ValueError('Frozen runtime environment mismatch')
    inventory=json.loads((HERE/'ORIGIN-INVENTORY.json').read_text())
    binding={p.name:digest(p) for p in [HERE/'protocol.json',HERE/'ORIGIN-INVENTORY.json',
        HERE/'evaluate.py',HERE/'baselines.py',HERE/'predictive_density.py',HERE/'summarize.py',HERE/'ENVIRONMENT.json']}
    binding['exact_t5_snapshot.py']=digest(EXACT_PATH)
    if binding['exact_t5_snapshot.py']!=EXACT_SHA:raise ValueError('Exact CDF source hash mismatch')
    if mode=='preflight':
        out.mkdir(parents=True,exist_ok=False)
        state=dict(pid=os.getpid(),mode=mode,binding=binding,status='running',completed=[],completed_sha256={},initial_fits={})
        budget=120.
    else:
        state=json.loads((out/'preflight.json').read_text())
        if state['binding']!=binding or state['status']!='complete':raise ValueError('Preflight admission failed')
        for name in state['completed']:
            if digest(out/name)!=state['completed_sha256'][name]:raise ValueError('Preflight origin changed')
        budget=state['remaining_budget_seconds']
        if budget>1800:raise ValueError('Budget not demonstrated; full run forbidden')
        if (out/'full.json').exists():raise FileExistsError('Full run already attempted')
        state.update(pid=os.getpid(),mode=mode,status='running')
    started=time.monotonic();deadline=started+budget
    state['started_unix']=time.time();state['hard_seconds']=budget
    state_path=out/f'{mode}.json';atomic(state_path,state)
    try:
        streams={}
        for data in inventory['datasets']:
            path=SOURCE/data['data_file_relative_to_wp97']
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=data['data_sha256']:raise ValueError('Data hash mismatch')
            streams[data['dataset']]=(data,np.asarray(json.loads(raw)['y'],dtype=float))
            if mode=='preflight':state['initial_fits'][data['dataset']]=fit_t5(streams[data['dataset']][1][:250],deadline)
        ticks=[1] if mode=='preflight' else range(2,101)
        for tick in ticks:
            for dataset in ['sim','real']:
                check_deadline(deadline)
                data,y=streams[dataset]
                name=f'{dataset}-tick-{tick:03d}.json';path=out/name
                if path.exists():raise FileExistsError(name)
                result=origin(dataset,data['origins'][tick-1],y,state['initial_fits'][dataset],deadline,path)
                atomic(path,result);state['completed'].append(name)
                state['completed_sha256'][name]=digest(path);atomic(state_path,state)
        elapsed=time.monotonic()-started
        for name,expected in binding.items():
            path=EXACT_PATH if name=='exact_t5_snapshot.py' else HERE/name
            if digest(path)!=expected:raise ValueError('Stage source binding changed: '+name)
        for data in inventory['datasets']:
            if digest(SOURCE/data['data_file_relative_to_wp97'])!=data['data_sha256']:
                raise ValueError('Stage data binding changed')
            for entry in data['origins']:
                name=f"{data['dataset']}-tick-{entry['tick']:03d}.json"
                if name not in state['completed']:continue
                for source in entry['sources']:
                    check_deadline(deadline)
                    if digest(SOURCE/source['file_relative_to_wp97'])!=source['sha256']:
                        raise ValueError('Stage draw binding changed')
        elapsed=time.monotonic()-started
        state['status']='complete'
        if mode=='preflight':
            valid=all(json.loads((out/name).read_text())['complete'] for name in state['completed'])
            state['remaining_budget_seconds']=max(300,math.ceil(1.5*99*elapsed+120))
            if not valid:state['status']='numerical_or_schema_failure'
    except BaseException as error:
        state.update(status='failed',error=type(error).__name__,reason=str(error),traceback=traceback.format_exc())
        raise
    finally:
        state.update(ended_unix=time.time(),elapsed_seconds=time.monotonic()-started)
        atomic(state_path,state)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['preflight','full']);parser.add_argument('--out',required=True)
    args=parser.parse_args();run(args.mode,args.out)
