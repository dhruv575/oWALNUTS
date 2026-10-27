"""Offline binding to exact prior runtime/source identities and opaque acquisition hashes."""
import argparse,hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(bundle,remote,prior_e62,prior_e63,acquisition,output):
    bundle=Path(bundle);remote=remote.rstrip('/');old=json.loads(Path(prior_e62).read_bytes());long=json.loads(Path(prior_e63).read_bytes());inventory=json.loads((bundle/'BUNDLE-MANIFEST.json').read_bytes());sources=dict(old['sources'])
    if old['status']!='frozen_scoring_authorized' or long['status']!='frozen_authorized' or old['runtime']!=long['runtime']:raise ValueError('Prior admitted runtime mismatch')
    for p,want in long['sources'].items():
        if '/.bridgestan/' in p:
            if p in sources and sources[p]!=want:raise ValueError('SDK binding disagreement')
            sources[p]=want
    for name,want in inventory['files'].items():
        if sha(bundle/name)!=want:raise ValueError('Source bundle drift '+name)
        sources[remote+'/'+name]=want
    study=bundle/'STUDIES/market_replication_v1';ops=bundle/'STUDIES/market_replication_ops_v1';draft=json.loads((study/'COMPUTE-DRAFT.json').read_bytes());fixed=json.loads((ops/'OPS-DRAFT.json').read_bytes());reserved=json.loads((ops/'SEED-RESERVATIONS.json').read_bytes());audit=json.loads((ops/'SEED-SOURCE-AUDIT.json').read_bytes())
    if any(draft['bounds'].get(k)!=v for k,v in fixed['bounds'].items()) or draft['bounds']['score_call_seconds']!=5:raise ValueError('Reviewed bounds changed')
    if audit['inventory_sha256']!=sha(ops/'SEED-RESERVATIONS.json') or reserved['collisions']:raise ValueError('Seed audit not bound')
    for row,seeds in zip(draft['months'],reserved['months']):
        expected=dict(candidate=dict(initial=seeds['initial'],warm=seeds['warm']),references=[seeds['reference_base']+seeds['reference_stride']*i for i in range(8)],bootstrap=seeds['bootstrap'])
        if row['month']!=seeds['month'] or row['origins']!=seeds['updates'] or row['seeds']!=expected:raise ValueError('Month seed reservation mismatch')
    e62_root='/home/ubuntu/lanes/fresh-real-readiness-20261027/source02'
    for name,want in json.loads((study/'REUSE-IDENTITIES.json').read_bytes())['sources'].items():
        if old['sources'].get(e62_root+'/'+name)!=want:raise ValueError('E62 source identity mismatch '+name)
    if draft['reference']['engine_options']!=old['reference']['engine_options']:raise ValueError('Reference settings changed')
    acq=json.loads(Path(acquisition).read_bytes());directory=Path(acq['directory'])
    for name,key in [('terminal.json','terminal_sha256'),('protocol.json','protocol_sha256'),('bars.json','bars_sha256')]:
        if sha(directory/name)!=acq[key]:raise ValueError('Sealed input bytes changed '+name)
    if sha(acq['supervisor_final_path'])!=acq['supervisor_final_sha256']:raise ValueError('Acquisition admission identity changed')
    # Hash only: this binder never parses bars/returns or invokes a generator/model.
    acq['directory']=remote+'/acquisition';acq['supervisor_final_path']=remote+'/acquisition-supervisor-final.json'
    draft.update(status='frozen_scoring_pending_authorization',runtime=old['runtime'],python=old['python'],sources=sources,dependencies=old['dependencies'],reference=old['reference'],e62_root=e62_root,worker_path=remote+'/STUDIES/market_replication_v1/worker.py',ops_root=remote+'/STUDIES/market_replication_ops_v1',acquisition=acq,provenance=dict(prior_e62_manifest_sha256=sha(prior_e62),prior_e63_manifest_sha256=sha(prior_e63),bundle_inventory_sha256=sha(bundle/'BUNDLE-MANIFEST.json'),seed_reservation_sha256=sha(ops/'SEED-RESERVATIONS.json'),seed_source_audit_sha256=sha(ops/'SEED-SOURCE-AUDIT.json'),acquisition_bindings_sha256=sha(acquisition),binder_sha256=sha(__file__)))
    out=Path(output);out.mkdir(exist_ok=False)
    with (out/'PRODUCTION-PENDING.json').open('x') as f:json.dump(draft,f,indent=2);f.write('\n')
    dev=json.loads(json.dumps(draft));dev['status']='development_pending_authorization';dev['acquisition']=None
    for month in dev['months']:month['seeds']=dict(candidate=dict(initial=993711000,warm=993712000),references=[993713000]*8,bootstrap=17)
    dev['provenance']['scope']='Fixed literal engineering replay only; no acquisition path or production RNG'
    with (out/'READINESS-PENDING.json').open('x') as f:json.dump(dev,f,indent=2);f.write('\n')
    print(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file()}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--remote-root',required=True);p.add_argument('--prior-e62',required=True);p.add_argument('--prior-e63',required=True);p.add_argument('--acquisition',required=True);p.add_argument('--output',required=True);a=p.parse_args();bind(a.bundle,a.remote_root,a.prior_e62,a.prior_e63,a.acquisition,a.output)
