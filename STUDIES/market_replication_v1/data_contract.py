"""Fixed three-month causal contract; no network calls."""
import hashlib,json
from pathlib import Path
import numpy as np
from acquire import validate_protocol,validate_response,day_starts,HALF

MONTHS=[dict(month='2026-04',origins=1440,first_origin_ms=1775001600000,close_start=36,reference_ticks=[1,207,412,618,823,1029,1234,1440]),
 dict(month='2026-05',origins=1488,first_origin_ms=1777593600000,close_start=1476,reference_ticks=[1,213,426,638,851,1063,1276,1488]),
 dict(month='2026-06',origins=1440,first_origin_ms=1780272000000,close_start=2964,reference_ticks=[1,207,412,618,823,1029,1234,1440])]
ORIGINS=1440;FIRST_ORIGIN_MS=1775001600000

def configure(month):
    global ORIGINS,FIRST_ORIGIN_MS
    row=next((dict(v) for v in MONTHS if v['month']==month),None)
    if row is None:raise ValueError('Month outside frozen three panels')
    ORIGINS=row['origins'];FIRST_ORIGIN_MS=row['first_origin_ms'];return row

def inputs(y,tick):
    if type(tick)is not int or not 1<=tick<=ORIGINS:raise ValueError('Tick outside fixed month')
    if np.asarray(y).shape!=(ORIGINS+251,):raise ValueError('Fixed month return count mismatch')
    origin=FIRST_ORIGIN_MS+(tick-1)*HALF
    return dict(tick=tick,current_index=249+tick,label_index=250+tick,origin_ms=origin,label_available_ms=origin+HALF,
        window=np.asarray(y[tick:250+tick]).copy(),observation=float(y[249+tick]),label=float(y[250+tick]))

def panel_returns(bars,month):
    row=next(v for v in MONTHS if v['month']==month)
    if len(bars)!=4656 or [r['open_ms'] for r in bars]!=list(range(1774483200000,1774483200000+4656*HALF,HALF)):raise ValueError('Full97day exact bar grid required')
    if any(r['close_available_ms']!=r['open_ms']+HALF for r in bars):raise ValueError('Historical timestamp convention mismatch')
    start=row['close_start'];closes=np.asarray([r['close'] for r in bars[start:start+row['origins']+252]],dtype=float)
    if closes.shape!=(row['origins']+252,) or not np.isfinite(closes).all() or np.any(closes<=0):raise ValueError('Invalid fixed relevant closes')
    y=np.diff(np.log(closes))
    if not np.isfinite(y).all():raise ValueError('Invalid returns')
    return y

def sha(raw):return hashlib.sha256(raw).hexdigest()

def load_sealed(bindings,month):
    root=Path(bindings['directory']);raws={}
    for name,key in [('terminal.json','terminal_sha256'),('protocol.json','protocol_sha256'),('bars.json','bars_sha256')]:
        raw=(root/name).read_bytes()
        if sha(raw)!=bindings[key]:raise ValueError('Acquisition hash changed: '+name)
        raws[name]=raw
    raw=Path(bindings['supervisor_final_path']).read_bytes()
    if sha(raw)!=bindings['supervisor_final_sha256']:raise ValueError('Outer admission hash changed')
    supervisor=json.loads(raw);terminal=json.loads(raws['terminal.json']);protocol=json.loads(raws['protocol.json'])
    if supervisor.get('sealed_acquisition_admitted')is not True or supervisor.get('status')!='exited' or supervisor.get('exit_code')!=0 or supervisor.get('remaining_owned_pids')!=[]:raise ValueError('Acquisition supervisor did not admit')
    if terminal.get('complete')is not True or terminal.get('status')!='complete' or terminal.get('completed_requests')!=list(range(97)) or terminal.get('valid_bars')!=4656:raise ValueError('Incomplete97day acquisition')
    if terminal['source_sha256']!=bindings['collector_sha256'] or terminal['protocol_sha256']!=bindings['protocol_sha256'] or terminal['bars_sha256']!=bindings['bars_sha256']:raise ValueError('Acquisition terminal mismatch')
    validate_protocol(protocol)
    if protocol.get('status')!='frozen_authorized' or protocol['acquire_source_sha256']!=bindings['collector_sha256']:raise ValueError('Acquisition protocol mismatch')
    reconstructed=[]
    for index,lo in enumerate(day_starts(protocol)):
        raw=(root/f'response-{index:03d}.json').read_bytes();meta=json.loads((root/f'response-{index:03d}-metadata.json').read_bytes())
        if meta['http_status']!=200 or len(raw)!=meta['bytes'] or sha(raw)!=meta['sha256']:raise ValueError('Raw response mismatch')
        reconstructed.extend(validate_response(raw,lo))
    saved=json.loads(raws['bars.json'])
    if saved!=reconstructed:raise ValueError('Sealed bars differ from raw responses')
    return panel_returns(saved,month)
