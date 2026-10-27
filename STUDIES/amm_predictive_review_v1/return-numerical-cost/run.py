"""Post-hoc single-origin numerical integration cost check. See PLAN.md."""
import argparse
import ctypes
import gc
import hashlib
import importlib.util
import json
import os
import platform
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import scipy

HERE=Path(__file__).resolve().parent
SHARED=HERE.parent/'predictive-return-smoke'/'process.py'
SAVED=SHARED.parent/'real-tick002-smoke'/'smoke-results.json'
FIXTURES=SHARED.parent/'fixture-results.json'
spec=importlib.util.spec_from_file_location('return_processor',SHARED)
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
LIMIT=400_000_000


def memory():
    if os.name!='nt':
        return dict(pid=os.getpid(),status='unavailable',reason='This run requires Windows process peak working-set API')
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[
            (name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
            'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    counters=Counters()
    counters.cb=ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return dict(pid=os.getpid(),status='measured',method='in-process GetProcessMemoryInfo',
        peak_working_set_bytes=counters.PeakWorkingSetSize,current_working_set_bytes=counters.WorkingSetSize,
        private_usage_bytes=counters.PrivateUsage,peak_pagefile_usage_bytes=counters.PeakPagefileUsage)


class BudgetCDF(base.ReturnCDF):
    def __init__(self,*args,ledger,**kwargs):
        self.ledger=ledger
        super().__init__(*args,**kwargs)
    def __call__(self,x):
        reserve=len(self.m)*self.nodes
        if self.ledger['reserved']+reserve>LIMIT:
            raise RuntimeError('component-node evaluation budget exhausted')
        self.ledger['reserved']+=reserve
        return super().__call__(x)


def verify_manifest(root):
    path=root/'files.sha256'
    for line in path.read_text().splitlines():
        digest,name=line.split(None,1)
        if base.identity(root/name.lstrip('*'))['sha256']!=digest:
            raise ValueError(f'snapshot manifest mismatch: {name}')
    return base.identity(path)


def load(root,cell_id,sources):
    proto=root/'protocol.json'
    log=root/'cells'/cell_id/'ticks.jsonl'
    sources.extend([base.identity(proto),base.identity(log),base.identity(root/'provenance.json'),verify_manifest(root)])
    protocol=json.loads(proto.read_text())
    records=[json.loads(line) for line in log.read_text().splitlines()]
    selected=[r for r in records if r.get('tick')==2]
    if len(selected)!=1 or selected[0].get('status')!='ok':
        raise ValueError('fixed tick missing, duplicated or original record failed')
    rec=selected[0]
    reference=cell_id.startswith('ref-')
    path=root/'cells'/cell_id/(rec['file'] if reference else 'tick-002.f32')
    sources.append(base.identity(path))
    raw=np.frombuffer(path.read_bytes(),dtype='<f4')
    if raw.size!=rec['chains']*rec['draws']*4:
        raise ValueError('compact four-field shape mismatch')
    a=raw.reshape(rec['chains'],rec['draws'],4).astype(float)
    if reference:
        a=a[rec['kept']]
    elif len(rec.get('kept',range(rec['chains'])))!=len(a):
        raise ValueError('warm chain identity mismatch')
    mu,ls,beta,h=[a[...,i].ravel() for i in range(4)]
    return (mu+protocol['model']['rho']*(h-mu),np.exp(ls),beta),protocol,rec,base.identity(path)


def stats(cdf):
    return dict(nodes=cdf.nodes,cdf_evaluations=cdf.calls,student_t_evaluations=cdf.student_t_evaluations,
                cached_bytes=cdf.cached_bytes,chunk=cdf.chunk,scratch_matrix_max_shape=[min(cdf.chunk,len(cdf.m)),cdf.nodes])


def process_case(root,cell_id,deadline,ledger,sources,saved):
    start=time.perf_counter()
    row=dict(cell=cell_id,tick=2,status='pending',rules={})
    cdf128=None
    low=None
    try:
        args,proto,rec,raw_id=load(root,cell_id,sources)
        row.update(components=len(args[0]),original_record=rec,raw_identity=raw_id)
        begin=time.perf_counter()
        cdf128=BudgetCDF(*args,proto['model']['nu'],128,deadline,base.CACHE_LIMIT,ledger=ledger)
        row['gh128_cache_initialization_seconds']=time.perf_counter()-begin
        low_results=[]
        for nodes in (8,16,32):
            begin=time.perf_counter()
            low=BudgetCDF(*args,proto['model']['nu'],nodes,deadline,base.CACHE_LIMIT-cdf128.cached_bytes,ledger=ledger)
            cached=time.perf_counter()
            q=low.quantiles()
            q.update(cache_initialization_seconds=cached-begin,total_rule_seconds=time.perf_counter()-begin,
                     counters=stats(low))
            row['rules'][str(nodes)]=q
            low_results.append(q)
            del low
            low=None
        if cell_id.startswith('ref-'):
            saved_raw=next(i for i in saved['input_identities'] if Path(i['path']).name=='tick-002-a0.f32')
            if raw_id['sha256']!=saved_raw['sha256']:
                raise ValueError('reference raw bytes differ from saved GH128 smoke')
            q128=np.array(saved['rules']['128']['quantiles'])
            row['gh128_comparator']=dict(source='saved prior same-input smoke',quantiles=q128.tolist())
        else:
            begin=time.perf_counter()
            q=cdf128.quantiles()
            q.update(total_rule_seconds=time.perf_counter()-begin+row['gh128_cache_initialization_seconds'],
                     cache_initialization_seconds=row['gh128_cache_initialization_seconds'])
            row['rules']['128']=q
            q128=np.array(q['quantiles'])
            row['gh128_comparator']=dict(source='computed on same actual warm draws',quantiles=q128.tolist())
        width=q128[2]-q128[0]
        comparisons=[]
        for nodes in (8,16,32):
            q=np.array(row['rules'][str(nodes)]['quantiles'])
            delta=np.abs(q-q128)/width
            residual=np.abs(np.array([cdf128(x) for x in q])-np.array(base.PS))
            comparisons.append(dict(nodes=nodes,relative_endpoint_discrepancies=delta.tolist(),
                gh128_cdf_residuals=residual.tolist(),within_fixed_targets=bool(max(delta)<=1e-6 and max(residual)<=1e-6)))
        row.update(status='completed',comparisons=comparisons,gh128_counters=stats(cdf128),memory=memory())
    except Exception as exc:
        row.update(status='failed_or_budget',error=str(exc),memory=memory())
        if cdf128 is not None:
            row['gh128_counters']=stats(cdf128)
        if low is not None:
            row['partial_low_counters']=stats(low)
    row['total_case_seconds']=time.perf_counter()-start
    del low,cdf128
    gc.collect()
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-snapshot',type=Path,required=True)
    parser.add_argument('--warm-snapshot',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=HERE)
    args=parser.parse_args()
    output=args.out/'results.json'
    if output.exists():
        raise SystemExit('Preserving existing result; use a new output directory')
    start=time.perf_counter()
    deadline=start+300
    ledger={'reserved':0}
    sources=[]
    result=dict(kind='post-hoc one-origin numerical-cost diagnostic; no posterior accuracy qualification',
        created_utc=datetime.now(timezone.utc).isoformat(),source=base.identity(Path(__file__)),
        plan=base.identity(HERE/'PLAN.md'),dependency=base.identity(SHARED),prior_smoke=base.identity(SAVED),
        reused_fixtures=base.identity(FIXTURES),environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,
        platform=platform.platform()),memory_start=memory(),cases=[],component_node_budget=LIMIT,cache_budget_bytes=base.CACHE_LIMIT)
    saved=json.loads(SAVED.read_text())
    fixture=json.loads(FIXTURES.read_text())
    if saved['source']['sha256']!=result['dependency']['sha256'] or fixture['source']['sha256']!=result['dependency']['sha256']:
        raise ValueError('shared processor differs from independently validated source')
    for root,cell in [(args.reference_snapshot,'ref-real-lo')]+[(args.warm_snapshot,f'warm{k}-real-s971301') for k in (20,50,200)]:
        if time.perf_counter()>=deadline or ledger['reserved']>=LIMIT:
            result['cases'].append(dict(cell=cell,tick=2,status='not_run_budget'))
        else:
            result['cases'].append(process_case(root,cell,deadline,ledger,sources,saved))
    result.update(memory_end=memory(),component_node_evaluations_reserved=ledger['reserved'],input_identities=sources,
        total_local_processing_seconds=time.perf_counter()-start,
        input_integrity_after=all(base.identity(Path(i['path']))['sha256']==i['sha256'] for i in sources))
    result['status']='completed' if result['input_integrity_after'] and all(c['status']=='completed' for c in result['cases']) else 'incomplete_or_failed'
    args.out.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(result,handle,indent=2,allow_nan=False)
        handle.write('\n')
    print(json.dumps(dict(status=result['status'],seconds=result['total_local_processing_seconds'],memory=result['memory_end'],
        reserved=ledger['reserved'],cases=[dict(cell=c['cell'],status=c['status'],comparisons=c.get('comparisons'),
        timings={k:v['total_rule_seconds'] for k,v in c.get('rules',{}).items()}) for c in result['cases']]),indent=2))


if __name__=='__main__':
    main()
