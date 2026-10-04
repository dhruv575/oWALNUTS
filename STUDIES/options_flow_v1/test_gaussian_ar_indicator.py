import unittest,math
from gaussian_ar_indicator import indicator_covariance,finite_n_covariance
class CovarianceTests(unittest.TestCase):
 def test_iid_closed_form_and_symmetry(self):
  r=finite_n_covariance(100,32,0.)['cdf_covariance'];self.assertAlmostEqual(r[0][0],.05*.95/3200);self.assertAlmostEqual(r[0][1],(.05-.05*.95)/3200);self.assertAlmostEqual(r[0][0],r[1][1])
 def test_median_arcsine_exact_identity(self):
  for rho in [-.9,-.1,0,.5,.9]:
   v,e=indicator_covariance(.5,.5,rho);self.assertAlmostEqual(v,math.asin(rho)/(2*math.pi),places=12)
 def test_finite_n_explicit_matrix_and_n1(self):
  for n in [1,2,5]:
   rho=.7;expected=sum(.25 if i==j else math.asin(rho**abs(i-j))/(2*math.pi) for i in range(n) for j in range(n))/(3*n*n)
   r=finite_n_covariance(n,3,rho,(.5,.5));self.assertAlmostEqual(r['cdf_covariance'][0][0],expected,places=12)
 def test_endpoint_psd_symmetry_and_quadrature_convergence(self):
  a=finite_n_covariance(32,32,.9,epsabs=1e-10);b=finite_n_covariance(32,32,.9,epsabs=1e-13);c=a['cdf_covariance']
  self.assertAlmostEqual(c[0][0],c[1][1],places=12);self.assertGreater(c[0][0]*c[1][1]-c[0][1]**2,0)
  for i in range(2):
   for j in range(2):self.assertAlmostEqual(c[i][j],b['cdf_covariance'][i][j],places=12)
 def test_invalid(self):
  for n,f,r in [(0,1,.9),(1,0,.9),(1,1,1.),(True,1,.9)]:
   with self.assertRaises(ValueError):finite_n_covariance(n,f,r)
if __name__=='__main__':unittest.main()
