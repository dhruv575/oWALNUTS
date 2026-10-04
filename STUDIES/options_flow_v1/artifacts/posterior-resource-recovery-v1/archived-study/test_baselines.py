import copy
import unittest
from baselines import empirical_forecast


class BaselineTests(unittest.TestCase):
    def test_forecast_never_fits_holdout(self):
        fixture={'data':{'y':[[0,1],[1,2],[2,3],[3,4]]},'holdout':{'y':[[2,2]]}}
        a=empirical_forecast(fixture)
        changed=copy.deepcopy(fixture);changed['holdout']['y']=[[100,100]]
        b=empirical_forecast(changed)
        for ar,br in zip(a['rows'],b['rows']):
            self.assertEqual((ar['lower'],ar['upper']),(br['lower'],br['upper']))
        self.assertGreater(b['mean_interval_score'],a['mean_interval_score'])

    def test_local_level_vector_accepted(self):
        result=empirical_forecast({'data':{'y':[0,1,2]},'holdout':{'y':[1,3]}})
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(result['coverage'],.5)


if __name__=='__main__':unittest.main()
