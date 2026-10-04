"""Draft-only bank allocation planner and bounded analytic-control controller.

No posterior fits. Execution requires an externally reviewed frozen manifest.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def bindings(implementation='scalar'):
    names=['reference_bank_allocation.py','reference_bank.py','reference_bank_controls.py','hardware_control.py']
    if implementation=='vectorized':names.append('reference_bank_vectorized.py')
    return {n:sha(HERE/n) for n in names}
def versions():return {n:importlib.metadata.version(n) for n in ['numpy','scipy']}

def draft(reserved_seeds,seed=None,seed_audit=None,implementation='scalar',wall_seconds=None):
    if implementation not in ['scalar','vectorized']:raise ValueError('Unknown implementation')
    if wall_seconds is None:wall_seconds=2700 if implementation=='vectorized' else 1800
    if wall_seconds not in ([2700,3600] if implementation=='vectorized' else [1800]):raise ValueError('Explicit supported prospective resource budget required')
    if seed is None:seed=(1950000000 if wall_seconds==3600 else 1940000000) if implementation=='vectorized' else 1930000000
    cells=[];cursor=seed
    configurations=[('sentinel',16,2048,rho,shift,i) for i,(rho,shift) in enumerate([(0.,0.),(0.,.5),(.9,0.),(.9,.5)])]
    configurations += [('campaign',f,n,rho,shift,i) for f,n in [(8,4096),(16,2048),(32,1024)] for rho in [0.,.9] for shift in [0.,.1,.5] for i in range(8)]
    for phase,f,n,rho,shift,i in configurations:
        streams=list(range(cursor,cursor+4*f+1));cursor+=len(streams)
        cells.append(dict(id=f'{phase}-f{f}-n{n}-rho{rho}-shift{shift}-{i}',phase=phase,fits_per_backend=f,lengths=[n//2,n],rho=rho,backend_b_shift=shift,fit_seeds=streams[:2*f],init_seeds=streams[2*f:4*f],bootstrap_seed=streams[-1]))
    p=dict(frozen=False,qualified=False,phase='exploratory',cells=cells,reserved_seeds=sorted(reserved_seeds),seed_audit=seed_audit,implementation=implementation,source=bindings(implementation),software=versions(),python=sys.version,interpreter=dict(path=str(Path(sys.executable).resolve()),sha256=sha(sys.executable)),wall_seconds=wall_seconds,cleanup_reserve_seconds=15,memory_bytes=2*1024**3,bootstrap_replicates=30000,minimum_tail_count=20,alpha=.05,relative_half_width=.1,backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1)
    validate(p);return p

def validate(p):
    implementation=p.get('implementation','scalar')
    if implementation not in ['scalar','vectorized']:raise ValueError('Unknown implementation')
    if len(p['cells'])!=148 or len({c['id'] for c in p['cells']})!=148:raise ValueError('Require all 148 unique intended cells')
    if [c['phase'] for c in p['cells'][:4]]!=['sentinel']*4 or any(c['phase']!='campaign' for c in p['cells'][4:]):raise ValueError('Sentinels must precede campaign')
    actual=[(c['fits_per_backend'],c['lengths'],c['rho'],c['backend_b_shift']) for c in p['cells'][:4]]
    expected=[(16,[1024,2048],rho,shift) for rho,shift in [(0.,0.),(0.,.5),(.9,0.),(.9,.5)]]
    if actual!=expected:raise ValueError('Exact four sentinel configurations required')
    streams=[]
    for c in p['cells']:
        f=c['fits_per_backend'];n=c['lengths'][-1]
        if (f,n) not in [(8,4096),(16,2048),(32,1024)] or c['lengths']!=[n//2,n] or c['rho'] not in [0.,.9] or c['backend_b_shift'] not in [0.,.1,.5]:raise ValueError('Unsupported design')
        if len(c['fit_seeds'])!=2*f or len(c['init_seeds'])!=2*f:raise ValueError('Incomplete streams')
        streams+=c['fit_seeds']+c['init_seeds']+[c['bootstrap_seed']]
    if any(type(s)!=int or not 0<=s<2**32 for s in streams) or len(set(streams))!=len(streams) or set(streams)&set(p['reserved_seeds']):raise ValueError('Invalid or colliding streams')
    expected={(f,n,rho,shift):8 for f,n in [(8,4096),(16,2048),(32,1024)] for rho in [0.,.9] for shift in [0.,.1,.5]}
    for c in p['cells'][4:]:expected[(c['fits_per_backend'],c['lengths'][-1],c['rho'],c['backend_b_shift'])]-=1
    if any(expected.values()):raise ValueError('Incorrect allocation denominator')
    if type(p['wall_seconds'])!=int or p['wall_seconds'] not in ([2700,3600] if implementation=='vectorized' else [1800]):raise ValueError('Unsupported prospective wall budget')
    for k,v in dict(cleanup_reserve_seconds=15,memory_bytes=2*1024**3,bootstrap_replicates=30000,minimum_tail_count=20,alpha=.05,relative_half_width=.1,backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1).items():
        if p[k]!=v:raise ValueError('Unsupported prospective budget: '+k)

def projection(sentinels):
    if len(sentinels)!=4 or any(r['status']!='completed' for r in sentinels):return None
    # 2x safety, plus2x maximum fit-count or path-length scaling from balanced.
    return max(r['outer_seconds'] for r in sentinels)*144*4

def memory_limit(limit):
    if os.name!='nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(limit,limit));return None
    import ctypes
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):_fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',w.DWORD),('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class IO(ctypes.Structure):_fields_=[('v',ctypes.c_ulonglong*6)]
    class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    api=ctypes.WinDLL('kernel32',use_last_error=True);api.CreateJobObjectW.restype=w.HANDLE;api.GetCurrentProcess.restype=w.HANDLE
    api.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];api.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
    handle=api.CreateJobObjectW(None,None);info=Extended();info.basic.flags=0x100;info.process_memory=limit
    if not handle or not api.SetInformationJobObject(handle,9,ctypes.byref(info),ctypes.sizeof(info)) or not api.AssignProcessToJobObject(handle,api.GetCurrentProcess()):raise OSError('Cannot enforce process committed-memory cap')
    return handle # Keep handle alive until worker exits. No numerical imports yet.

def analyze_selected(plan,spec,fits):
    from reference_bank import analyze
    implementation=plan.get('implementation','scalar')
    if implementation=='scalar':return analyze(spec,fits)
    if implementation!='vectorized':raise ValueError('Unknown implementation')
    from reference_bank_vectorized import batch_cached_parameter
    return analyze(spec,fits,parameter_batch=batch_cached_parameter)

def cell_worker(p,c,out):
    cpu_started=time.process_time()
    guard=memory_limit(p['memory_bytes'])
    import numpy as np
    from scipy.signal import lfilter
    from scipy.stats import norm
    from reference_bank import analyze
    truth=norm.ppf([.05,.95]);width=float(truth[1]-truth[0]);fits=[];f=c['fits_per_backend']
    for i,seed in enumerate(c['fit_seeds']):
        rho=c['rho'];innov=np.random.default_rng(seed).normal(size=c['lengths'][-1])*np.sqrt(1-rho*rho)
        innov[0]=np.random.default_rng(c['init_seeds'][i]).normal();v=lfilter([1.],[1.,-rho],innov)+(c['backend_b_shift'] if i>=f else 0.)
        fit=dict(id=str(i),backend='a' if i<f else 'b',seed=seed,initialization_seed=c['init_seeds'][i],fixture_sha256='analytic-normal',source_sha256=p['source']['reference_bank.py'],target_sha256='normal-zero-one',levels={})
        for n in c['lengths']:
            dist=dict(scale='unit',distribution_id='theta',draws=v[:n].tolist())
            fit['levels'][str(n)]=dict(status='completed',healthy=True,draws_per_chain=n,endpoints={'lo':dist,'hi':dist})
        fits.append(fit)
    spec={k:p[k] for k in ['bootstrap_replicates','minimum_tail_count','alpha','relative_half_width','backend_equivalence_relative_width','length_equivalence_relative_width']}
    spec.update(lengths=c['lengths'],fits=[{k:v for k,v in f.items() if k!='levels'} for f in fits],chains=1,source_sha256=p['source']['reference_bank.py'],target_sha256='normal-zero-one',numerical_policy='validated_estimate',candidate_streams=[],bootstrap_seed=c['bootstrap_seed'],interval_pairs=[['lo','hi']],endpoints={n:dict(kind='parameter',distribution_id='theta',probability=q,scale='unit') for n,q in [('lo',.05),('hi',.95)]})
    analysis_started=time.perf_counter();bank=analyze_selected(p,spec,fits);analysis_seconds=time.perf_counter()-analysis_started
    if 'endpoints' not in bank:raise ValueError('No finite bank bounds: '+str(bank['reasons']))
    vectors=np.asarray([[r['lo'],r['hi']] for r in bank['joint_bootstrap_endpoints']]);shared=vectors-vectors.mean(axis=0)
    # Common reference perturbation reused across20 candidate comparisons.
    covariance=np.cov(shared.T)
    if not np.isfinite(covariance).all() or np.any(np.diag(covariance)<=0):raise ValueError('Degenerate/nonfinite shared reference uncertainty control')
    repeated=np.broadcast_to(shared[:,None,:],(len(shared),20,2)).mean(axis=1)
    if not np.allclose(np.cov(repeated.T),covariance,rtol=1e-12,atol=1e-15):raise ValueError('Shared reference covariance changed')
    bounds=[bank['endpoints'][n] for n in ['lo','hi']]
    save(out/'bank.json',bank);save(out/'result.json',dict(status='completed',cell=c,truth=truth.tolist(),bank_status=bank['status'],bank_reasons=bank['reasons'],both_endpoints_cover_truth=all(b['lower']<=t<=b['upper'] for b,t in zip(bounds,truth)),max_endpoint_error_over_width=max(abs(b['estimate']-t)/width for b,t in zip(bounds,truth)),shared_reference_covariance=covariance.tolist(),cpu_seconds_before_final_report=time.process_time()-cpu_started,bank_serialized_bytes=(out/'bank.json').stat().st_size,bank_analysis_seconds=analysis_seconds,analysis_seconds_per_bootstrap_including_setup=analysis_seconds/p['bootstrap_replicates'],bounds=bounds,qualified=False))

def verify_seed_audit(p):
    audit=p.get('seed_audit')
    if not audit or set(audit)!={'path','sha256'}:raise ValueError('Historical seed audit evidence required')
    path=Path(audit['path'])
    if sha(path)!=audit['sha256']:raise ValueError('Historical seed audit changed')
    evidence=json.loads(path.read_text())
    if evidence.get('status')!='complete' or not evidence.get('inventory_files') or evidence.get('reserved_seeds')!=p['reserved_seeds']:raise ValueError('Incomplete seed inventory audit')
    for filename,digest in evidence['inventory_files'].items():
        if sha(filename)!=digest:raise ValueError('Historical inventory file changed')
    # Evidence names its search scope; completeness remains an auditable claim,
    # never inferred from an arbitrary caller-provided list.
    if not evidence.get('search_scope') or not evidence.get('auditor'):raise ValueError('Seed audit scope/author required')

def run(path,out):
    path=Path(path);p=json.loads(path.read_text());validate(p);original=sha(path)
    if not p['frozen']:raise ValueError('Draft cannot execute')
    verify_seed_audit(p)
    def verify():
        verify_seed_audit(p)
        if sha(path)!=original or p['source']!=bindings(p.get('implementation','scalar')) or p['software']!=versions() or p['python']!=sys.version or p['interpreter']!={'path':str(Path(sys.executable).resolve()),'sha256':sha(sys.executable)}:raise ValueError('Frozen bindings changed')
    verify();out=Path(out);out.mkdir(parents=True,exist_ok=False);start=time.monotonic();rows=[];stop=None
    save(out/'expected.json',dict(plan_sha256=original,cells=p['cells']))
    for i,c in enumerate(p['cells']):
        remaining=p['wall_seconds']-(time.monotonic()-start)
        if i==4:
            projected=projection(rows);save(out/'projection.json',dict(projected_seconds=projected,remaining_seconds=remaining,includes_imports_serialization=True))
            if projected is None or projected>remaining-p['cleanup_reserve_seconds']:stop='sentinel_cost_or_failure'
        if remaining<=0:stop='wall_budget'
        row=dict(id=c['id'],status='not_started',reason=stop,outer_seconds=0.,plan_sha256=original)
        if not stop:
            cellout=out/c['id'];cellout.mkdir();tick=time.monotonic()
            save(cellout/'started.json',dict(cell=c,plan_sha256=original,started_unix=time.time(),remaining_wall_seconds=remaining))
            try:
                verify()
                from hardware_control import wrapper_command,get_affinity
                remaining=p['wall_seconds']-(time.monotonic()-start)
                if remaining<=p['cleanup_reserve_seconds']:stop='wall_budget';raise TimeoutError('No compute budget after reserving cleanup')
                command=[sys.executable,str(Path(__file__).resolve()),'--worker',str(path),'--cell',str(i),'--out',str(cellout)]
                wrapped=wrapper_command(command,[get_affinity()[0]],cellout/'hardware.json',timeout=remaining-p["cleanup_reserve_seconds"])
                with (cellout/'worker.log').open('w') as log:
                    finished=subprocess.run(wrapped,stdout=log,stderr=subprocess.STDOUT,check=False)
                row['worker_exit_code']=finished.returncode
                # Preserve exit evidence before any potentially failing postcheck.
                save(cellout/'worker-exit.json',dict(returncode=finished.returncode,exit_unix=time.time()))
                verify()
                if finished.returncode:raise RuntimeError('Contained worker exit '+str(finished.returncode))
                row.update(json.loads((cellout/'result.json').read_text()))
            except Exception as exc:
                row.update(status='failed',reason=f'{type(exc).__name__}: {exc}',worker_exit_code=row.get('worker_exit_code',getattr(exc,'returncode',None)))
                if isinstance(exc,ValueError):stop='binding_integrity_failure'
            if (cellout/'resources.json').exists():row['resources']=json.loads((cellout/'resources.json').read_text())
            else:row['resources']={'peak_committed_bytes':None,'reason':'Worker exited before resource record; never assume zero peak'} 
            row['outer_seconds']=time.monotonic()-tick
            save(cellout/'exit.json',dict(status=row['status'],reason=row.get('reason'),exit_unix=time.time(),worker_exit_code=row.get('worker_exit_code'),outer_seconds=row['outer_seconds']))
        rows.append(row);save(out/(c['id']+'.json'),row)
    integrity_error=None
    try:verify()
    except Exception as exc:integrity_error=str(exc)
    save(out/'summary.json',dict(compute_and_cleanup_budget_seconds=p['wall_seconds'],cleanup_reserve_seconds=p['cleanup_reserve_seconds'],timing_scope='Contained inner timeout reserves cleanup inside budget; no unsafe outer launcher kill. Scheduling and terminal bookkeeping may overrun, all charged.',integrity_error=integrity_error,expected=148,completed=sum(r['status']=='completed' for r in rows),failed=sum(r['status']=='failed' for r in rows),not_started=sum(r['status']=='not_started' for r in rows),rows=rows,total_seconds=time.monotonic()-start,qualified=False))

def peak_memory():
    if os.name!='nt':
        import resource
        return dict(peak_resident_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,peak_committed_bytes=None,measurement='POSIX peak RSS; committed peak unavailable',cap_kind='OS virtual-address-space limit')
    import ctypes
    from ctypes import wintypes as w
    class Counters(ctypes.Structure):
        _fields_=[('cb',w.DWORD),('faults',w.DWORD),('peak_ws',ctypes.c_size_t),('ws',ctypes.c_size_t),('peak_paged',ctypes.c_size_t),('paged',ctypes.c_size_t),('peak_nonpaged',ctypes.c_size_t),('nonpaged',ctypes.c_size_t),('pagefile',ctypes.c_size_t),('peak_pagefile',ctypes.c_size_t),('private',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=w.HANDLE
    api=ctypes.WinDLL('psapi',use_last_error=True);api.GetProcessMemoryInfo.argtypes=[w.HANDLE,ctypes.c_void_p,w.DWORD]
    info=Counters();info.cb=ctypes.sizeof(info)
    if not api.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(info),info.cb):raise ctypes.WinError(ctypes.get_last_error())
    return dict(peak_committed_bytes=info.peak_pagefile,peak_resident_bytes=info.peak_ws,measurement='Windows process peak pagefile/working set',cap_kind='OS process committed-memory limit')

def run_worker(p,c,out):
    try:cell_worker(p,c,out)
    finally:save(Path(out)/'resources.json',peak_memory())

def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);a.add_argument('--plan',type=Path);a.add_argument('--worker',type=Path);a.add_argument('--cell',type=int);a.add_argument('--reserved-seeds',type=Path);a.add_argument('--implementation',choices=['scalar','vectorized'],default='scalar');a.add_argument('--wall-seconds',type=int);v=a.parse_args()
    if v.worker:
        p=json.loads(v.worker.read_text());validate(p)
        if not p['frozen'] or p['source']!=bindings(p.get('implementation','scalar')) or p['software']!=versions() or p['python']!=sys.version or p['interpreter']!={'path':str(Path(sys.executable).resolve()),'sha256':sha(sys.executable)}:raise ValueError('Worker binding mismatch')
        run_worker(p,p['cells'][v.cell],v.out)
    elif v.plan:run(v.plan,v.out)
    else:
        if not v.reserved_seeds:raise ValueError('Explicit complete prior seed inventory required')
        evidence=json.loads(v.reserved_seeds.read_text())
        save(v.out,draft(evidence['reserved_seeds'],seed_audit=dict(path=str(v.reserved_seeds.resolve()),sha256=sha(v.reserved_seeds)),implementation=v.implementation,wall_seconds=v.wall_seconds))
if __name__=='__main__':main()









