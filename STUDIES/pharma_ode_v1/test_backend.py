import json,unittest
import numpy as np
from scipy.integrate import solve_ivp
from backend import Backend,ROOT,DP
from sampling import fit

def independent(data,q):
    theta=np.exp(q);ka=theta[0];vol=theta[-2] if data['infer_v'] else data['fixed_v']
    def rhs(t,y):
        elim=theta[1]*y[0] if data['linear'] else theta[2]/vol*y[0]/(theta[1]+y[0])
        return [ka*data['dose']/vol*np.exp(-ka*t)-elim]
    sol=solve_ivp(rhs,(0,max(data['pred_times'])),[data['c0']],t_eval=data['pred_times'],rtol=2e-11,atol=2e-12,method='DOP853')
    assert sol.success
    prediction=np.log(sol.y[0]);mu=prediction[:data['N']];sig=theta[-1]
    prior=np.sum(q-np.log1p(theta**2)) if data['half_cauchy'] else -.5*np.sum(((q-np.array(data['prior_mean']))/np.array(data['prior_sd']))**2)
    lp=prior-data['N']*q[-1]-.5*np.sum(((np.log(data['concentration'])-mu)/sig)**2)
    return lp,prediction

class Tests(unittest.TestCase):
    def test_native_density_gradients_and_solver_tolerance(self):
        receipts={}
        for case in ['stan_public','theoph_1','theoph_2','theoph_3','linear_1']:
            data=json.loads((ROOT/'data'/f'{case}.json').read_text());prep=json.loads((ROOT/'prepared'/f'{case}.json').read_text());mode=np.array(prep['mode']);b=Backend(data)
            tighter=Backend(dict(data,tol=1e-10));rk=Backend(dict(data,tol=1e-10,solver=1));l0=b.value(mode)[0];i0=independent(data,mode)[0];maximum=0.
            for j in range(4):
                q=mode+.15*np.sin(np.arange(len(mode))+j);lp,g=b.value(q);other,pred=independent(data,q)
                self.assertAlmostEqual(lp-l0,other-i0,places=4)
                np.testing.assert_allclose(b.predict(q),pred,rtol=1e-5,atol=1e-6)
                np.testing.assert_allclose(tighter.value(q)[1],g,rtol=2e-4,atol=2e-4)
                np.testing.assert_allclose(rk.value(q)[1],g,rtol=2e-4,atol=2e-4)
                numeric=[]
                for k in range(len(q)):
                    e=np.zeros(len(q));e[k]=1e-5;numeric.append((independent(data,q+e)[0]-independent(data,q-e)[0])/2e-5)
                np.testing.assert_allclose(g,numeric,rtol=2e-4,atol=2e-4)
                maximum=max(maximum,float(np.max(abs(g-numeric))))
            receipts[case]={'max_absolute_gradient_discrepancy':maximum};b.close();tighter.close();rk.close()
        (ROOT/'SOLVER-PREFLIGHT.json').write_text(json.dumps(receipts,indent=2)+'\n')
    def test_whitening_and_both_abis(self):
        data=json.loads((ROOT/'data/theoph_1.json').read_text());prep=json.loads((ROOT/'prepared/theoph_1.json').read_text());mode=np.array(prep['mode']);L=np.array(prep['L']);raw=Backend(data);b=Backend(data,mode,L)
        z=np.linspace(-.1,.1,data['P']);lp,g=b.value(z);r,h=raw.value(mode+L@z)
        self.assertAlmostEqual(lp,r);np.testing.assert_allclose(g,L.T@h)
        q=np.ascontiguousarray(z);gn=np.zeros(len(z));ln=np.zeros(1)
        status=b.lib.nuts(len(z),q.ctypes.data_as(DP),gn.ctypes.data_as(DP),ln.ctypes.data_as(DP),b.nuts.user_data.ctypes.data)
        gw=np.zeros(len(z));lw=b.lib.walnuts(len(z),q.ctypes.data_as(DP),gw.ctypes.data_as(DP),b.ptr)
        self.assertEqual(status,0);self.assertAlmostEqual(ln[0],lw);np.testing.assert_array_equal(gn,gw);raw.close();b.close()
    def test_native_sampler_smoke(self):
        data=json.loads((ROOT/'data/theoph_1.json').read_text());prep=json.loads((ROOT/'prepared/theoph_1.json').read_text())
        for i,c in enumerate(['nuts_raw_90','nuts_white_99','walnuts_raw_90','walnuts_white_99']):
            q,r=fit(data,prep,c,885000000+i,100,150);self.assertEqual(q.shape,(4,100,5));self.assertTrue(np.isfinite(q).all());self.assertGreater(r['target_calls'],0)

if __name__=='__main__':unittest.main()
