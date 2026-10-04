import unittest
from original_units import forecast_in_original_units


class OriginalUnitsTests(unittest.TestCase):
    def test_score_and_mcse_scale_with_positive_affine_map(self):
        forecast={'coverage':0.,'mean_interval_score':21.,'rows':[{
            'lower':0.,'upper':1.,'observed':2.,'width':1.,'interval_score':21.,'endpoint_mcse':[.01,.02]}]}
        result=forecast_in_original_units(forecast,{'scaling':{'y_mean':10.,'y_sd':2.},'provenance':{'y_units':'basis points'}})
        row=result['rows'][0]
        self.assertEqual((row['lower'],row['upper'],row['observed']),(10.,12.,14.))
        self.assertEqual(row['endpoint_mcse'],[.02,.04])
        self.assertEqual(result['mean_interval_score'],42.)
        self.assertEqual(forecast['rows'][0]['observed'],2.)
        self.assertEqual(result['units'],'basis points')

    def test_no_scaling_does_not_invent_units(self):
        self.assertIsNone(forecast_in_original_units({},{}))


if __name__=='__main__':unittest.main()
