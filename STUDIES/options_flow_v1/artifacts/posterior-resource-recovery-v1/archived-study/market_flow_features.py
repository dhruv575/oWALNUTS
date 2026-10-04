"""Offline chronological features for the frozen Deribit access protocol.

Trade prices are in the venue's native quote convention. This is conditional on
eligible future trade arrival, not a missingness model or market-utility claim.
No networking, fitting, forward filling of targets, or removal of grid rows.
"""
import bisect
import datetime
import hashlib
import json
import math
from pathlib import Path
import zipfile


def milliseconds(iso):return int(datetime.datetime.fromisoformat(iso).timestamp()*1000)
def digest_json(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def build_panel(trades,selection,protocol,*,acquisition_complete,stabilizer):
    """selection: {instrument_names:[...],selection_end_ms:int}.

    stabilizer: {value:positive,estimated_through_ms:int,provenance:nonempty}.
    Caller binds these declarations to acquisition/selection artifacts. All
    returned timestamps are event-time plus the declared assumed lag; no receipt
    timestamp is available and no realtime availability is asserted.
    """
    if acquisition_complete is not True:raise ValueError('Incomplete acquisition cannot form a fit-eligible panel')
    names=selection['instrument_names']
    if not names or len(set(names))!=len(names):raise ValueError('Unique selected instrument names required')
    start=milliseconds(protocol['start_utc']);end=milliseconds(protocol['end_utc_exclusive'])
    dev_end=start+protocol['development_hours']*3600000;val_end=dev_end+protocol['validation_hours']*3600000
    selection_end=start+protocol['selection_hours']*3600000
    if selection['selection_end_ms']!=selection_end:raise ValueError('Selection cutoff differs from protocol')
    delta=stabilizer['value']
    if isinstance(delta,bool) or not isinstance(delta,(float,int)) or not math.isfinite(delta) or delta<=0 or not stabilizer.get('provenance'):raise ValueError('Positive frozen stabilizer and provenance required')
    if not start<=stabilizer['estimated_through_ms']<=dev_end:raise ValueError('Stabilizer may use development only')
    f=protocol['forecast'];window=f['feature_bin_minutes']*60000;lag=f['availability_lag_seconds']*1000
    stale=f['maximum_reference_staleness_minutes']*60000;horizon=f['horizon_minutes']*60000;stride=f['origin_stride_minutes']*60000
    if (window,lag,stale,horizon,stride)!=(900000,60000,1800000,1800000,1800000):raise ValueError('Unsupported changed forecast protocol')
    groups={name:[] for name in names};seen=set();excluded=0
    for row in trades:
        name=row['instrument_name']
        if name not in groups:continue
        timestamp=row['timestamp'];sequence=row['trade_seq']
        if isinstance(sequence,bool) or not isinstance(sequence,int) or sequence<0:raise ValueError('Trade sequence must be a nonnegative integer')
        if isinstance(timestamp,bool) or not isinstance(timestamp,int) or not start<=timestamp<end:raise ValueError('Selected trade outside acquired panel')
        key=(name,sequence)
        if key in seen:raise ValueError('Duplicate instrument trade sequence')
        seen.add(key)
        if any(row.get(flag) is not None for flag in protocol['exclude_flags']):excluded+=1;continue
        price=row['price'];amount=row['amount'];direction=row['direction']
        if not all(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for v in (price,amount)) or direction not in ('buy','sell'):raise ValueError('Invalid eligible price/basecoin amount/direction')
        groups[name].append(dict(timestamp=timestamp,sequence=sequence,trade_id=row.get('trade_id'),price=price,amount=amount,signed_amount=amount if direction=='buy' else -amount))
    for rows in groups.values():rows.sort(key=lambda r:(r['timestamp'],r['sequence']))
    clocks={name:[r['timestamp'] for r in rows] for name,rows in groups.items()}
    records=[];cutoff=start
    while cutoff+lag+horizon<end:
        decision=cutoff+lag;target_end=decision+horizon;available=target_end+lag
        phase='development' if decision<dev_end else 'validation' if decision<val_end else 'evaluation'
        boundary=dev_end if phase=='development' else val_end if phase=='validation' else end
        group_rows=[]
        for name in names:
            rows=groups[name];times=clocks[name];last=bisect.bisect_right(times,cutoff)
            reference=rows[last-1] if last and cutoff-rows[last-1]['timestamp']<=stale else None
            first_flow=bisect.bisect_right(times,cutoff-window);flow=rows[first_flow:last]
            signed=math.fsum(r['signed_amount'] for r in flow);total=math.fsum(r['amount'] for r in flow)
            feature_complete=cutoff-window>=start
            feature=signed/(total+delta) if feature_complete else None
            first_target=bisect.bisect_right(times,decision);last_target=bisect.bisect_right(times,target_end)
            target=rows[last_target-1] if last_target>first_target else None
            y=math.log(target['price'])-math.log(reference['price']) if target and reference else None
            group_rows.append(dict(instrument_name=name,x=feature,y=y,x_available=feature_complete,y_available=y is not None,
                reference_timestamp=reference['timestamp'] if reference else None,target_timestamp=target['timestamp'] if target else None,
                reference_trade_id=reference['trade_id'] if reference else None,target_trade_id=target['trade_id'] if target else None,
                flow_count=len(flow),signed_basecoin_amount=signed,total_basecoin_amount=total,
                observation_mask=feature_complete and y is not None and available<=boundary,
                phase_boundary_purged=available>boundary,feature_available_ms=decision,target_available_ms=available))
        records.append(dict(grid_index=len(records),cutoff_ms=cutoff,decision_ms=decision,target_end_ms=target_end,
            phase=phase,selection_available=decision>=selection_end,stabilizer_available=decision>=stabilizer['estimated_through_ms'],groups=group_rows))
        cutoff+=stride
    return dict(schema='market-flow-features/v1',qualified=False,protocol_sha256=digest_json(protocol),selection_sha256=digest_json(selection),stabilizer=stabilizer,
        instruments=names,grid_stride_ms=stride,records=records,scheduled_origins=len(records),excluded_trades=excluded,
        target_definition=f['estimand'],availability=f['availability'],
        limitation='Conditional on eligible future trade arrival; no correction for informative selection. Development fitting is retrospective; report selection/stabilizer availability before any origin-level claim.')


def training_fixture(panel,*,as_of_ms,phase):
    """Keep every grid row in the requested chronological prefix, mask late labels.

    Uses raw model units; any scaling must be fitted on a separately declared
    development subset. No compression of origins with no eligible observations.
    """
    if isinstance(as_of_ms,bool) or not isinstance(as_of_ms,int) or as_of_ms<0:raise ValueError('as_of_ms must be a nonnegative integer timestamp')
    if phase not in ('development','validation','evaluation'):raise ValueError('Unknown chronological phase')
    if as_of_ms<panel['stabilizer']['estimated_through_ms']:raise ValueError('Frozen stabilizer unavailable at requested training cutoff')
    rows=[r for r in panel['records'] if r['phase']==phase and r['decision_ms']<=as_of_ms]
    if not rows:raise ValueError('No scheduled rows in requested prefix')
    if any(b['grid_index']!=a['grid_index']+1 for a,b in zip(rows,rows[1:])):raise ValueError('Requested phase is not a contiguous grid')
    y=[];x=[];mask=[]
    for row in rows:
        usable=[g['observation_mask'] and g['target_available_ms']<=as_of_ms for g in row['groups']]
        y.append([g['y'] if keep else 0. for g,keep in zip(row['groups'],usable)])
        x.append([g['x'] if g['x'] is not None else 0. for g in row['groups']])
        mask.append(usable)
    return dict(data=dict(y=y,x=x,observation_mask=mask,grid_index=list(range(len(rows))),rho=.95,nu=5.),
        provenance=dict(original_grid_indices=[r['grid_index'] for r in rows],as_of_ms=as_of_ms,phase=phase,protocol_sha256=panel['protocol_sha256']),
        missing_outcomes_are_masked=True,qualified=False)


def load_verified_panel(directory,*,expected_manifest_sha256,expected_protocol_sha256):
    """Verify completed acquisition against externally pinned artifact hashes.

    Canonical protocol hash matches collector summary; manifest hashes bind exact
    bytes, including source archive, selected names and each retained trade file.
    This verifies archived acquisition, not exchange-feed completeness.
    """
    root=Path(directory).resolve();manifest_path=root/'artifact-hashes.json'
    byte_hash=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if byte_hash(manifest_path)!=expected_manifest_sha256:raise ValueError('Artifact manifest differs from pinned digest')
    hashes=json.loads(manifest_path.read_text())
    required=['summary.json','protocol.json','selection.json','source-snapshots.zip','independent-audit.json']
    def verified_file(name):
        if not isinstance(name,str) or Path(name).name!=name or name in ('.','..'):raise ValueError('Unsafe artifact path')
        path=root/name
        if name not in hashes or byte_hash(path)!=hashes[name]:raise ValueError('Artifact hash mismatch: '+name)
        return path
    for name in required:verified_file(name)
    summary=json.loads((root/'summary.json').read_text());protocol=json.loads((root/'protocol.json').read_text());selection=json.loads((root/'selection.json').read_text())
    if summary.get('status')!='complete_access_panel':raise ValueError('Acquisition not complete')
    if digest_json(protocol)!=expected_protocol_sha256 or summary.get('protocol_sha256')!=expected_protocol_sha256:raise ValueError('Archived protocol differs from frozen protocol')
    audit=json.loads((root/'independent-audit.json').read_text())
    if audit.get('passed') is not True:raise ValueError('Independent acquisition audit did not pass')
    with zipfile.ZipFile(root/'source-snapshots.zip') as archive:
        name='acquire_deribit_panel.py'
        if archive.namelist().count(name)!=1 or hashlib.sha256(archive.read(name)).hexdigest()!=summary.get('source_sha256'):raise ValueError('Archived collector source hash mismatch')
    names=summary['selected']
    if names!=selection.get('selected') or len(set(names))!=len(names) or len(names)!=protocol['contracts']:raise ValueError('Selected names differ or duplicate')
    if set(summary['trade_counts'])!=set(names) or set(summary['field_quality'])!=set(names):raise ValueError('Per-instrument inventory differs')
    rows=[];seen_ids=set();seen_sequences=set();files=set()
    for name in names:
        quality=summary['field_quality'][name];filename=quality['file']
        if filename in files:raise ValueError('Trade file reused across instruments')
        files.add(filename);trades=json.loads(verified_file(filename).read_text())
        if len(trades)!=summary['trade_counts'][name] or len(trades)!=quality['total']:raise ValueError('Trade count mismatch')
        for trade in trades:
            if trade['instrument_name']!=name:raise ValueError('Instrument/file mismatch')
            identifier=str(trade['trade_id']);sequence=trade['trade_seq']
            if isinstance(sequence,bool) or not isinstance(sequence,int) or sequence<0:raise ValueError('Invalid trade sequence')
            if identifier in seen_ids or (name,sequence) in seen_sequences:raise ValueError('Duplicate trade ID or instrument sequence')
            seen_ids.add(identifier);seen_sequences.add((name,sequence))
        rows.extend(trades)
    if len(rows)!=audit.get('trades'):raise ValueError('Audited total trade count mismatch')
    normalized_selection=dict(instrument_names=names,selection_end_ms=milliseconds(protocol['start_utc'])+protocol['selection_hours']*3600000)
    stabilizer=dict(value=1e-8,estimated_through_ms=milliseconds(protocol['start_utc']),provenance='prespecified constant; no estimation')
    panel=build_panel(rows,normalized_selection,protocol,acquisition_complete=True,stabilizer=stabilizer)
    panel['acquisition_binding']=dict(manifest_sha256=expected_manifest_sha256,protocol_sha256=expected_protocol_sha256,
        selection_file_sha256=hashes['selection.json'],summary_sha256=hashes['summary.json'],collector_source_sha256=summary['source_sha256'],trade_files={name:hashes[name] for name in sorted(files)})
    return panel


def observability_summary(panel):
    counts={};origins={}
    for row in panel['records']:
        phase=row['phase'];origins[phase]=origins.get(phase,0)+1
        for group in row['groups']:
            entry=counts.setdefault(phase,{}).setdefault(group['instrument_name'],dict(scheduled=0,reference_present=0,target_present=0,usable=0,missing_return=0,empty_feature_bin=0))
            for key,value in dict(scheduled=True,reference_present=group['reference_timestamp'] is not None,target_present=group['target_timestamp'] is not None,usable=group['observation_mask'],missing_return=group['y'] is None,empty_feature_bin=group['flow_count']==0).items():entry[key]+=int(value)
    return dict(scheduled_origins=origins,counts=counts,usable_group_observations={phase:sum(v['usable'] for v in groups.values()) for phase,groups in counts.items()},qualified=False)
