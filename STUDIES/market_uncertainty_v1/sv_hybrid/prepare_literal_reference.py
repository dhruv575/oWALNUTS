"""Freeze the literal reference manifest on the existing AWS research runtime."""
import argparse
import json
from pathlib import Path
import shutil
from literal_reference import sha, validate, write


def prepare(root, parent):
    root=Path(root).resolve(); parent=Path(parent).resolve()
    previous=json.loads(parent.read_bytes())
    reference=previous['reference']
    shutil.copyfile(parent,root/'RUNTIME-PARENT.json')
    paths=dict(worker=root/'literal_reference.py', monitor=root/'resource_monitor.py',
               stan=Path(reference['stan_path']), capture=Path(reference['capture_path']),
               adapter=Path('/home/ubuntu/lanes/prior-predictive-validation-20261027/source/STUDIES/prior_predictive_validation_v1/sentinel_adapter.py'),
               sdk_makefile=Path(reference['bridgestan_sdk'])/'Makefile',
               runtime_inventory=root/'RUNTIME-PARENT.json')
    if sha(paths['stan'])!=reference['stan_sha256'] or sha(paths['sdk_makefile'])!=reference['sdk_makefile_sha256']:
        raise ValueError('Inherited target/compiler binding mismatch')
    audit=root/'SEED-AUDIT.json'
    spec=dict(status='frozen_authorized',scope='Literal specialist reference readiness; no market or economic claim',
              bindings={name:dict(path=str(path),sha256=sha(path)) for name,path in paths.items()},
              sampling=dict(chains=4,draws=4000,tune=2000,cores=4),
              limits=dict(seconds=900,rss_bytes=4*1024**3,output_bytes=512*1024**2),
              seed=704028000,seed_audit=dict(path=str(audit),sha256=sha(audit),reserved_seeds=[704028000,704028001]),
              reference_settings=reference,
              comparator_archive_sha256='809141a9462552773ca48a0fb175984f41c86f7754a2f5422925ad66c219c844',
              comparator_scope='All eight existing T250 specialist chains, no reruns or selection',
              preparer_sha256=sha(__file__))
    validate(spec)
    write(root/'MANIFEST.json',spec)
    return dict(status='frozen',manifest_sha256=sha(root/'MANIFEST.json'),sampling_started=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('parent');a=p.parse_args()
    print(json.dumps(prepare(a.root,a.parent)))
