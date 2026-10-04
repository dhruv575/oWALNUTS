import copy
import tempfile
import unittest
from pathlib import Path

from test_qualification import fixture
from precision_compare import compare_precision,audit_tiers,RESTART_POLICY
from precision_tiers import run_tiers


def bundle(final_draws=2000,arm='candidate'):
    model,expected,report,_=fixture()
    expected['settings'].pop('draws');expected['settings']['warmup']=1000
    expected['arm']=arm
    tiers=[1000,2000,4000];selected=tiers[:tiers.index(final_draws)+1]
    plan=dict(model='flow',arm=arm,seed=1,warmup=1000,tiers=tiers,chains=4,
              timeout_per_tier=60,relative_mcse=.02,names=None,cpus=[0],
              restart_policy=RESTART_POLICY,phase='exploratory')
    reports={};attempts=[]
    for draws in selected:
        r=copy.deepcopy(report);r['arm']=arm;r['phase']='exploratory'
        r['settings']=dict(expected['settings'],draws=draws);r['healthy']=True
        if draws!=final_draws:
            r['evaluation']['functionals']['tau']['endpoint_mcse']=[.06,.06]
        path=f'{arm}/{draws}/report.json';reports[path]=r
        attempts.append(dict(draws=draws,report=path,status='completed',call_seconds_including_reporting=3.))
    total=3.*len(attempts)
    result=dict(plan=plan,attempts=attempts,precision_pass=True,
                attempted_draws_per_chain=sum(selected),selected_draws_per_chain=final_draws,
                cumulative_fit_and_report_seconds=total,tier_controller_seconds=total+.5)
    return model,expected,dict(result=result,reports=reports,invocation={'controller_invocation_seconds':total+1})


class PrecisionComparisonTests(unittest.TestCase):
    def test_different_retained_counts_same_precision_are_comparable(self):
        model,a,ba=bundle(2000);_,b,bb=bundle(4000,'reference')
        result=compare_precision(ba,bb,a,b,model)
        self.assertTrue(result['comparable']);self.assertAlmostEqual(result['time_to_precision_speedup'],10/7)
        self.assertFalse(result['qualified']);self.assertFalse(result['candidate']['qualification_eligible'])

    def test_missing_and_undercounted_restarts_fail(self):
        model,e,b=bundle();del b['reports'][b['result']['attempts'][0]['report']]
        self.assertFalse(audit_tiers(b,e,model)['pass'])
        _,e,b=bundle();b['result']['cumulative_fit_and_report_seconds']=3.
        self.assertFalse(audit_tiers(b,e,model)['pass'])
        _,e,b=bundle();b['result']['attempts'][0]['call_seconds_including_reporting']=.1
        self.assertFalse(audit_tiers(b,e,model)['pass'])

    def test_false_health_does_not_hide_final_bad_coordinate(self):
        model,e,b=bundle();r=b['reports'][b['result']['attempts'][-1]['report']]
        r['evaluation']['canonical_parameter_diagnostics']['q_0']['rhat']=1.2
        self.assertFalse(audit_tiers(b,e,model)['pass'])

    def test_failed_attempt_cannot_disappear_or_restart(self):
        model,e,b=bundle();r=b['reports'][b['result']['attempts'][0]['report']]
        r.update(status='failed',failed_elapsed_seconds=2.)
        b['result']['attempts'][0]['status']='failed'
        self.assertFalse(audit_tiers(b,e,model)['pass'])

    def test_mismatched_precision_fixture_and_names_fail(self):
        model,a,ba=bundle();_,b,bb=bundle(4000,'reference')
        bb['result']['plan']['relative_mcse']=.03
        self.assertFalse(compare_precision(ba,bb,a,b,model)['comparable'])
        _,b,bb=bundle(4000,'reference');b['fixture_sha256']='different'
        self.assertFalse(compare_precision(ba,bb,a,b,model)['comparable'])
        _,b,bb=bundle(4000,'reference');bb['result']['plan']['names']=['tau']
        self.assertFalse(compare_precision(ba,bb,a,b,model)['comparable'])

    def test_cold_scope_is_explicit_reused_claim_rejected(self):
        model,a,ba=bundle();_,b,bb=bundle(4000,'reference')
        result=compare_precision(ba,bb,a,b,model,'cold_fit_and_report')
        self.assertAlmostEqual(result['time_to_precision_speedup'],1.5)
        del bb['invocation']
        self.assertFalse(compare_precision(ba,bb,a,b,model)['comparable'])
        with self.assertRaises(ValueError):compare_precision(ba,bb,a,b,model,'reused_process')

    def test_different_unused_caps_allowed_only_after_common_passes(self):
        model,a,ba=bundle();_,b,bb=bundle(4000,'reference')
        ba['result']['plan']['tiers'].append(8000)
        result=compare_precision(ba,bb,a,b,model)
        self.assertTrue(result['comparable'])
        self.assertTrue(result['tier_schedule_comparison']['unused_cap_difference'])
        bb['result']['plan']['tiers']=[1000,3000,4000]
        self.assertFalse(compare_precision(ba,bb,a,b,model)['comparable'])

    def test_skip_first_passing_tier_rejected(self):
        model,e,b=bundle();r=b['reports'][b['result']['attempts'][0]['report']]
        r['evaluation']['functionals']['tau']['endpoint_mcse']=[.01,.01]
        self.assertFalse(audit_tiers(b,e,model)['pass'])

    def test_shared_runtime_source_change_refuses_comparison(self):
        model,a,ba=bundle();_,b,bb=bundle(4000,'reference')
        b['source_sha256']={'file':'new_revision'}
        for report in bb['reports'].values():report['source_sha256']=dict(b['source_sha256'])
        result=compare_precision(ba,bb,a,b,model)
        self.assertFalse(result['comparable'])
        self.assertEqual(result['source_comparison']['shared_differences'],['file'])

    def test_executor_exception_persisted_and_charged(self):
        def raises(*args,**kwargs):raise RuntimeError('worker setup failed')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result'
            result=run_tiers('fixture.json',path,'candidate',None,1,100,[100,200],4,20,executor=raises)
            self.assertFalse(result['precision_pass']);self.assertEqual(len(result['attempts']),1)
            self.assertTrue((path/'precision-result.json').exists())
            self.assertTrue((path/'draws-100'/'controller-exception.json').exists())
            self.assertGreater(result['cumulative_fit_and_report_seconds'],0)
            self.assertFalse((path/'draws-100'/'candidate-report.json').exists())


if __name__=='__main__':unittest.main()
