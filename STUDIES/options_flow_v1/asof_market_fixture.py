"""As-of replay fixtures for the audited fixed-universe trade panel.

No execution or acquisition. Event timestamps plus assumed lag are not receipts.
"""
import math
from market_flow_features import digest_json, milliseconds
from masked_market_comparison_plan import dispersed_starts


def prepare(panel, protocol, *, origin_index, window, init_seed):
    if panel.get('protocol_sha256') != digest_json(protocol) or not panel.get('acquisition_binding'):
        raise ValueError('Audited acquisition and exact protocol binding required')
    names=panel['instruments']
    if len(names)!=4 or len(set(names))!=4 or protocol['contracts']!=4:
        raise ValueError('Fixed four-contract universe required')
    if type(window) is not int or window<2 or type(origin_index) is not int or origin_index<window:
        raise ValueError('At least two strict pre-origin rows required')
    if type(init_seed) is not int or not 0<=init_seed<2**32:
        raise ValueError('Explicit uint32 initialization seed required')
    f=protocol['forecast']; stride=f['origin_stride_minutes']*60000
    lag=f['availability_lag_seconds']*1000; horizon=f['horizon_minutes']*60000
    if (stride,lag,horizon,f['feature_bin_minutes'])!=(1800000,60000,1800000,15):
        raise ValueError('Unsupported time contract')
    records=panel['records']; selected=[r for r in records if origin_index-window<=r['grid_index']<=origin_index]
    if [r['grid_index'] for r in selected]!=list(range(origin_index-window,origin_index+1)):
        raise ValueError('Complete consecutive grid required')
    current=selected[-1]; issuance=current['decision_ms']
    selection_end=milliseconds(protocol['start_utc'])+protocol['selection_hours']*3600000
    if not current['selection_available'] or issuance<selection_end:
        raise ValueError('Universe unavailable at issuance')
    if not current['stabilizer_available'] or issuance<panel['stabilizer']['estimated_through_ms']:
        raise ValueError('Stabilizer unavailable at issuance')
    for j,row in enumerate(selected):
        if row['decision_ms']!=issuance-(window-j)*stride or row['cutoff_ms']+lag!=row['decision_ms'] or row['target_end_ms']!=row['decision_ms']+horizon:
            raise ValueError('Time gaps or inconsistent clock')
        if [g['instrument_name'] for g in row['groups']]!=names:
            raise ValueError('Universe/order changed')
        for g in row['groups']:
            if g['feature_available_ms']!=row['decision_ms'] or g['target_available_ms']!=row['target_end_ms']+lag:
                raise ValueError('Inconsistent feature/target availability')
            if g['x_available'] and (g['x'] is None or not math.isfinite(g['x'])):
                raise ValueError('Available feature must be finite')
    x=[];y=[];mask=[]
    for row in selected[:-1]:
        m=[bool(g['x_available'] and g['observation_mask'] and g['target_available_ms']<=issuance) for g in row['groups']]
        if any(keep and (g['y'] is None or not math.isfinite(g['y'])) for g,keep in zip(row['groups'],m)):
            raise ValueError('Mature observed outcome must be finite')
        x.append([g['x'] if g['x_available'] else 0. for g in row['groups']])
        y.append([g['y'] if keep else 0. for g,keep in zip(row['groups'],m)]);mask.append(m)
    available=[bool(g['x_available']) for g in current['groups']]
    if not any(available):raise ValueError('No current flow features available')
    data=dict(x=x,y=y,observation_mask=mask,grid_index=list(range(window)),rho=.95,nu=5.)
    data['initial_positions']=dispersed_starts(window,4,.95,init_seed)
    return dict(data=data,holdout=dict(x=[[g['x'] if g['x_available'] else 0. for g in current['groups']]],
        y=[[None]*4],observation_mask=[[False]*4],x_available=[available],grid_index=[window]),
        source='real',prior_predictive=False,qualified=False,
        precision_family=[[1,g] for g,yes in enumerate(available) if yes],
        provenance=dict(protocol_sha256=panel['protocol_sha256'],acquisition_binding=panel['acquisition_binding'],
            selection_sha256=panel.get('selection_sha256'),selection_binding='Acquisition manifest binds selection file; optional normalized selection digest retained',
            instruments=names,origin_index=origin_index,issuance_ms=issuance,original_grid_indices=[r['grid_index'] for r in selected[:-1]],
            init_seed=init_seed,stabilizer=panel['stabilizer'],phase_purge='Retain existing protocol observation masks across phase boundaries; no history reset'),
        forecast_contract='Current known flow only; strict pre-origin latent grid including immature rows; one AR step and Student-t observed outcome noise.',
        units=dict(x='signed basecoin amount / (total basecoin amount + frozen stabilizer)',y='native-quote trade-price log return',scaling='None; original model priors in these raw units'),
        limitations=['Conditional on eligible future trade arrival; missingness not modeled.',
                    'Historical event-time plus assumed60sec lag, not verified receipt-time availability.',
                    'Retrospective replay using universe/stabilizer available by issuance; not live execution.'])


def delayed_scores(fixture,panel,*,as_of_ms):
    """Return labels separately, never mutate inference inputs or precision family."""
    p=fixture['provenance']
    if panel['protocol_sha256']!=p['protocol_sha256'] or panel['acquisition_binding']!=p['acquisition_binding'] or panel['instruments']!=p['instruments'] or panel.get('selection_sha256')!=p['selection_sha256']:
        raise ValueError('Scoring panel binding differs')
    rows=[r for r in panel['records'] if r['grid_index']==p['origin_index']]
    if len(rows)!=1 or rows[0]['decision_ms']!=p['issuance_ms']:raise ValueError('Scoring origin mismatch')
    if type(as_of_ms) is not int or any(g['target_available_ms']>as_of_ms for g in rows[0]['groups']):
        raise ValueError('Scoring requested before label maturity')
    result=[]
    for j,g in enumerate(rows[0]['groups']):
        if g['y_available'] and (g['y'] is None or not math.isfinite(g['y'])):
            raise ValueError('Available scoring label must be finite')
        purged=bool(g.get('phase_boundary_purged',False))
        eligible=bool(g['observation_mask'] and not purged and g['y_available'])
        result.append(dict(horizon=1,group=j,observed=g['y'] if eligible else None,
            target_observed=bool(g['y_available']),scoring_eligible=eligible,
            protocol_observation_mask=bool(g['observation_mask']),phase_boundary_purged=purged,
            scoring_policy='Only mature observed labels admitted by original protocol mask and phase purge',
            forecast_available=fixture['holdout']['x_available'][0][j]))
    return result
