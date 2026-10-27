"""Sealed acquisition admission and fixed causal indexing; no acquisition calls."""
import hashlib,json
from pathlib import Path
import numpy as np
from acquire import validate_response,day_starts,validate_protocol,HALF

ORIGINS=1488
FIRST_ORIGIN_MS=1785542400000

def sha(raw):return hashlib.sha256(raw).hexdigest()

def returns_from_bars(bars):
    if len(bars)!=1776:raise ValueError('Exactly1776 acquired bars required')
    first=1785024000000
    if [r['open_ms'] for r in bars]!=list(range(first,first+1776*HALF,HALF)):raise ValueError('Whole bar grid mismatch')
    if any(r['close_available_ms']!=r['open_ms']+HALF for r in bars):raise ValueError('Bar availability convention mismatch')
    closes=np.asarray([r['close'] for r in bars[36:]],dtype=float)
    if closes.shape!=(1740,) or not np.isfinite(closes).all() or np.any(closes<=0):raise ValueError('Invalid relevant closes')
    y=np.diff(np.log(closes))
    if y.shape!=(1739,) or not np.isfinite(y).all():raise ValueError('Invalid relevant returns')
    return y

def inputs(y,tick):
    if type(tick)is not int or not 1<=tick<=ORIGINS:raise ValueError('Tick outside fixed1488 grid')
    if np.asarray(y).shape!=(1739,):raise ValueError('Exactly1739 relevant returns required')
    origin=FIRST_ORIGIN_MS+(tick-1)*HALF
    return dict(tick=tick,current_index=249+tick,label_index=250+tick,origin_ms=origin,label_available_ms=origin+HALF,
        window=np.asarray(y[tick:250+tick]).copy(),observation=float(y[249+tick]),label=float(y[250+tick]))

def load_sealed(directory,bindings):
    """Only a compute-authorized caller may supply sealed acquisition hashes."""
    root=Path(directory);raws={}
    for name,key in [('terminal.json','terminal_sha256'),('protocol.json','protocol_sha256'),('bars.json','bars_sha256')]:
        raw=(root/name).read_bytes()
        if sha(raw)!=bindings[key]:raise ValueError('Acquisition binding changed: '+name)
        raws[name]=raw
    supervisor_raw=Path(bindings['supervisor_final_path']).read_bytes()
    if sha(supervisor_raw)!=bindings['supervisor_final_sha256']:raise ValueError('Supervisor binding changed')
    supervisor=json.loads(supervisor_raw);terminal=json.loads(raws['terminal.json']);protocol=json.loads(raws['protocol.json'])
    if supervisor.get('sealed_acquisition_admitted')is not True or supervisor.get('status')!='exited' or supervisor.get('exit_code')!=0 or supervisor.get('remaining_owned_pids')!=[]:raise ValueError('Acquisition watchdog did not admit')
    if terminal.get('complete')is not True or terminal.get('status')!='complete' or terminal.get('completed_requests')!=list(range(37)) or terminal.get('valid_bars')!=1776:raise ValueError('Acquisition incomplete')
    if terminal['source_sha256']!=bindings['collector_sha256'] or terminal['protocol_sha256']!=bindings['protocol_sha256'] or terminal['bars_sha256']!=bindings['bars_sha256']:raise ValueError('Acquisition terminal binding mismatch')
    validate_protocol(protocol)
    if protocol.get('status')!='frozen_authorized' or protocol['acquire_source_sha256']!=bindings['collector_sha256']:raise ValueError('Acquisition protocol mismatch')
    reconstructed=[]
    for index,lo in enumerate(day_starts(protocol)):
        raw=(root/f'response-{index:03d}.json').read_bytes();meta=json.loads((root/f'response-{index:03d}-metadata.json').read_bytes())
        if meta['http_status']!=200 or len(raw)!=meta['bytes'] or sha(raw)!=meta['sha256']:raise ValueError('Raw acquisition response mismatch')
        reconstructed.extend(validate_response(raw,lo))
    saved=json.loads(raws['bars.json'])
    if saved!=reconstructed:raise ValueError('Saved bars differ from sealed raw responses')
    return returns_from_bars(saved)
