data {
  int<lower=1> N;
  array[N] real x;
  array[N] int k;
  vector[N+2] mu;
  matrix[N+2,N+2] L_map;
  vector[N+2] shift;
  vector<lower=0>[N+2] scale;
  matrix[N+2,N+2] linear;
  array[N+2] matrix[N+2,N+2] quadratic;
  real map_log_det;
}
parameters { vector[N+2] z; }
transformed parameters {
  vector[N+2] q;
  real<lower=0> rho;
  real<lower=0> alpha;
  vector[N] f_tilde;
  vector[N] f;
  {
    vector[N+2] e;
    for (j in 1:(N+2)) {
      e[j] = scale[j]*z[j]+shift[j];
      if (j>1) {
        for (i in 1:(j-1)) e[j] += linear[j,i]*e[i];
        for (i in 1:(j-1))
          for (v in i:(j-1)) e[j] += quadratic[j,i,v]*e[i]*e[v];
      }
    }
    q = mu + L_map*e;
  }
  rho=exp(q[1]); alpha=exp(q[2]); f_tilde=segment(q,3,N);
  {
    matrix[N,N] cov=gp_exp_quad_cov(x,alpha,rho)+diag_matrix(rep_vector(1e-10,N));
    matrix[N,N] L_cov=cholesky_decompose(cov);
    f=L_cov*f_tilde;
  }
}
model {
  rho ~ gamma(25,4);
  alpha ~ normal(0,2);
  f_tilde ~ normal(0,1);
  k ~ poisson_log(f);
  target += q[1]+q[2]+map_log_det;
}
