functions {
  vector rhs(real t, vector y, real ka, real km, real vm, real dose, real vol) {
    vector[1] dy;
    dy[1] = exp(-ka*t)*dose*ka/vol - (vm/vol)*y[1]/(km+y[1]);
    return dy;
  }
  vector curve(vector q, data int linear, data int infer_v, data real fixed_v, data real dose,
               data real c0, data array[] real ts, data real tol, data int solver) {
    int n = size(ts);
    vector[n] out;
    real ka=exp(q[1]);
    real vol = infer_v ? exp(q[num_elements(q)-1]) : fixed_v;
    if (linear) {
      real ke=exp(q[2]);
      for (i in 1:n) {
        real delta=ka-ke;
        real absorption;
        if (abs(delta)<1e-6)
          absorption=ka*ts[i]*exp(-ke*ts[i])*(1-delta*ts[i]/2+square(delta*ts[i])/6);
        else
          absorption=ka*exp(-ke*ts[i])*(-expm1(-delta*ts[i]))/delta;
        out[i]=c0*exp(-ke*ts[i])+dose/vol*absorption;
      }
    } else {
      vector[1] y0; y0[1]=c0;
      if (solver==0) {
        array[n] vector[1] ys=ode_bdf_tol(rhs,y0,0,ts,tol,tol,20000,
                                           ka,exp(q[2]),exp(q[3]),dose,vol);
        for (i in 1:n) out[i]=ys[i,1];
      } else {
        array[n] vector[1] ys=ode_rk45_tol(rhs,y0,0,ts,tol,tol,20000,
                                            ka,exp(q[2]),exp(q[3]),dose,vol);
        for (i in 1:n) out[i]=ys[i,1];
      }
    }
    return out;
  }
}
data {
  int<lower=1> P;
  int<lower=1> N;
  array[N] real<lower=0> times;
  vector<lower=0>[N] concentration;
  int<lower=1> Npred;
  array[Npred] real<lower=0> pred_times;
  real<lower=0> dose;
  real<lower=0> fixed_v;
  real<lower=0> c0;
  int<lower=0,upper=1> infer_v;
  int<lower=0,upper=1> linear;
  int<lower=0,upper=1> half_cauchy;
  vector[P] prior_mean;
  vector<lower=0>[P] prior_sd;
  real<lower=0> tol;
  int<lower=0,upper=1> solver;
}
parameters { vector[P] q; }
model {
  vector[N] mu=curve(q,linear,infer_v,fixed_v,dose,c0,times,tol,solver);
  if (half_cauchy) target += cauchy_lpdf(exp(q)|0,1)+sum(q);
  else q ~ normal(prior_mean,prior_sd);
  concentration ~ lognormal(log(mu),exp(q[P]));
}
generated quantities {
  vector[Npred] log_prediction=log(curve(q,linear,infer_v,fixed_v,dose,c0,pred_times,tol,solver));
}
