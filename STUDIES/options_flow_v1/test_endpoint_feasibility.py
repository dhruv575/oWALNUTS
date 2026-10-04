import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import endpoint_feasibility as study


class FeasibilityTests(unittest.TestCase):
    def test_commands_share_broad_stopping_family(self):
        plan=dict(python='python',cpus=[0],timeout_seconds=1800,local_coordinates='observation_residual')
        cell=dict(id='flow-00-candidate',arm='candidate',model='flow',fixture='fixture.json',streams={'sampler_seed':1})
        args,_,_=study.command(plan,cell,Path('output'))
        self.assertIn('--block-size',args);self.assertEqual(set(args[args.index('--precision-names')+1:]),set(study.FLOW_ALL))
        cell['arm']='reference';args,_,_=study.command(plan,cell,Path('output'))
        self.assertEqual(args[args.index('--target-accept')+1],'0.9')
        cell['model']='local_level';plan['local_coordinates']='conditional_whitening'
        for arm in ['candidate','reference']:
            cell['arm']=arm;args,_,_=study.command(plan,cell,Path('output'))
            self.assertEqual(args[args.index('--coordinates')+1],'conditional_whitening')

    def test_terminal_selection_and_start_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture=Path(directory)/'fixture.json';fixture.write_text(json.dumps({'data':{'initial_positions':[[1.]]}}))
            cell=dict(model='local_level',arm='reference',fixture=str(fixture),fixture_sha256='fixturehash',streams={'initialization_seed':2,'sampler_seed':3})
            screen=dict(pass_=False)
            attempts=[dict(draws=1000,screen={'pass':False,'parameter_functionals':study.PRIMARY['local_level'],'forecast_rows':1}),dict(draws=2000,screen={'pass':True,'parameter_functionals':study.PRIMARY['local_level'],'forecast_rows':1})]
            plan={'source_sha256':{},'local_coordinates':'observation_residual'}
            worker=dict(settings={'draws':2000,'warmup':1000,'chains':4,'target_accept':.9},attempts=attempts,precision_pass=True,
                arm='numpyro-continuation-observation-residual',seed=3,source_sha256={},fixture_sha256='fixturehash')
            with patch.object(study,'initial_positions',return_value=[[1.]]):
                binding=study.validate_terminal(plan,cell,worker,{'initial_positions':[[1.]]})
                self.assertEqual(binding['report_fields']['settings']['target_accept'],.9)
                with self.assertRaises(ValueError):study.validate_terminal(plan,cell,worker,{'initial_positions':[[2.]]})
                attempts[0]['screen']['pass']=True
                with self.assertRaises(ValueError):study.validate_terminal(plan,cell,worker,{'initial_positions':[[1.]]})
                attempts[0]['screen']['pass']=False;attempts[-1]['screen']['pass']=False;worker['precision_pass']=False
                with self.assertRaises(ValueError):study.validate_terminal(plan,cell,worker,{'initial_positions':[[1.]]})

    def test_zero_covariate_intervention_preserves_observation_noise(self):
        fixture={'truth':[2.,0.,0.,0.,0.,3.], 'holdout':{'x':[[4.]],'y':[[21.]]}}
        # beta=2+exp(0)*3=5, original conditional location=20, residual=1.
        study.zero_flow_covariates(fixture)
        self.assertEqual(fixture['holdout']['x'],[[0.]])
        self.assertEqual(fixture['holdout']['y'],[[1.]])

    def test_seed_collision_rejected_before_generation(self):
        seeds=dict(dataset_seed=10,replicates=[{'sampler_seed':1,'initialization_seed':2}]*20)
        with self.assertRaises(ValueError):study.create_plan({'seeds':{'flow':seeds,'local_level':seeds},'previously_used_seeds':[]},'must-not-create')


if __name__=='__main__':unittest.main()
