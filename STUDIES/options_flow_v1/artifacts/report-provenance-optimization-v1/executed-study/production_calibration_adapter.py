"""Immutable prospective normalization for dense public continuation reports.

No inference is launched. A prospective manifest adds ``procedure`` to the
production_calibration_report contract. Its canonical sorted-JSON SHA256 must
match procedure_sha256. Procedure fields: worker_kind ('public'|'reference'),
worker_arm, coordinates, warmup, chains, tiers, relative_mcse, timeout_seconds,
cpus, bound_files, runtime_bindings; optional target_accept and block_size.
Each intended cell adds fixture_path, output_directory, status_path,
hardware_path, and started_path. The pre-execution started marker must bind
protocol_sha256, procedure_sha256, fixture_sha256, dataset_seed. Existing
exploratory files without that prospective envelope remain ineligible.

Cells keep the source_sha256 schema expected by the worker: absolute bindings
for public continuation, filename keys for reference. Extra runtime bindings
are verified separately. Inputs are never edited; write_records uses exclusive
creation. This first adapter supports dense flow and exogenous local-level only.

Reference procedures explicitly declaring implementation='associative' use the
mixed_flow_reference report.json schema and per-tier raw artifacts. Admission
checks absolute worker bindings against the manifest's basename source map,
transformed starts, checkpoint continuity, and exact selected-tier output.
Legacy reference procedures retain the continuation_precision schema.
"""
import hashlib,json,math
from pathlib import Path
from production_calibration_report import validate_manifest,finite


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def object_digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def normalized(bindings):return {str(Path(k).resolve()).casefold():v for k,v in bindings.items()}
def require(ok,message):
    if not ok:raise ValueError(message)
def close_matrix(a,b):
    return isinstance(a,list) and len(a)==len(b) and all(isinstance(x,list) and len(x)==len(y) and all(finite(v) and abs(v-w)<=1e-12 for v,w in zip(x,y)) for x,y in zip(a,b))
def raw_tail(path,key):
    with Path(path).open('rb') as f:
        f.seek(max(0,Path(path).stat().st_size-1000000));tail=f.read().decode()
    marker='"'+key+'":';offset=tail.rfind(marker)
    require(offset>=0,'Missing bounded raw '+key)
    return json.JSONDecoder().raw_decode(tail[offset+len(marker):].lstrip())[0]


def fixture_contract(fixture,model):
    require(fixture.get('prior_predictive') is True,'Not a prior-generative fixture')
    data=fixture['data'];truth=fixture['truth'];future=fixture['holdout'];t=len(data['y'])
    require(t>0 and all(finite(v) for v in truth),'Invalid canonical generated truth')
    if model=='flow':
        require('observation_mask' not in data and 'observation_mask' not in future,'Dense adapter cannot ignore masks')
        g=len(data['y'][0]);dimension=4+2*g+t
        require(g>0 and len(truth)==dimension,'Flow canonical truth layout')
        for matrix,length in [(data['y'],t),(data['x'],t),(future['y'],len(future['y'])),(future['x'],len(future['y']))]:
            require(length>0 and len(matrix)==length and all(len(row)==g and all(finite(v) for v in row) for row in matrix),'Invalid dense panel')
        names=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']
        vals=dict(beta_bar=truth[0],tau=math.exp(truth[1]),mu_h=truth[2],sigma_h=math.exp(truth[3]),h_terminal=truth[-1],h_mean=sum(truth[4+2*g:])/t)
        for j in range(g):
            names.extend([f'alpha_{j}',f'beta_{j}']);vals[f'alpha_{j}']=.3*truth[4+j];vals[f'beta_{j}']=truth[0]+math.exp(truth[1])*truth[4+g+j]
        forecasts={(i+1,j):v for i,row in enumerate(future['y']) for j,v in enumerate(row)}
    elif model=='local_level':
        require(data.get('anchor_mode')=='exogenous','Empirical-Bayes anchor is not prior-generative calibration')
        dimension=t+2;require(len(truth)==dimension and all(finite(v) for v in data['y']+future['y']) and len(future['y'])>0,'Local truth/observations invalid')
        names=['h_initial','h_terminal','h_mean','sigma_obs','sigma_rw']
        vals=dict(h_initial=truth[0],h_terminal=truth[t-1],h_mean=sum(truth[:t])/t,sigma_obs=math.exp(truth[-2]),sigma_rw=math.exp(truth[-1]))
        forecasts={(i+1,None):v for i,v in enumerate(future['y'])}
    else:raise ValueError('Unknown dense model')
    starts=data.get('initial_positions')
    require(isinstance(starts,list) and len(starts)==4 and all(len(row)==dimension and all(finite(v) for v in row) for row in starts),'Four explicit canonical starts required')
    require(len({tuple(row) for row in starts})==4,'Identical starts')
    return dict(dimension=dimension,names=names,truth=vals,forecasts=forecasts,starts=starts)


