"""Resolve admission metadata after successful literal readiness; never authorize generation."""
import argparse,hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def resolve(pending,literal,readiness,output):
    p=Path(pending);r=Path(readiness);spec=json.loads(p.read_text());proof=json.loads(r.read_text())
    literal_spec=json.loads(Path(literal).read_text());comparison=dict(literal_spec);comparison['status']='frozen_pending_authorization'
    if literal_spec.get('status')!='literal_readiness_authorized' or comparison!=spec:raise ValueError('Literal manifest differs beyond admission status')
    if spec['status']!='frozen_pending_authorization':raise ValueError('Expected pending production manifest')
    if proof.get('readiness_complete') is not True or proof.get('group_drained') is not True or proof.get('manifest_unchanged') is not True:raise ValueError('Successful drained literal readiness required')
    study=Path(spec['dependencies']['resident_adapter']).parents[1]/'long_horizon_k400_v1';reservation=study/'SEED-RESERVATIONS.json';scan=study/'SEED-SOURCE-AUDIT.json'
    for source in (reservation,scan):
        if sha(source)!=spec['sources'][str(source)]:raise ValueError('Seed inventory/source audit drift')
    protocol=spec['protocol'];protocol['status']='reviewed_pending_top_level_authorization';protocol.pop('generation_authorized',None);protocol['generation_admission']='Only top-level status frozen_authorized admits production workers; pending and literal-only manifests cannot generate study data.'
    protocol['seed_audit']=dict(reservation_sha256=sha(reservation),bounded_source_audit_sha256=sha(scan),scope='Explicit reserved raw/derived inventories plus bounded source/metadata search; not universal collision proof')
    protocol['runtime_bindings']=dict(authoritative_manifest_field='runtime',runtime_identity_sha256=hashlib.sha256(json.dumps(spec['runtime'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
    spec['provenance']['admission_resolution']=dict(prior_pending_sha256=sha(p),literal_manifest_sha256=sha(literal),literal_supervision_sha256=sha(r),resolver_sha256=sha(__file__))
    with Path(output).open('x') as f:json.dump(spec,f,indent=2);f.write('\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pending');p.add_argument('literal');p.add_argument('readiness');p.add_argument('output');a=p.parse_args();resolve(a.pending,a.literal,a.readiness,a.output)
