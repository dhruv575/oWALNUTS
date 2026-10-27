"""Linear immutable evidence loop shared by fixed-window research studies.
Numerical engine/scorer are injected, pinned dependencies; this module samples nothing on import.
"""
import hashlib,json,os,time
from pathlib import Path
import numpy as np

MASK=(1<<64)-1

def digest_bytes(raw):return hashlib.sha256(raw).hexdigest()
def safe(value):
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,np.ndarray):return safe(value.tolist())
    if isinstance(value,float) and not np.isfinite(value):return dict(nonfinite=repr(value))
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    return value

def encoded(value):return (json.dumps(safe(value),sort_keys=True,allow_nan=False)+'\n').encode()
def exclusive(path,value):
    raw=encoded(value)
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return digest_bytes(raw)

def packed(value,prefix,arrays,retain):
    if isinstance(value,np.ndarray):
        a=np.asarray(value);identity=dict(shape=list(a.shape),dtype=a.dtype.str,sha256=digest_bytes(a.tobytes(order='C')))
        if retain:arrays[prefix]=a;identity['array_key']=prefix
        else:identity['raw_retained']=False
        return identity
    if isinstance(value,dict):return {str(k):packed(v,prefix+'__'+str(k),arrays,retain) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [packed(v,prefix+'__'+str(i),arrays,retain) for i,v in enumerate(value)]
    return safe(value)

def diagnostic_totals(diagnostics):
    result=[]
    for chain,entry in enumerate(diagnostics):
        divergence=np.asarray(entry['divergent']);row=dict(chain=chain,transitions=int(divergence.size),divergences=int(np.count_nonzero(divergence)))
        for key in ('stop','depth','max_abs_energy_error','zero_density_evaluations'):
            if key not in entry:row[key+'_available']=False;continue
            a=np.asarray(entry[key]);row[key+'_available']=True
            if key=='stop':
                values,counts=np.unique(a,return_counts=True);row['stop_counts']={str(int(v)):int(n) for v,n in zip(values,counts)}
            elif key=='depth':row['maximum_depth']=int(a.max()) if a.size else None
            elif key=='zero_density_evaluations':row['zero_density_evaluations']=int(a.sum())
            else:
                finite=np.isfinite(a);row['nonfinite_energy_errors']=int((~finite).sum());row['maximum_finite_abs_energy_error']=float(np.max(np.abs(a[finite]))) if finite.any() else None
        result.append(row)
    return result

def run_lane(y,*,updates,seeds,score_ticks,retain_ticks,engine_factory,score_hook,output,metadata_hook=None,window=250,k=400):
    y=np.asarray(y)
    if y.dtype!=np.dtype('float64') or y.ndim!=1 or len(y)<window+updates+1 or not np.isfinite(y).all():raise ValueError('finite float64 causal observations plus last label required')
    if window!=250 or k!=400 or type(updates)is not int or updates<1:raise ValueError('fixed250/K400 and positive updates required')
    scored=set(score_ticks);retained=set(retain_ticks)
    if not scored<=retained or any(type(t)is not int or not 1<=t<=updates for t in retained):raise ValueError('scored ticks must be retained planned ticks')
    root=Path(output);root.mkdir(parents=True,exist_ok=False);(root/'records').mkdir();(root/'draws').mkdir();(root/'arrays').mkdir();(root/'native').mkdir()
    exclusive(root/'PLAN.json',dict(updates=updates,window=window,k=k,seeds=seeds,score_ticks=sorted(scored),retain_ticks=sorted(retained),y_shape=list(y.shape),y_sha256=digest_bytes(y.tobytes(order='C'))))
    started=time.perf_counter();engine=None;native_completed=0;score_counts={'ok':0,'partial':0,'unavailable':0};attempted=0;terminal_error=None;initialization_seconds=None;io_seconds=0.;native_seconds=0.;scoring_seconds=0.
    journal=(root/'progress.jsonl').open('xb')
    def event(value):journal.write(encoded(value));journal.flush();os.fsync(journal.fileno())
    event(dict(event='initialization_started'))
    try:
        init_start=time.perf_counter()
        try:engine=engine_factory(y[:window].copy(),dict(seeds))
        finally:initialization_seconds=time.perf_counter()-init_start
        exclusive(root/'INITIAL.json',dict(status='complete',telemetry=getattr(engine,'initial',None),engine_factory_seconds=initialization_seconds))
        event(dict(event='initialization_complete'))
        for tick in range(1,updates+1):
            attempted=tick;current=window-1+tick;label_index=window+tick;conditioning=y[tick:window+tick].copy();tick_start=time.perf_counter()
            event(dict(event='tick_started',tick=tick,current_index=current,label_index=label_index))
            row=dict(tick=tick,current_index=current,label_index=label_index,window_start=tick,window_stop=window+tick,window_sha256=digest_bytes(conditioning.tobytes(order='C')),native_status='pending',score_status='pending' if tick in scored else 'not_planned')
            if metadata_hook is not None:row['context']=metadata_hook(tick,current,label_index)
            draws=None;arrays={};native_error=False
            try:
                t=time.perf_counter();draws,telemetry=engine.advance(float(y[current]),k);row['native_wall_seconds']=time.perf_counter()-t;native_seconds+=row['native_wall_seconds']
                draws=np.asarray(draws)
                if draws.dtype!=np.dtype('float64') or draws.shape!=(4,k,4) or not np.isfinite(draws).all():raise ValueError('invalid native joint compact')
                if int(telemetry['call_index'])!=tick-1 or int(telemetry['seed'])!=((seeds['warm']+4*(tick-1))&MASK):raise ValueError('native call index/seed schedule mismatch')
                if hasattr(engine,'y') and not np.array_equal(engine.y,conditioning):raise ValueError('native window ownership mismatch')
                row['native_health']=diagnostic_totals(telemetry['diagnostics'])
                row.update(native_status='ok',compact_value_sha256=digest_bytes(draws.tobytes(order='C')),native=packed(telemetry,'native',arrays,tick in retained));native_completed+=1
            except Exception as exc:
                if 'native_wall_seconds' not in row:
                    row['native_wall_seconds']=time.perf_counter()-t;native_seconds+=row['native_wall_seconds']
                row.update(native_status='failed',native_error=repr(exc),score_status='unavailable' if tick in scored else 'not_planned');native_error=True
                if tick in scored:score_counts['unavailable']+=1
                terminal_error=dict(phase='native',tick=tick,error=repr(exc))
            # Persist successful native evidence before any downstream scorer can hang/fail/mutate.
            io_start=time.perf_counter()
            if draws is not None and tick in retained:
                p=root/'draws'/f'{tick:06d}.npy'
                with p.open('xb') as f:np.save(f,draws,allow_pickle=False);f.flush();os.fsync(f.fileno())
                row['compact']=dict(file=str(p.relative_to(root)),sha256=digest_bytes(p.read_bytes()))
            if arrays:
                p=root/'arrays'/f'{tick:06d}-native.npz'
                with p.open('xb') as f:np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno())
                row['native_arrays']=dict(file=str(p.relative_to(root)),sha256=digest_bytes(p.read_bytes()));arrays={}
            if tick in scored:row['native_record_sha256']=exclusive(root/'native'/f'{tick:06d}.json',row)
            pre_io=time.perf_counter()-io_start
            if not native_error and tick in scored:
                event(dict(event='score_started',tick=tick))
                t=time.perf_counter()
                try:
                    score_draws=draws.copy();score_draws.flags.writeable=False
                    score_window=conditioning.copy();score_window.flags.writeable=False
                    value=score_hook(score_draws,score_window,float(y[label_index]),tick)
                    if not isinstance(value,dict):raise ValueError('scorer must return mapping')
                    status=value.get('status','ok')
                    if status not in score_counts:raise ValueError('invalid scorer status')
                    row['score']=packed(value,'score',arrays,True);row['score_status']=status
                except Exception as exc:row.update(score_status='unavailable',score_error=repr(exc))
                row['scoring_seconds']=time.perf_counter()-t;scoring_seconds+=row['scoring_seconds'];score_counts[row['score_status']]+=1
            io_start=time.perf_counter()
            if arrays:
                p=root/'arrays'/f'{tick:06d}.npz'
                with p.open('xb') as f:np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno())
                row['arrays']=dict(file=str(p.relative_to(root)),sha256=digest_bytes(p.read_bytes()))
            row['before_record_io_seconds']=pre_io+time.perf_counter()-io_start;row['before_record_elapsed_seconds']=time.perf_counter()-tick_start
            record=root/'records'/f'{tick:06d}.json';record_sha=exclusive(record,row);this_io=pre_io+time.perf_counter()-io_start;io_seconds+=this_io
            event(dict(event='tick_completed',tick=tick,native_status=row['native_status'],score_status=row['score_status'],record_sha256=record_sha,io_seconds=this_io,total_through_record_seconds=time.perf_counter()-tick_start))
            if native_error:break
    except Exception as exc:
        if terminal_error is None:terminal_error=dict(phase='initialization' if engine is None else 'infrastructure',tick=attempted,error=repr(exc),payload=getattr(exc,'payload',None))
        else:terminal_error['infrastructure_error']=repr(exc)
        if engine is None and not (root/'INITIAL.json').exists():exclusive(root/'INITIAL.json',dict(status='failed',failure=terminal_error))
    finally:
        close_error=None
        if engine is not None:
            try:engine.close()
            except Exception as exc:close_error=repr(exc)
        journal.close()
        result=dict(status='failed' if terminal_error or close_error else 'complete' if score_counts['partial']==score_counts['unavailable']==0 else 'partial_scores',planned_updates=updates,attempted_updates=attempted,native_completed=native_completed,planned_scores=len(scored),score_counts=score_counts,unattempted_from=attempted+1 if attempted<updates else None,terminal_error=terminal_error,close_error=close_error,initialization_seconds=initialization_seconds,native_seconds=native_seconds,scoring_seconds=scoring_seconds,record_io_seconds=io_seconds,elapsed_seconds=time.perf_counter()-started,timing_scope='Whole elapsed includes all progress/record I/O; per-tick journal totals end after immutable record, before its completion journal append.')
        exclusive(root/'DONE.json',result)
    return result