def interval(row,forecast=False):
    bounds=[row.get('lower'),row.get('upper')] if forecast else row.get('interval_90')
    mcse=row.get('endpoint_mcse')
    require(isinstance(bounds,list) and isinstance(mcse,list) and len(bounds)==len(mcse)==2 and all(finite(v) for v in bounds+mcse) and bounds[1]>bounds[0] and min(mcse)>=0,'Invalid endpoint interval/MCSE')
    return bounds,max(mcse)/(bounds[1]-bounds[0])


def gate(report,contract,threshold):
    e=report['evaluation'];fs=e['functionals'];coords=e['canonical_parameter_diagnostics'];rows=e['forecast']['rows']
    require(set(fs)==set(contract['names']) and set(coords)=={f'q_{i}' for i in range(contract['dimension'])},'Incomplete physical/canonical diagnostic scope')
    keys=[(r.get('horizon'),r.get('group')) for r in rows]
    require(len(keys)==len(set(keys)) and set(keys)==set(contract['forecasts']),'Incomplete/duplicate forecast scope')
    for r in rows:require(r.get('observed')==contract['forecasts'][(r.get('horizon'),r.get('group'))],'Forecast outcome differs from verified fixture')
    # Worker truth is checked when emitted, but never used as the truth source.
    for name,row in fs.items():
        if 'truth' in row:require(finite(row['truth']) and math.isclose(row['truth'],contract['truth'][name],rel_tol=1e-12,abs_tol=1e-12),'Worker truth differs from fixture')
    ds=[*fs.values(),*coords.values()]
    healthy=report.get('status')=='completed' and e.get('chain_count')==4 and report.get('retained_divergences')==0 and all(all(finite(d.get(k)) for k in ['rhat','bulk_ess','tail_ess']) and 0<d['rhat']<=1.01 and d['bulk_ess']>=400 and d['tail_ess']>=400 for d in ds)
    ratios=[interval(r)[1] for r in fs.values()]+[interval(r,True)[1] for r in rows]
    return dict(healthy=healthy,precise=all(v<=threshold for v in ratios),passed=healthy and all(v<=threshold for v in ratios),max_endpoint_ratio=max(ratios))


def select_truth(contract,selectors):
    return {s['name']:(contract['truth'][s['key']] if s['kind']=='functional' else contract['forecasts'][(s['horizon'],s.get('group'))]) for s in selectors}
def select_intervals(report,selectors):
    e=report['evaluation'];forecasts={(r.get('horizon'),r.get('group')):r for r in e['forecast']['rows']}
    return {s['name']:(interval(e['functionals'][s['key']])[0] if s['kind']=='functional' else interval(forecasts[(s['horizon'],s.get('group'))],True)[0]) for s in selectors}


