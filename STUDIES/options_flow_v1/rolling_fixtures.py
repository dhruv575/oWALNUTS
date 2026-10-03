"""Create operational one-step rolling-origin fixtures from availability-stamped CSV.

Each fit has its own training-only scaling and exactly one future outcome row per
group. The future flow feature must already be available at that forecast origin.
This prepares immutable inputs; it does not verify data authenticity or qualify
forecast performance.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from ingest import ingest,timestamp


def prepare(source,metadata,out,window,step=1):
    if window<2 or step<1:raise ValueError('window>=2 and step>=1 required')
    source=Path(source);raw=source.read_bytes()
    reader=csv.DictReader(raw.decode('utf-8-sig').splitlines())
    fields=reader.fieldnames;rows=list(reader)
    if not rows:raise ValueError('Empty source')
    origins=sorted({timestamp(r['origin']) for r in rows})
    if len(origins)<=window:raise ValueError('Insufficient history for a held-out forecast')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    entries=[]
    for i in range(window,len(origins),step):
        directory=out/f'origin-{i:06d}';directory.mkdir()
        selected=set(origins[i-window:i+1]);panel=directory/'panel.csv'
        with panel.open('w',newline='',encoding='utf-8') as h:
            writer=csv.DictWriter(h,fieldnames=fields);writer.writeheader()
            writer.writerows(r for r in rows if timestamp(r['origin']) in selected)
        fixture=ingest(panel,metadata,window)
        # The input adapter checks available<=row origin. For a one-step forecast
        # this includes the current future x at exactly the issuance timestamp.
        fixture['forecast_contract']='One-step rolling origin: current x available at issuance; training outcomes available by issuance; future y withheld.'
        fixture['provenance'].update(parent_csv_sha256=hashlib.sha256(raw).hexdigest(),
            forecast_origin=origins[i].isoformat(),window_periods=window,
            authenticity='User-declared metadata; not independently verified')
        path=directory/'fixture.json'
        path.write_text(json.dumps(fixture,indent=2,allow_nan=False),encoding='utf-8')
        entries.append({'id':directory.name,'forecast_origin':origins[i].isoformat(),
                        'fixture':str(path.resolve()),'fixture_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest={'schema':'rolling-origin-fixtures-v1','source_sha256':hashlib.sha256(raw).hexdigest(),
              'window':window,'step':step,'expected':entries,'qualified':False,
              'dependence':'Training windows overlap; evaluate forecast errors in prespecified time blocks, not as iid rows.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


def no_flow(fixture):
    """Same outcomes/noise model with all flow predictors zero; an ablation, not SBC."""
    result=json.loads(json.dumps(fixture))
    for key in ('data','holdout'):
        if key in result:
            result[key]['x']=[[0. for _ in row] for row in result[key]['x']]
    result.pop('truth',None);result['prior_predictive']=False
    result['ablation']={'kind':'no_flow','method':'Zero flow covariate in training and prediction; same hierarchical noise/volatility model. Flow-slope priors remain nuisance dimensions.',
        'parent_fixture_sha256':hashlib.sha256(json.dumps(fixture,sort_keys=True,allow_nan=False).encode()).hexdigest(),
        'parent_hash_serialization':'Canonical JSON string sorted keys (not raw file bytes)'}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv',type=Path);p.add_argument('metadata',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--window',type=int,required=True);p.add_argument('--step',type=int,default=1)
    a=p.parse_args();result=prepare(a.csv,json.loads(a.metadata.read_text()),a.out,a.window,a.step)
    print(json.dumps({'origins':len(result['expected']),'qualified':False}))
