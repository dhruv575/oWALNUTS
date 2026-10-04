import tempfile
from pathlib import Path
import unittest
from precision_tiers import precision_screen,run_tiers


def report(error=.01,healthy=True,status='completed'):
    return {'status':status,'healthy':healthy,'evaluation':{
        'functionals':{'a':{'interval_90':[0.,1.],'endpoint_mcse':[error,error]}},
        'forecast':{'rows':[{'lower':0.,'upper':1.,'endpoint_mcse':[error,error]}]}}}


class PrecisionTests(unittest.TestCase):
    def test_fast_unhealthy_not_accepted(self):
        self.assertFalse(precision_screen(report(0.,healthy=False))['pass'])

    def test_missing_and_nonfinite_precision_rejected(self):
        self.assertFalse(precision_screen(report(),names=['absent'])['pass'])
        self.assertFalse(precision_screen(report(float('nan')))['pass'])
        self.assertFalse(precision_screen({'status':'completed','healthy':True})['pass'])

    def test_every_restart_charged_and_stops_at_first_pass(self):
        calls=[]
        def execute(fixture,path,arm,exe,seed,warmup,draws,chains,timeout):
            calls.append(draws)
            return report(.04 if draws==100 else .01)
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'tiers'
            result=run_tiers('fixture.json',out,'numpyro',None,1,100,[100,200,400],4,30,executor=execute)
            self.assertEqual(calls,[100,200])
            self.assertEqual(result['attempted_draws_per_chain'],300)
            self.assertEqual(result['selected_draws_per_chain'],200)
            self.assertEqual(result['cumulative_fit_and_report_seconds'],sum(a['call_seconds_including_reporting'] for a in result['attempts']))
            self.assertFalse(result['qualified'])
            with self.assertRaises(FileExistsError):
                run_tiers('fixture.json',out,'numpyro',None,1,100,[100],4,30,executor=execute)

    def test_failed_worker_stops_and_stays_failure(self):
        with tempfile.TemporaryDirectory() as root:
            result=run_tiers('fixture.json',Path(root)/'tiers','numpyro',None,1,100,[100,200],4,30,
                executor=lambda *args:report(status='failed'))
            self.assertFalse(result['precision_pass'])
            self.assertEqual(len(result['attempts']),1)


if __name__=='__main__':unittest.main()
