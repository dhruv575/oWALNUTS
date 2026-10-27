"""Artifact integrity/completeness independent of favorable scientific outcomes."""
import json
from pathlib import Path
from evidence import digest
from ledger import build_ledger,sentinel_ledger

def validate(root,source_bindings):
    root=Path(root);errors=[];checked=0
    for name,want in source_bindings.items():
        if digest(name)!=want:errors.append('source:'+name)
    for stream in range(32):
        directory=root/f'stream-{stream:02d}'
        data=directory/'data.json'
        if data.exists():
            d=json.loads(data.read_text())
            if d['stream']!=stream:errors.append('stream_identity')
            for item in d['files'].values():
                checked+=1
                if digest(directory/item['file'])!=item['sha256']:errors.append('data_hash')
        candidate=directory/'candidate.json'
        if candidate.exists():
            value=json.loads(candidate.read_text())
            if value['stream']!=stream:errors.append('candidate_stream_identity')
            for row in value.get('rows',[]):
                for key in ['compact','score_arrays']:
                    if key in row:
                        checked+=1
                        if digest(directory/row[key]['file'])!=row[key]['sha256']:errors.append(key+'_hash')
                    elif row.get('candidate_status')=='ok':errors.append('missing_'+key)
    ledger=build_ledger(root);sentinels=sentinel_ledger(root)
    for entry in sentinels:
        r=entry.get('result') or {}
        if r.get('candidate_integrity_error'):errors.append('candidate_reference_comparison_integrity')
        if r and any(r.get(k)!=entry[k] for k in ('index','stream','tick')):errors.append('reference_identity')
        for key in ('compact','score_arrays'):
            if key in r:
                p=root/f"sentinel-{entry['index']:02d}"/r[key]['file'];checked+=1
                if digest(p)!=r[key]['sha256']:errors.append('reference_'+key+'_hash')
            elif r.get('status')=='complete':errors.append('missing_reference_'+key)
    campaign=json.loads((root/'campaign.json').read_text())
    planned={(k,i) for k,n in [('candidate',32),('sides',32),('reference',8),('report',1)] for i in range(n)}
    ids=[(x['kind'],x['id']) for x in campaign['jobs']]
    if len(ids)!=len(planned) or set(ids)!=planned:errors.append('job_denominator')
    if any(x['status']=='running' for x in campaign['jobs']):errors.append('unfinished_job')
    if any(x.get('group_drained') is False for x in campaign['jobs']):errors.append('undrained_job')
    return dict(evidence_complete=not errors,checked_artifact_hashes=checked,planned_origins=len(ledger),planned_sentinels=len(sentinels),errors=errors,qualification=None)