def normalize_cell(manifest,cell,*,shared_context=None):
    """shared_context is an internal seam; records remain provisional until cohort finish."""
    procedure=manifest['procedure'];out=Path(cell['output_directory']);public=procedure['worker_kind']=='public'
    mixed_reference=not public and procedure.get('implementation')=='associative'
    modern=public or mixed_reference
    filename='python-pymc-flow-report.json' if manifest['model']=='flow' else 'python-pymc-report.json'
    rp=out/(filename if public else 'report.json' if mixed_reference else 'numpyro-continuation-report.json')
    record={k:cell[k] for k in ['id','model','arm','procedure_sha256','dataset_seed','source_sha256','fixture_sha256','truth']}
    record.update(protocol_sha256=manifest['protocol_sha256'],provenance_valid=False,usable=False,intervals={},original_report_sha256=None,normalization=dict(phase='prospective_component_evidence',qualified=False,errors=[],tier_checks=[],artifact_sha256={}))
    if shared_context is not None:record['shared_validation_provisional']=True
    evidence=record['normalization'];cost={};record['cost']=cost
    def read(path):
        evidence['artifact_sha256'][str(path)]=digest(path);return load(path)
    # Preserve available consumed cost even if a later binding is invalid.
    for key,path in [('controller_seconds',cell['status_path']),('wrapper_seconds',cell['hardware_path'])]:
        try:cost[key]=load(path).get('elapsed_seconds')
        except (OSError,ValueError):cost[key]=None
    def shared_check(message):
        if shared_context is None:
            for path,expected in procedure['bound_files'].items():require(digest(path)==expected,message+': '+path)
        else:
            from cohort_validation import POLICY
            require(shared_context.policy==POLICY,'Unsupported shared validation policy')
            shared_context.require(procedure['bound_files'])
    def failure(classification):
        shared_check('Post-failure source/build drift')
        require(digest(cell['fixture_path'])==cell['fixture_sha256'],'Post-failure fixture drift')
        record['provenance_valid']=True
        record['failure_evidence']=dict(classification=classification,
            status_sha256=digest(cell['status_path']),hardware_sha256=digest(cell['hardware_path']),started_sha256=digest(cell['started_path']),
            **{k:record[k] for k in ['protocol_sha256','procedure_sha256','fixture_sha256','dataset_seed']})
        evidence['errors'].append(classification)
        if shared_context is not None:
            record['shared_validation_pending_flags']=dict(usable=record['usable'],provenance_valid=record['provenance_valid'])
            record['usable']=False;record['provenance_valid']=False
        return record
    try:
        require(object_digest(procedure)==manifest['procedure_sha256'],'Procedure digest mismatch')
        require(procedure['worker_kind'] in ['public','reference'] and procedure['chains']==4 and procedure['warmup']>0,'Invalid worker procedure')
        if 'implementation' in procedure:
            require(mixed_reference and manifest['model']=='flow' and procedure['coordinates']=='mixed_slopes' and procedure['worker_arm']=='numpyro-mixed-slopes-continuation','Unsupported explicit reference implementation')
        tiers=procedure['tiers'];require(tiers and all(isinstance(v,int) and not isinstance(v,bool) and v>0 for v in tiers) and all(a<b for a,b in zip(tiers,tiers[1:])),'Invalid retained tiers')
        require(finite(procedure['relative_mcse']) and 0<procedure['relative_mcse']<1,'Invalid precision threshold')
        require(bool(procedure['bound_files']) and bool(procedure['runtime_bindings']),'Empty build/runtime binding')
        frozen=normalized(procedure['bound_files']);runtime=normalized(procedure['runtime_bindings'])
        require(all(frozen.get(k)==v for k,v in runtime.items()),'Runtime files not frozen')
        source=normalized(cell['source_sha256']) if public else normalized({str(Path(procedure['study_directory'])/k):v for k,v in cell['source_sha256'].items()})
        require(all(frozen.get(k)==v for k,v in source.items()),'Worker sources not frozen')
        shared_check('Bound source/build drift')
        fixture=read(cell['fixture_path']);require(digest(cell['fixture_path'])==cell['fixture_sha256'],'Fixture hash mismatch')
        require(fixture.get('seed')==cell['dataset_seed'],'Dataset seed mismatch')
        contract=fixture_contract(fixture,manifest['model']);truth=select_truth(contract,manifest['selectors'])
        require(truth==cell['truth'],'Manifest truth differs from separately verified fixture');record['truth']=truth
        marker=read(cell['started_path'])
        for key in ['protocol_sha256','procedure_sha256','fixture_sha256','dataset_seed']:
            expected=manifest[key] if key in ['protocol_sha256','procedure_sha256'] else cell[key]
            require(marker.get(key)==expected,'Missing prospective start binding: '+key)
        status=read(cell['status_path']);hardware=read(cell['hardware_path'])
        cost.update(controller_seconds=status.get('elapsed_seconds'),wrapper_seconds=hardware.get('elapsed_seconds'))
        require(all(finite(v) and v>0 for v in cost.values()) and cost['controller_seconds']>=cost['wrapper_seconds'],'Invalid charged invocation cost')
        require(status.get('hardware_sha256')==digest(cell['hardware_path']),'Hardware hash mismatch')
        require(hardware.get('job_active_processes_after_cleanup')==0 and hardware.get('realized_cpus')==procedure['cpus'],'Containment/affinity failure')
        require(status.get('returncode')==hardware.get('returncode'),'Exit-code mismatch')
        require(hardware.get('command')==cell['worker_command'],'Actual worker command differs from intended procedure')
        require(hardware.get('containment',{}).get('assigned_before_worker_execution') is True,'Worker containment not established before execution')
        if rp.exists():record['original_report_sha256']=digest(rp)
        if hardware.get('status')=='worker-timeout':
            require(status.get('returncode')==124 and cost['wrapper_seconds']>=procedure['timeout_seconds'],'Timeout accounting mismatch')
            return failure('budgeted_computational_timeout')
        if not rp.exists():return failure('missing_report')
        report=read(rp);require(status.get('report_sha256')==record['original_report_sha256'],'Report hash mismatch')
        if report.get('status')=='failed':
            require(isinstance(report.get('error'),str) and bool(report['error']) and isinstance(report.get('attempts',[]),list),'Malformed worker exception report')
            if modern:
                require(report.get('seed')==cell['chain_seed'] and report.get('arm')==procedure['worker_arm'],'Failed public identity mismatch')
                actual=normalized(report['bindings']);expected=dict(source);expected.update(runtime);expected[str(Path(cell['fixture_path']).resolve()).casefold()]=cell['fixture_sha256']
                require(all(actual.get(k)==v for k,v in expected.items()),'Failed public source/runtime mismatch')
                for key in ['chains','warmup','target_accept','block_size']:
                    if key in procedure:require(report.get('settings',{}).get(key)==procedure[key],'Failed public setting mismatch')
                if mixed_reference:
                    require(report.get('implementation')=='associative' and report.get('coordinates')=='mixed_slopes','Failed mixed reference implementation mismatch')
                    require(report['settings'].get('implementation')=='associative' and report['settings'].get('batch')==procedure['batch_size'] and report['settings'].get('tiers')==tiers,'Failed mixed reference policy mismatch')
            else:
                failed_plan=report['plan']
                require(failed_plan.get('model')==manifest['model'] and failed_plan.get('arm')==procedure['worker_arm'] and failed_plan.get('seed')==cell['chain_seed'] and failed_plan.get('coordinates')==procedure['coordinates'],'Failed reference plan identity mismatch')
                require(failed_plan.get('source_sha256')==cell['source_sha256'] and failed_plan.get('fixture_sha256')==cell['fixture_sha256'] and failed_plan.get('tiers')==procedure['tiers'],'Failed reference source/fixture/tier mismatch')
                for key in ['chains','warmup','target_accept','batch_size']:
                    if key in procedure:require(failed_plan.get(key)==procedure[key],'Failed reference setting mismatch')
            return failure('worker_failed')
        require(report.get('seed')==cell['chain_seed'] and report.get('arm')==procedure['worker_arm'] and report.get('coordinates')==procedure['coordinates'],'Worker identity mismatch')
        settings=report['settings']
        for key in ['chains','warmup','target_accept','block_size']:
            if key in procedure:require(settings.get(key)==procedure[key],'Worker setting mismatch: '+key)
        if modern:
            actual=normalized(report['bindings']);expected=dict(source);expected.update(normalized(procedure['runtime_bindings']));expected[str(Path(cell['fixture_path']).resolve()).casefold()]=cell['fixture_sha256']
            require(all(actual.get(k)==v for k,v in expected.items()),'Public source/runtime mismatch')
            require(close_matrix(report['initial_positions'],contract['starts']),'Report canonical start mismatch')
            require(report.get('predictive_seed')==cell['chain_seed']+130000,'Predictive seed mismatch')
            require(report.get('parity',{}).get('passed') is True,'Target parity missing/failed')
            if mixed_reference:
                require(report.get('implementation')==settings.get('implementation')=='associative','Mixed reference implementation mismatch')
                require(settings.get('batch')==procedure['batch_size'] and settings.get('tiers')==tiers,'Mixed reference policy mismatch')
        else:require(report.get('source_sha256')==cell['source_sha256'] and report.get('fixture_sha256')==cell['fixture_sha256'],'Reference source/fixture mismatch')
        if report.get('status')!='completed':return failure('worker_failed')
        attempts=report['attempts'];counts=[a['draws'] for a in attempts]
        require(counts and counts==tiers[:len(counts)],'Non-prefix retained tiers')
        gates=[];previous_checkpoints=[]
        for attempt in attempts:
            n=attempt['draws'];fp=out/(f'draws-{n}/fit-report.json' if public else f'draws-{n}-report.json')
            fit=read(fp);require((fit.get('draws') if modern else fit.get('settings',{}).get('draws'))==n,'Tier report retained count mismatch');g=gate(fit,contract,procedure['relative_mcse']);gates.append(g)
            require(g['passed']==attempt['screen']['pass'],'Stored tier gate disagrees with recomputation')
            require(set(attempt['screen']['parameter_functionals'])==set(contract['names']) and attempt['screen']['forecast_rows']==len(contract['forecasts']) and attempt['screen']['threshold']==procedure['relative_mcse'],'Stored screen scope mismatch')
            evidence['tier_checks'].append(dict(draws=n,**g))
            if mixed_reference:
                from asof_rolling_execute import validate_checkpoint_continuity
                require(procedure['batch_size']==1000,'Unsupported mixed reference checkpoint batch')
                checkpoints=fit['checkpoints'];validate_checkpoint_continuity(checkpoints)
                require(len(checkpoints)==n//1000 and checkpoints[:len(previous_checkpoints)]==previous_checkpoints,'Mixed reference checkpoint prefix differs')
                previous_checkpoints=checkpoints
            if modern or n==counts[-1]:
                raw=(out/f'draws-{n}'/('python-pymc-flow-raw.json' if manifest['model']=='flow' else 'python-pymc-raw.json') if public else out/f'draws-{n}-raw.json' if mixed_reference else out/'numpyro-continuation-raw.json')
                require(close_matrix(raw_tail(raw,'initial_positions'),contract['starts']),'Raw canonical starts mismatch')
                if mixed_reference:
                    import numpy as np
                    from flow_mixed_coordinates import to_mixed
                    expected_starts=to_mixed(np.asarray(contract['starts']),fixture['data']).tolist()
                    require(raw_tail(raw,'sampling_initial_positions')==expected_starts and report.get('sampling_initial_positions')==expected_starts,'Mixed reference sampling starts differ')
                    evidence['artifact_sha256'][str(raw)]=digest(raw)
        require(not any(g['passed'] for g in gates[:-1]) and (gates[-1]['passed'] or counts[-1]==tiers[-1]),'Not the frozen first-pass/cap procedure')
        require(gate(report,contract,procedure['relative_mcse'])==gates[-1] and report.get('precision_pass')==gates[-1]['passed'],'Final gate mismatch')
        if mixed_reference:
            require(report.get('draws')==counts[-1] and all(report.get(k)==fit.get(k) for k in ['evaluation','retained_divergences','checkpoints']),'Mixed reference final selected output differs')
        inv=read(out/'invocation-timing.json');worker=next(v for k,v in inv.items() if k.startswith('seconds_'));cost['worker_seconds']=worker
        require(finite(worker) and cost['wrapper_seconds']>=worker>=report['end_to_end_seconds'],'Worker cost enclosure failure')
        if public:
            metadata=report['adapted_metadata'];base=report['warmup_target_calls']
            for attempt in attempts:
                n=attempt['draws'];raw=out/f'draws-{n}'/('python-pymc-flow-raw.json' if manifest['model']=='flow' else 'python-pymc-raw.json')
                require(raw_tail(raw,'adapted_metadata')==metadata,'Adaptation changed across retained tiers')
                base+=attempt['added_target_calls'];require(base==attempt['cumulative_target_calls'],'Cumulative callback mismatch')
            require(base==report['total_target_calls'],'Total callback mismatch')
            require(math.isclose(report['total_sampling_seconds'],report['adapt_seconds']+sum(a['sampling_seconds'] for a in attempts),rel_tol=1e-12,abs_tol=1e-7),'Sampling-stage cost mismatch')
        else:
            checkpoints=report['checkpoints'];batch=procedure['batch_size']
            require([c['draws_per_chain'] for c in checkpoints]==list(range(batch,counts[-1]+1,batch)) and len({c['adaptation_sha256'] for c in checkpoints})==1,'Reference continuation state/batches mismatch')
            require(report['end_to_end_seconds']>=report['adapt_seconds' if mixed_reference else 'warmup_seconds']+sum(c['seconds'] for c in checkpoints),'Reference stage cost enclosure failure')
            if mixed_reference:
                require(math.isclose(report['total_sampling_seconds'],report['adapt_seconds']+sum(a['sampling_seconds'] for a in attempts),rel_tol=1e-12,abs_tol=1e-7),'Mixed reference sampling-stage cost mismatch')
        record['intervals']=select_intervals(report,manifest['selectors']);evidence['selected_draws']=counts[-1]
        record['usable']=gates[-1]['passed'] and status.get('returncode')==0 and hardware.get('status')=='completed'
        if not record['usable']:evidence['errors'].append('production health/precision/exit failed')
        shared_check('Post-read source/build drift')
        require(digest(cell['fixture_path'])==cell['fixture_sha256'] and digest(rp)==record['original_report_sha256'],'Post-read fixture/report drift')
        record['provenance_valid']=True
    except (KeyError,TypeError,ValueError,OSError,StopIteration,OverflowError) as exc:
        record['usable']=False;record['provenance_valid']=False;evidence['errors'].append(f'{type(exc).__name__}: {exc}')
    for key,value in list(cost.items()):
        if value is not None and not finite(value):cost[key]=None
    if shared_context is not None:
        record['shared_validation_pending_flags']=dict(usable=record['usable'],provenance_valid=record['provenance_valid'])
        record['usable']=False;record['provenance_valid']=False
    return record


def normalize(manifest):
    validate_manifest(manifest)
    return [normalize_cell(manifest,c) for c in manifest['cells']]
def write_records(path,records):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(records,f,indent=2,allow_nan=False)


def normalize_shared(manifests,*,policy,expected_inventory,inventory):
    """Explicit opt-in cohort transaction; legacy normalize() is unchanged.

    Whole-cohort shared drift invalidates every returned record. This validates
    pre/post content, not every legacy intermediate observation instant.
    Historical manifests/archived source paths must not be silently rewritten.
    """
    from cohort_validation import POLICY,normalize_cohort
    if policy!=POLICY:raise ValueError('Explicit supported cohort policy required')
    manifests=list(manifests);cells=[];owners={}
    for manifest in manifests:
        validate_manifest(manifest)
        for original in manifest['cells']:
            if original['id'] in owners:raise ValueError('Duplicate intended cohort IDs')
            owners[original['id']]=manifest;cell=dict(original);cell['known_cost']={}
            cell['record_template']={k:cell[k] for k in ['id','model','arm','procedure_sha256','dataset_seed','source_sha256','fixture_sha256','truth']}
            cell['record_template'].update(protocol_sha256=manifest['protocol_sha256'],intervals={},original_report_sha256=None,normalization=dict(phase='prospective_component_evidence',qualified=False,errors=[],tier_checks=[],artifact_sha256={}))
            for key,path in [('controller_seconds',cell['status_path']),('wrapper_seconds',cell['hardware_path'])]:
                try:
                    value=load(path).get('elapsed_seconds');cell['known_cost'][key]=value if finite(value) else None
                except (OSError,ValueError,TypeError):cell['known_cost'][key]=None
            cells.append(cell)
    return normalize_cohort(cells,[m['procedure']['bound_files'] for m in manifests],lambda cell,ctx:normalize_cell(owners[cell['id']],cell,shared_context=ctx),inventory,expected_inventory)
