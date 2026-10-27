import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import evaluate
from summarize import summarize

class OrchestrationTests(unittest.TestCase):
    def test_missing_keeps_denominator(self):
        with tempfile.TemporaryDirectory() as folder:
            result=summarize(folder)
            for data in result['datasets'].values():
                self.assertEqual(data['planned_origins'],100)
                self.assertEqual(data['arms']['reference']['available_origins'],0)
                self.assertIsNone(data['arms']['reference']['full_mean_logscore'])

    def test_partial_timeout_checkpoint(self):
        sources=[dict(arm='reference',seed=None,sha256='fixture'),
                 dict(arm='warm_K200',seed=1,sha256='fixture')]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'partial.json'
            with patch.object(evaluate,'predictive',side_effect=[dict(logpdf=1.,pit=.4),TimeoutError('fixture')]):
                with self.assertRaises(TimeoutError):
                    evaluate.origin('sim',dict(tick=1,sources=sources),np.zeros(300),{},None,path)
            value=json.loads(path.read_text())
            self.assertEqual(len(value['arms']),1)
            self.assertEqual(value['arms'][0]['status'],'ok')

    def test_missing_arm_and_paired_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            for tick in range(1,101):
                arms=[dict(arm='reference',seed=None,status='ok',logpdf=2.,pit=.5)]
                arms += [dict(arm='warm_K200',seed=s,status='ok',logpdf=1.5,pit=.4) for s in [971201,971202,971203]]
                arms += [dict(arm=s,seed=None,status='ok',logpdf=1.,pit=.3) for s in ['nig_ar1','rolling_t5_mle','ewma_t5']]
                if tick==50:arms[1]=dict(arm='warm_K200',seed=971201,status='unavailable')
                evaluate.atomic(Path(folder)/f'sim-tick-{tick:03d}.json',dict(dataset='sim',tick=tick,arms=arms))
            got=summarize(folder)['datasets']['sim']['paired_comparisons']
            ref=got['reference-minus-nig_ar1']
            self.assertEqual(ref['full_mean'],1.)
            self.assertEqual(ref['bootstrap']['5'],[1.,1.])
            warm=got['warm-971201-minus-reference']
            self.assertEqual(warm['available_pairs'],99)
            self.assertIsNone(warm['full_mean']);self.assertIsNone(warm['bootstrap']['10'])
            self.assertEqual(warm['available_mean'],-.5)

if __name__=='__main__':unittest.main()
