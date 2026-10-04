import json,tempfile,unittest
from pathlib import Path
from continuation_comparison import validate_worker,validate_raw_starts,command
class ComparisonTests(unittest.TestCase):
    def test_continuation_bindings_and_failed_terminal(self):
        root=Path.cwd();source=str(root/'x.py');fixture=str(root/'fixture.json');att=str(root/'att.json')
        plan=dict(study_bindings={source:'s'},bound_files={att:'a'},attestation=att)
        cell=dict(arm='owalnuts_continuation',seed=1,fixture=fixture,fixture_sha256='f',starts=[[1.]])
        report=dict(seed=1,coordinates='observation_residual',settings={'warmup':1000,'chains':4},bindings={source:'s',fixture:'f'},initial_positions=[[1.]],status='failed')
        self.assertFalse(validate_worker(plan,cell,report))
        report['initial_positions']=[[2.]]
        with self.assertRaises(ValueError):validate_worker(plan,cell,report)
        report['initial_positions']=[[1.]];report['bindings'][source]='drift'
        with self.assertRaises(ValueError):validate_worker(plan,cell,report)
    def test_raw_start_shape(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'raw.json';p.write_text(json.dumps({'initial_positions':[[1.,2.]]}))
            validate_raw_starts(p,[[1.,2.]])
            with self.assertRaises(ValueError):validate_raw_starts(p,[[1.]])
    def test_command_budget_and_reference_acceptance(self):
        args=command({'python':'python'},{'id':'x','fixture':'f','seed':1,'arm':'numpyro_continuation'},Path('out/x'))
        self.assertEqual(args[args.index('--timeout')+1],'600');self.assertEqual(args[args.index('--target-accept')+1],'0.9')


class AttestationAndGateTests(unittest.TestCase):
    def test_unattested_build_rejected(self):
        from unittest.mock import patch
        import continuation_comparison as c
        with patch.object(c,'load',side_effect=[{'status':'failed','manifest_path':'m'},{'status':'attested'}]):
            with self.assertRaises(ValueError):c.attested_dependencies('a','python','pkg')
    def test_per_tier_health_and_precision_gate(self):
        from copy import deepcopy
        from continuation_comparison import fit_gate
        names=['h_initial','h_terminal','h_mean','sigma_obs','sigma_rw']
        d=dict(rhat=1.,bulk_ess=500.,tail_ess=500.)
        e=dict(chain_count=4,functionals={k:dict(d,interval_90=[0.,1.],endpoint_mcse=[.01,.01]) for k in names},canonical_parameter_diagnostics={str(i):dict(d) for i in range(130)},forecast={'rows':[{'lower':0.,'upper':1.,'endpoint_mcse':[.01,.01]}]})
        fit=dict(evaluation=e,retained_divergences=0);self.assertTrue(fit_gate(fit))
        bad=deepcopy(fit);bad['retained_divergences']=1;self.assertFalse(fit_gate(bad))
        bad=deepcopy(fit);bad['evaluation']['canonical_parameter_diagnostics']['129']['bulk_ess']=2.;self.assertFalse(fit_gate(bad))
        bad=deepcopy(fit);bad['evaluation']['forecast']['rows'][0]['endpoint_mcse']=[.03,.01];self.assertFalse(fit_gate(bad))

if __name__=='__main__':unittest.main()
