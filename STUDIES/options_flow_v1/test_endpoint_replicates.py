import copy
import unittest
from endpoint_replicates import analyze,extract_worker,extract_cohort


class EndpointTests(unittest.TestCase):
    def test_extract_real_worker_and_reject_identity_mismatches(self):
        import hashlib,json
        streams=dict(sampler_seed=10,initialization_seed=20,prediction_seed=130010)
        fixture=dict(data={'y':[[0.]],'x':[[1.]],'initial_positions':[[0.]]},replicate_streams=streams)
        encoded=json.dumps(fixture).encode();fixture_hash=hashlib.sha256(encoded).hexdigest()
        target=dict(data={'y':[[0.]],'x':[[1.]]},predictive_contract='one-step',predictive_inputs={})
        target_hash=hashlib.sha256(json.dumps(target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        fields=dict(arm='worker-arm',seed=10,source_sha256={'worker':'hash'},settings={'draws':1000})
        manifest=dict(replicate_ids=['a'],target_sha256=target_hash,predictive_contract='one-step',arm='candidate',policy='first-pass',streams={'a':streams},
            worker_bindings={'a':dict(fixture_sha256=fixture_hash,report_fields=fields,prediction_seed_rule='sampler_seed_plus_130000',endpoint_scales={'q05':'log'})},
            endpoints={'q05':dict(scale='log',probability=.05,selector={'kind':'functional','name':'sigma'})})
        worker=dict(fields,fixture_sha256=fixture_hash,status='completed',healthy=True,precision_pass=True,end_to_end_seconds=2.,
            evaluation={'functionals':{'sigma':{'interval_90':[1.,2.],'endpoint_mcse':[.01,.02]}}})
        result=extract_worker(manifest,'a',worker,encoded)
        self.assertEqual(result['endpoints']['q05']['estimate'],1.)
        for key,value in [('seed',11),('fixture_sha256','wrong'),('source_sha256',{})]:
            bad=dict(worker);bad[key]=value
            with self.assertRaises(ValueError):extract_worker(manifest,'a',bad,encoded)
        bad=dict(worker);bad['seed']=11
        cohort=extract_cohort(manifest,{'a':(bad,encoded)})
        result=analyze(manifest,cohort)
        self.assertEqual(result['expected'],1);self.assertEqual(result['usable'],0)
        self.assertEqual(result['costs']['recorded_elapsed_seconds'],2.)
        manifest['endpoints']['q05']['scale']='price'
        with self.assertRaises(ValueError):extract_worker(manifest,'a',worker,encoded)

    def fixture(self):
        manifest=dict(target_sha256='fixed-target',arm='candidate',policy='first-pass',replicate_ids=['a','b','c'],endpoints={'q05':{'scale':'log','probability':.05}})
        rows=[dict(id=i,target_sha256='fixed-target',arm='candidate',policy='first-pass',status='completed',healthy=True,precision_pass=True,endpoints={'q05':dict(estimate=v,mcse=1.,scale='log',probability=.05)}) for i,v in zip(manifest['replicate_ids'],[-1.,0.,1.])]
        return manifest,rows

    def test_dispersion_and_understated_mcse(self):
        m,r=self.fixture();self.assertEqual(analyze(m,r)['endpoints']['q05']['variance_ratio'],1.)
        for row in r:row['endpoints']['q05']['mcse']=.1
        self.assertAlmostEqual(analyze(m,r)['endpoints']['q05']['variance_ratio'],100.)
        self.assertAlmostEqual(analyze(m,r)['endpoints']['q05']['mcse_calibration_ratio'],10.)
        for row in r:row['endpoints']['q05']['mcse']=.5
        self.assertAlmostEqual(analyze(m,r)['endpoints']['q05']['mcse_calibration_ratio'],2.)

    def test_missing_failed_ids_remain_denominator(self):
        m,r=self.fixture();r.pop();r[1]['healthy']=False
        output=analyze(m,r)
        self.assertEqual(output['expected'],3);self.assertEqual(output['usable'],1)
        self.assertEqual(output['outcomes']['c'],'missing');self.assertEqual(output['usable_rate_full_denominator'],1/3)

    def test_reference_unresolved_and_shared_uncertainty(self):
        m,r=self.fixture();self.assertEqual(analyze(m,r)['endpoints']['q05']['reference_status'],'reference_unresolved')
        ref=dict(resolved=True,target_sha256='fixed-target',provenance={'bank':'independent'},endpoints={'q05':dict(estimate=.5,mcse=.2,scale='log',probability=.05)})
        row=analyze(m,r,ref)['endpoints']['q05'];self.assertEqual(row['signed_difference_from_reference'],-.5)
        self.assertEqual(row['reference_mcse_shared'],.2)
        ref['target_sha256']='wrong';self.assertEqual(analyze(m,r,ref)['endpoints']['q05']['reference_status'],'reference_unresolved')

    def test_streams_and_full_denominator_costs(self):
        m,r=self.fixture()
        self.assertEqual(analyze(m,r)['independence_status'],'independence_unverified')
        m['streams']={key:dict(sampler_seed=10+i,initialization_seed=20+i,prediction_seed=30+i) for i,key in enumerate(m['replicate_ids'])}
        for row in r:row['streams']=m['streams'][row['id']].copy();row['elapsed_seconds']=2.
        r[1]['status']='failed'
        output=analyze(m,r)
        self.assertEqual(output['independence_status'],'declared_streams_matched')
        self.assertEqual(output['costs']['recorded_elapsed_seconds'],6.)
        r[0]['streams']['sampler_seed']=999
        self.assertEqual(analyze(m,r)['outcomes']['a'],'stream_mismatch')
        m['streams']['b']['initialization_seed']=m['streams']['a']['sampler_seed']
        with self.assertRaises(ValueError):analyze(m,r)
        m['streams']['b']['initialization_seed']=21
        m['streams']['b']['sampler_seed']=m['streams']['a']['sampler_seed']
        with self.assertRaises(ValueError):analyze(m,r)

    def test_replay_variance_separate_and_ids_strict(self):
        m,r=self.fixture();r[0]['predictive_replays']={'q05':[dict(seed=1,estimate=0.),dict(seed=2,estimate=2.)]}
        row=analyze(m,r)['endpoints']['q05'];self.assertEqual(row['predictive_replay']['mean_conditional_variance'],2.)
        self.assertEqual(row['variance_ratio'],1.)
        with self.assertRaises(ValueError):analyze(m,r+[copy.deepcopy(r[0])])
        r[0]['predictive_replays']['q05'][1]['seed']=1
        with self.assertRaises(ValueError):analyze(m,r)


if __name__=='__main__':unittest.main()
