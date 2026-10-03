"""Correctness checks; execute only in a coordinated quiet window."""
import unittest
import numpy as np
from importlib.util import find_spec
OPTIONAL_AVAILABLE=all(find_spec(name) is not None for name in ['pymc','pytensor','numba','owalnuts'])
if OPTIONAL_AVAILABLE:
    import pymc_flow_workflow as workflow
else:
    workflow=None


@unittest.skipIf(workflow is None, 'Optional public PyMC environment unavailable')
class FlowWorkflowTests(unittest.TestCase):
    def data(self, t=8, g=2):
        rng = np.random.default_rng(612)
        return dict(y=rng.normal(size=(t,g)), x=rng.normal(size=(t,g)), nu=5., rho=.95)

    def test_roundtrips_displaced_starts(self):
        for t,g in [(1,1),(8,2),(128,4),(1000,4)]:
            data=self.data(t,g)
            starts=workflow.canonical_starts(data,4)
            starts+=np.random.default_rng(891).normal(0,.15,starts.shape)
            data['initial_positions']=starts.tolist()
            np.testing.assert_array_equal(workflow.canonical_starts(data,4),starts)
            nc=workflow.to_noncentered(starts,data)
            np.testing.assert_allclose(workflow.to_canonical(nc,data),starts,rtol=1e-12,atol=1e-12)

    def test_normalized_density_gradient_and_direction(self):
        for t,g in [(1,1),(8,2)]:
            data=self.data(t,g);target,_=workflow.compile_target(data)
            u=workflow.to_noncentered(workflow.canonical_starts(data,1),data)[0]
            u+=np.random.default_rng(121).normal(0,.05,u.shape)
            self.assertTrue(workflow.parity(target,data,[u])['passed'])
            _,gradient=workflow.evaluate_cfunc(target,u)
            direction=np.random.default_rng(22).normal(size=u.shape)
            direction/=np.linalg.norm(direction);eps=1e-5
            plus=workflow.evaluate_cfunc(target,u+eps*direction)[0]
            minus=workflow.evaluate_cfunc(target,u-eps*direction)[0]
            np.testing.assert_allclose((plus-minus)/(2*eps),gradient@direction,rtol=1e-6,atol=1e-6)

    def test_immutable_data_and_independent_targets(self):
        data=self.data(3,1);target,metadata=workflow.compile_target(data)
        u=workflow.to_noncentered(workflow.canonical_starts(data,1),data)[0]
        before=workflow.evaluate_cfunc(target,u)
        data['y']+=3
        after=workflow.evaluate_cfunc(target,u)
        np.testing.assert_array_equal(before[1],after[1]);self.assertEqual(before[0],after[0])
        self.assertNotEqual(metadata['data_sha256'],workflow.data_hash(data))
        other,_=workflow.compile_target(data)
        self.assertTrue(workflow.parity(other,data,[u])['passed'])
        self.assertNotEqual(workflow.evaluate_cfunc(other,u)[0],before[0])
        self.assertEqual(workflow.evaluate_cfunc(target,u)[0],before[0])

    def test_initial_positions_validation(self):
        data=self.data(1,1)
        data['initial_positions']=None
        workflow.build_model(data)
        for bad in [[],[1,2],[[0]],[[float('nan')]*7]]:
            data['initial_positions']=bad
            with self.assertRaises(ValueError):workflow.build_model(data)

    def test_parity_evidence_binding(self):
        import copy
        data=self.data(1,1)
        report=dict(model='flow',arm='python-pymc-flow-noncentered',adapter_source_sha256='adapter',
            extension_sha256='extension',source_sha256={'worker':'hash'},software={'python':'version'})
        evidence=dict(report,status='completed',parity={'passed':True,'cases':[{'value_error':0}]},
                      compilation={'data_sha256':workflow.data_hash(data)})
        self.assertTrue(workflow.validate_parity_evidence(evidence,report,data))
        for key in report:
            invalid=copy.deepcopy(evidence);invalid[key]='mismatch'
            with self.assertRaises(ValueError):workflow.validate_parity_evidence(invalid,report,data)
        for change in [{'status':'failed'},{'parity':{'passed':False}},
                       {'parity':{'passed':True,'cases':[]}}, {'compilation':{'data_sha256':'wrong'}}]:
            invalid=copy.deepcopy(evidence);invalid.update(change)
            with self.assertRaises(ValueError):workflow.validate_parity_evidence(invalid,report,data)
        with self.assertRaises(ValueError):workflow.validate_parity_evidence({},report,data)

    def test_rejects_bad_inputs(self):
        data=self.data()
        with self.assertRaises(ValueError):workflow.to_canonical(np.zeros(3),data)
        data['x'][0,0]=np.nan
        with self.assertRaises(ValueError):workflow.build_model(data)


if __name__=='__main__':unittest.main()
