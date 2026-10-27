"""Bind development-only replay to existing E61 verified runtime; no sampling."""
import argparse,hashlib,json
from pathlib import Path
from linear_runner_snapshot import exclusive
from worker import admit

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    bundle=Path(args.bundle).resolve();inventory=json.loads((bundle/'READINESS-BUNDLE.json').read_bytes())
    for name,want in inventory['files'].items():
        if sha(bundle/name)!=want:raise ValueError('Bundle drift: '+name)
    prior=json.loads((bundle/'E61-MANIFEST-AUTHORIZED.json').read_bytes())
    if prior['status']!='frozen_authorized':raise ValueError('Prior runtime not admitted')
    draft=json.loads((bundle/'COMPUTE-DRAFT.json').read_bytes());base='/home/ubuntu/lanes/prior-predictive-validation-20261027/source/STUDIES/'
    draft.update(status='development_authorized',seeds=dict(candidate=dict(initial=993711000,warm=993712000),references=[993713000]*8,bootstrap=17),acquisition=None,
        python=prior['python_by_kind']['candidate'],runtime=prior['runtimes']['candidate'],
        dependencies=dict(resident_adapter=base+'prior_predictive_validation_v1/resident_adapter.py',target=prior['target_path'],predictive_density=prior['evaluator']['path'],independent_adapter=base+'prior_predictive_validation_v1/sentinel_adapter.py',compiler_capture=prior['reference']['capture_path']))
    if any(prior['runtimes'][kind]!=draft['runtime'] or prior['python_by_kind'][kind]!=draft['python'] for kind in ['reference','sides','report']):raise ValueError('Prior runtime disagreement')
    draft['reference']=dict(prior['reference'],sdk_path=prior['reference']['bridgestan_sdk'])
    # Verify the entire earlier source inventory once, including SDK sources.
    for path,want in prior['sources'].items():
        if sha(path)!=want:raise ValueError('Prior source drift: '+path)
    draft['sources']={path:want for path,want in prior['sources'].items() if path.endswith(('.py','.stan')) or path.endswith('/Makefile')}
    draft['sources'].update({str(bundle/name):want for name,want in inventory['files'].items()})
    draft['provenance']=dict(bundle_manifest_sha256=sha(bundle/'READINESS-BUNDLE.json'),prior_manifest_sha256=sha(bundle/'E61-MANIFEST-AUTHORIZED.json'),scope='Fixed literal engineering replay; acquisition absent; no production seed consumption')
    exclusive(Path(args.out),draft);admit(args.out,expected_status='development_authorized')

if __name__=='__main__':main()
