import copy
import unittest
from qualification import (calibration_gate, cell_gate, interval_gate,
                           paired_performance_gate, validate_manifest)


def fixture():
    names=['beta_bar','tau','mu_h','sigma_h','h_terminal']
    model={'kind':'flow','primary':[{'name':n,'kind':'functional','key':n} for n in names]+
           [{'name':'next_observed_y','kind':'forecast','horizon':1,'group':0}]}
    expected=dict(id='a',model='flow',arm='candidate',seed=1,fixture_sha256='data',
                  source_sha256={'file':'hash'},settings={'chains':4,'draws':1000},
                  dimension=2,prior_predictive=True)
    diag=dict(rhat=1.,bulk_ess=500.,tail_ess=500.)
    functions={n:dict(diag,interval_90=[-1.,1.],endpoint_mcse=[.01,.01],truth=0.) for n in names}
    report={k:copy.deepcopy(expected[k]) for k in ('arm','seed','fixture_sha256','source_sha256','settings')}
    report.update(status='completed',phase='qualification',protocol_sha256='frozen',
                  retained_divergences=0,end_to_end_seconds=2.,evaluation={
                    'chain_count':4,'canonical_parameter_diagnostics':{'q_0':dict(diag),'q_1':dict(diag)},
                    'functionals':functions,'forecast':{'rows':[dict(horizon=1,group=0,lower=-1.,upper=1.,
                    endpoint_mcse=[.01,.01],observed=0.)]}})
    manifest=dict(status='FROZEN',protocol_sha256='frozen',models={'flow':model},cells=[expected])
    return model,expected,report,manifest


class QualificationTests(unittest.TestCase):
    def test_missing_report_fails_and_counts(self):
        _,_,_,m=fixture(); result=calibration_gate(m,{})['groups']['flow/candidate']
        self.assertFalse(result['pass']); self.assertEqual(result['attempted'],1)
        self.assertEqual(result['functionals']['tau']['usable_and_covering'],0)

    def test_failed_fit_not_excluded(self):
        _,e,r,m=fixture(); e2=copy.deepcopy(e);e2['id']='b';m['cells'].append(e2)
        failed=copy.deepcopy(r);failed['status']='failed'
        g=calibration_gate(m,{'a':r,'b':failed})['groups']['flow/candidate']
        self.assertEqual(g['attempted'],2);self.assertEqual(g['usable'],1)
        self.assertEqual(g['functionals']['tau']['coverage'],.5)

    def test_precision_both_endpoints_and_forecast(self):
        self.assertFalse(interval_gate([0.,1.],[.01,.021]))
        self.assertFalse(interval_gate([0.,0.],[0.,0.]))
        self.assertFalse(interval_gate([0.,1.],[float('nan'),.01]))
        model,e,r,_=fixture();r['evaluation']['forecast']['rows'][0]['endpoint_mcse']=[.01,.05]
        self.assertFalse(cell_gate(r,e,model,'frozen')['pass'])

    def test_cached_health_cannot_hide_missing_coordinate(self):
        model,e,r,_=fixture();r['healthy']=True
        del r['evaluation']['canonical_parameter_diagnostics']['q_1']
        self.assertFalse(cell_gate(r,e,model,'frozen')['pass'])

    def test_pilot_cannot_be_promoted(self):
        model,e,r,_=fixture();r['phase']='exploratory'
        self.assertFalse(cell_gate(r,e,model,'frozen')['pass'])

    def test_source_mismatch_and_unknown_functionals(self):
        model,e,r,m=fixture();r['source_sha256']={'file':'wrong'}
        self.assertFalse(cell_gate(r,e,model,'frozen')['pass'])
        m['models']['flow']['primary'][0]['name']='post_hoc_choice'
        with self.assertRaises(ValueError):validate_manifest(m)

    def test_multiplicity_cannot_be_understated(self):
        _,_,r,m=fixture();m['family_size']=1
        with self.assertRaises(ValueError):calibration_gate(m,{'a':r})

    def test_1200_exact_equivalence_component_and_inaccurate_coverage(self):
        _,e,r,m=fixture();reports={};m['cells']=[]
        uncovered=copy.deepcopy(r)
        for row in uncovered['evaluation']['functionals'].values(): row['truth']=2.
        uncovered['evaluation']['forecast']['rows'][0]['observed']=2.
        for i in range(1200):
            cell=copy.deepcopy(e);cell['id']=str(i);m['cells'].append(cell)
            reports[str(i)]=r if i<1080 else uncovered
        good=calibration_gate(m,reports)
        self.assertTrue(good['calibration_component_pass']);self.assertFalse(good['qualified'])
        for i in range(960,1080): reports[str(i)]=uncovered
        self.assertFalse(calibration_gate(m,reports)['calibration_component_pass'])

    def test_local_level_primary_metadata(self):
        _,e,_,m=fixture()
        names=['h_initial','h_terminal','h_mean','sigma_obs','sigma_rw']
        model={'kind':'local_level','primary':[{'name':n,'kind':'functional','key':n} for n in names]+
               [{'name':'next_observed_log_price','kind':'forecast','horizon':1}]}
        m['models']={'local_level':model};e['model']='local_level'
        validate_manifest(m)
        model['primary'][0]['key']='h_terminal'
        with self.assertRaises(ValueError):validate_manifest(m)

    def test_unhealthy_faster_arm_cannot_win(self):
        model,a,ra,_=fixture();b=copy.deepcopy(a);b.update(id='b',arm='reference')
        rb=copy.deepcopy(ra);rb['arm']='reference';rb['end_to_end_seconds']=100.
        ra['evaluation']['canonical_parameter_diagnostics']['q_1']['rhat']=1.1
        result=paired_performance_gate([{'candidate':a,'reference':b}],{'a':ra,'b':rb},model,'frozen')
        self.assertFalse(result['material_speed_screen']);self.assertIsNone(result['geomean_speedup'])

    def test_valid_pair_is_only_component_screen(self):
        model,a,ra,_=fixture();b=copy.deepcopy(a);b.update(id='b',arm='reference')
        rb=copy.deepcopy(ra);rb['arm']='reference';rb['end_to_end_seconds']=4.
        result=paired_performance_gate([{'candidate':a,'reference':b}],{'a':ra,'b':rb},model,'frozen')
        self.assertTrue(result['material_speed_screen']);self.assertFalse(result['qualified'])


if __name__=='__main__': unittest.main()
