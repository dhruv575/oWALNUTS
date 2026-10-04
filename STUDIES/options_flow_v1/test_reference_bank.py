import unittest
import statistics
from reference_bank import weighted_quantile,pooled_parameter,predictive_bracket,shared_reference_errors,analyze,prepare_parameters,cached_parameter


class ReferenceBankTests(unittest.TestCase):
    def test_nondegenerate_bank_resamples_remain_shared_across_candidates(self):
        spec,fits=self.bank()
        for index,fit in enumerate(fits):
            for level in fit['levels'].values():
                for row in level['endpoints'].values():row['draws']=[v+(index-1.5)*.1 for v in row['draws']]
        result=analyze(spec,fits);vectors=result['joint_bootstrap_endpoints']
        self.assertGreater(statistics.variance(v['lo'] for v in vectors),0.)
        single=[];twenty=[]
        for vector in vectors:
            single.append(shared_reference_errors([{'lo':-1.}],vector)[0]['lo'])
            values=shared_reference_errors([{'lo':-1.}]*20,vector)
            twenty.append(statistics.mean(v['lo'] for v in values))
        self.assertAlmostEqual(statistics.variance(single),statistics.variance(twenty),places=12)
        lower=[v['lo'] for v in vectors];upper=[v['hi'] for v in vectors]
        covariance=sum((a-statistics.mean(lower))*(b-statistics.mean(upper)) for a,b in zip(lower,upper))/(len(lower)-1)
        self.assertGreater(covariance,0.)

    def bank(self):
        endpoints={name:dict(kind='parameter',probability=p,scale='unit',distribution_id='theta') for name,p in [('lo',.05),('hi',.95)]}
        fits=[]
        for i in range(4):
            fit=dict(id=str(i),backend='a' if i<2 else 'b',seed=10+i,initialization_seed=20+i,fixture_sha256='fixture',source_sha256='source',target_sha256='target')
            fit['levels']={str(n):dict(status='completed',healthy=True,draws_per_chain=n,endpoints={name:dict(scale='unit',distribution_id='theta',draws=[-1.,1.]*(n//2)) for name,value in [('lo',-1.),('hi',1.)]}) for n in [2,4]}
            fits.append(fit)
        spec=dict(fits=[{k:v for k,v in fit.items() if k!='levels'} for fit in fits],source_sha256='source',target_sha256='target',lengths=[2,4],chains=1,endpoints=endpoints,interval_pairs=[['lo','hi']],numerical_policy='validated_estimate',candidate_streams=[],bootstrap_replicates=1000,minimum_tail_count=2,bootstrap_seed=99,alpha=.05,relative_half_width=.001,backend_equivalence_relative_width=.001,length_equivalence_relative_width=.001)
        return spec,fits

    def test_cached_weighted_cdf_matches_direct_pool(self):
        spec,fits=self.bank()
        values=[[-3.,-1.,1.,8.],[-2.,0.],[.5,2.,7.],[-4.,3.,5.,9.,10.]]
        for fit,draws in zip(fits,values):
            for name in ['lo','hi']:fit['levels']['4']['endpoints'][name]['draws']=draws
        cache=prepare_parameters(fits,spec)
        self.assertIs(cache[(4,'lo')],cache[(4,'hi')])
        for counts in [None,{'0':2,'2':1,'3':1},{'1':3,'3':1}]:
            for p in [.05,.2,.5,.73,.95]:
                self.assertEqual(cached_parameter(fits,cache,4,'lo',p,counts),pooled_parameter(fits,'lo',4,p,counts))

    def test_mismatched_interval_distribution_rejected(self):
        import copy
        spec,fits=self.bank()
        spec['endpoints']['hi']['distribution_id']='other'
        self.assertEqual(analyze(spec,fits)['status'],'reference_unresolved')
        spec,fits=self.bank();fits[0]['levels']['4']['endpoints']['hi']['draws']=[0.]*4
        self.assertTrue(any('identical distribution' in reason for reason in analyze(spec,fits)['reasons']))

    def test_family_tail_resolution_and_equivalence_fail_closed(self):
        import copy
        spec,fits=self.bank()
        self.assertEqual(analyze(spec,fits)['status'],'numerically_resolved_under_declared_checks')
        bad=copy.deepcopy(spec);bad['interval_pairs']=[]
        self.assertEqual(analyze(bad,fits)['status'],'reference_unresolved')
        bad=copy.deepcopy(spec);bad['bootstrap_replicates']=200
        self.assertIn('Bootstrap tail resolution',analyze(bad,fits)['reasons'][0])
        for fit in fits[2:]:
            for level in fit['levels'].values():
                for name in ['lo','hi']:level['endpoints'][name]['draws']=[v+.1 for v in level['endpoints'][name]['draws']]
        result=analyze(spec,fits)
        self.assertTrue(any('Backend equivalence' in reason for reason in result['reasons']))

    def test_equal_fit_pool_is_not_average_quantiles(self):
        fits=[dict(id='a',levels={'2':{'endpoints':{'q':{'draws':[0.,100.]}}}}),
              dict(id='b',levels={'2':{'endpoints':{'q':{'draws':[10.]*20}}}})]
        self.assertEqual(pooled_parameter(fits,'q',2,.5),10.)
        self.assertEqual(pooled_parameter(fits,'q',2,.75),10.)
        self.assertEqual(weighted_quantile([0.,10.,100.],[.25,.5,.25],.95),100.)

    def test_predictive_envelope_inversion_known_uniform(self):
        row=dict(grid=[0.,.25,.5,.75,1.],cdf=[0.,.25,.5,.75,1.],cdf_error_bound=0.,error_bound_verified=True,error_bound_provenance='analytic Uniform(0,1)')
        fits=[dict(id='a',levels={'4':{'endpoints':{'q':row}}})]
        self.assertEqual(predictive_bracket(fits,'q',4,.5),(.25,.5))
        row['error_bound_verified']=False
        with self.assertRaises(ValueError):predictive_bracket(fits,'q',4,.5)

    def test_shared_reference_error_does_not_shrink_with_replicate_count(self):
        for count in [1,20,200]:
            errors=shared_reference_errors([{'q':1.}]*count,{'q':1.2})
            self.assertTrue(all(abs(row['q']+.2)<1e-12 for row in errors))
            self.assertAlmostEqual(sum(row['q'] for row in errors)/count,-.2)

    def test_missing_fit_unresolved_not_dropped(self):
        spec=dict(fits=[{'id':'a'},{'id':'b'}],source_sha256='source',target_sha256='target')
        result=analyze(spec,[{'id':'a'}])
        self.assertEqual(result['status'],'reference_unresolved')
        self.assertEqual(result['expected_fits'],2)
        self.assertEqual(result['recorded_fits'],1)


if __name__=='__main__':unittest.main()
