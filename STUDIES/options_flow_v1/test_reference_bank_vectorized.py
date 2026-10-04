"""Prospective equivalence contract for an optional vectorized bank quantile path.

Static only. Proposed module/API is not implemented or routed into analyze yet.
"""
import random
import unittest
from reference_bank import prepare_parameters,cached_parameter,resample_fits

class VectorizedBankContractTests(unittest.TestCase):
    def bank(self,heterogeneous=False):
        fits=[]
        for i in range(6):
            values=[-2.,-1.,-.3,0.,.2,1.,1.,2.]
            values=[v+.03*i for v in values]
            if heterogeneous:values=values[:5+i%3]
            fit=dict(id=str(i),backend='a' if i<3 else 'b',levels={})
            for n in [1,2]:
                row=dict(draws=values[:len(values)//2] if n==1 else values,distribution_id='theta',scale='unit')
                fit['levels'][str(n)]=dict(endpoints={'lo':row,'hi':row})
            fits.append(fit)
        spec=dict(lengths=[1,2],endpoints={k:dict(kind='parameter',distribution_id='theta',probability=p) for k,p in [('lo',.05),('hi',.95)]})
        return fits,prepare_parameters(fits,spec)
    def test_exact_random_stream_chunking_subsets_and_heterogeneous_fallback(self):
        from reference_bank_vectorized import batch_cached_parameter
        for heterogeneous in [False,True]:
            fits,cache=self.bank(heterogeneous);rng=random.Random(9971)
            counts=[resample_fits(fits,rng) for _ in range(37)]
            after=rng.getstate()
            for subset in [fits,fits[:3],fits[3:]]:
                for length in [1,2]:
                    for probability in [.05,.5,.95]:
                        expected=[cached_parameter(subset,cache,length,'lo',probability,c) for c in counts]
                        for chunk in [1,7,100]:
                            actual=batch_cached_parameter(subset,cache,length,'lo',probability,counts,chunk_size=chunk)
                            self.assertEqual(list(actual),expected)
            self.assertEqual(rng.getstate(),after)
    def test_left_inverse_repeated_values_and_threshold_boundary(self):
        from reference_bank_vectorized import batch_cached_parameter
        fits,cache=self.bank();counts=[{str(i):int(i==j)*6 for i in range(6)} for j in range(6)]
        counts += [{str(i):1 for i in range(6)}]
        for probability in [.125,.25,.5,.75,.95]:
            expected=[cached_parameter(fits,cache,2,'hi',probability,c) for c in counts]
            self.assertEqual(list(batch_cached_parameter(fits,cache,2,'hi',probability,counts,chunk_size=3)),expected)
    def test_joint_paired_vectors_share_original_counts(self):
        from reference_bank_vectorized import batch_cached_parameter
        fits,cache=self.bank();rng=random.Random(832)
        counts=[resample_fits(fits,rng) for _ in range(53)]
        high={};low={};backend={}
        for name,p in [('lo',.05),('hi',.95)]:
            high[name]=batch_cached_parameter(fits,cache,2,name,p,counts,chunk_size=8)
            low[name]=batch_cached_parameter(fits,cache,1,name,p,counts,chunk_size=8)
            backend[name]=[batch_cached_parameter(group,cache,2,name,p,counts,chunk_size=8) for group in [fits[:3],fits[3:]]]
        for i,c in enumerate(counts):
            for name,p in [('lo',.05),('hi',.95)]:
                self.assertEqual(high[name][i]-low[name][i],cached_parameter(fits,cache,2,name,p,c)-cached_parameter(fits,cache,1,name,p,c))
                self.assertEqual(backend[name][0][i]-backend[name][1][i],cached_parameter(fits[:3],cache,2,name,p,c)-cached_parameter(fits[3:],cache,2,name,p,c))
    def test_complete_analysis_evidence_identical(self):
        from test_reference_bank import ReferenceBankTests
        from reference_bank import analyze
        from reference_bank_vectorized import batch_cached_parameter
        spec,fits=ReferenceBankTests().bank()
        for i,fit in enumerate(fits):
            for n in [2,4]:
                for name in ['lo','hi']:fit['levels'][str(n)]['endpoints'][name]['draws']=[v+i*.17 for v in fit['levels'][str(n)]['endpoints'][name]['draws']]
        from unittest.mock import Mock
        spy=Mock(wraps=batch_cached_parameter)
        self.assertEqual(analyze(spec,fits),analyze(spec,fits,parameter_batch=spy))
        self.assertEqual(spy.call_count,8)
        self.assertTrue(all(len(call.args[5])==spec['bootstrap_replicates'] for call in spy.call_args_list))
        rejected=analyze(spec,fits,parameter_batch=Mock(side_effect=ValueError('batch definitely invoked')))
        self.assertIn('batch definitely invoked',rejected['reasons'])
    def test_invalid_generic_counts_fail_before_int64_cast(self):
        from reference_bank_vectorized import batch_cached_parameter
        fits,cache=self.bank()
        for bad in [True,.5,-1,2**63]:
            with self.assertRaises(ValueError):batch_cached_parameter(fits,cache,2,'lo',.05,[{'0':bad}])
if __name__=='__main__':unittest.main()



