import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import prepare_local_residual_breadth as prepare


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        refs=[0,5,8,13,16,21]
        cells=[]
        for i in range(24):
            order=['candidate']
            if i in refs:order=['candidate','reference'] if refs.index(i)%2==0 else ['reference','candidate']
            cells.append(dict(index=i,dataset_seed=99780001+i,chain_seed=99810001+i,prediction_seed=99940001+i,execution_order=order))
        self.spec=dict(cells=cells,reference_indices=refs,candidate={'target_accept':.8},reference={'target_accept':.9},settings=dict(cpus=[0],chains=4,warmup=1000,retained_tiers=[1000,2000,4000,8000],batch_size=1000,timeout_seconds_per_worker=1800))
        self.path=self.root/'spec.json';self.path.write_text(json.dumps(self.spec))
        evidence=self.root/'source.txt';evidence.write_text('default acceptance 0.8')
        self.audit=dict(status='passed',spec_sha256=prepare.digest(self.path),seeds=sorted(c[k] for c in cells for k in ['dataset_seed','chain_seed','prediction_seed']),method='bounded seed manifest audit',audited_files={str(evidence):prepare.digest(evidence)})
        self.defaults=dict(target_accept=.8,explanation='test source establishes default',evidence_files={str(evidence):prepare.digest(evidence)})

    def test_evidence_rejects_unbound_incomplete_and_stale(self):
        prepare.check_evidence(self.path,self.spec,self.audit,self.defaults)
        for field,value in [('status','pending'),('spec_sha256','wrong'),('seeds',self.audit['seeds'][:-1]),('audited_files',{}),('method','')]:
            bad=dict(self.audit);bad[field]=value
            with self.assertRaises(ValueError):prepare.check_evidence(self.path,self.spec,bad,self.defaults)
        wrong=dict(self.defaults,target_accept=.9)
        with self.assertRaises(ValueError):prepare.check_evidence(self.path,self.spec,self.audit,wrong)
        Path(next(iter(self.defaults['evidence_files']))).write_text('mutated')
        with self.assertRaises(ValueError):prepare.check_evidence(self.path,self.spec,self.audit,self.defaults)

    def test_controlled_preparation_with_mocked_generator(self):
        # No real prior fixtures or sampling; tiny known y verifies transport.
        audit_path=self.root/'audit.json';audit_path.write_text(json.dumps(self.audit))
        default_path=self.root/'default.json';default_path.write_text(json.dumps(self.defaults))
        output=self.root/'prepared'
        argv=['prepare','--prepare','--spec',str(self.path),'--seed-audit',str(audit_path),'--default-attestation',str(default_path),'--out',str(output)]
        fixture=dict(data=dict(y=[.1,.2],dt=[1.],anchor=0.,anchor_mode='exogenous',nu=5.),truth=[0.,0.,-2.,-2.])
        with patch('sys.argv',argv),patch('local_level.simulate',side_effect=lambda *a,**k:copy.deepcopy(fixture)) as generator,contextlib.redirect_stdout(io.StringIO()):
            prepare.main()
        self.assertEqual(generator.call_count,24)
        self.assertEqual(generator.call_args.kwargs,dict(periods=128,holdout=1,prior=True,anchor=0.))
        plan=json.loads((output/'plan.json').read_text())
        self.assertTrue(plan['frozen']);self.assertEqual(len(plan['cells']),30)
        self.assertEqual((output/'plan.sha256').read_text().strip(),prepare.digest(output/'plan.json'))
        first=json.loads(Path(plan['cells'][0]['fixture']).read_text())
        self.assertEqual(len(first['data']['initial_positions']),4)
        self.assertAlmostEqual(first['data']['initial_positions'][0][0],.07)
        self.assertEqual(plan['candidate_default_attestation']['target_accept'],.8)
        self.assertIn('runtime_parity_policy',plan)
        with patch('sys.argv',argv),self.assertRaises(FileExistsError):prepare.main()


if __name__=='__main__':unittest.main()
