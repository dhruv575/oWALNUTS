data {
  int<lower=1> N;
  array[N] vector[2] x;
  matrix[N,3] design;
  vector<lower=0>[3] coef_scale;
  real<lower=0> exposure;
  array[N] int<lower=0> y;
}
parameters {
  real<lower=0> rho;
  real<lower=0> alpha;
  vector[3] coef_tilde;
  vector[N] f_tilde;
}
transformed parameters {
  vector[3] beta = coef_scale .* coef_tilde;
  vector[N] f;
  {
    matrix[N,N] cov = gp_exp_quad_cov(x,alpha,rho)
                      + diag_matrix(rep_vector(1e-10,N));
    f = design * beta + cholesky_decompose(cov) * f_tilde;
  }
}
model {
  rho ~ gamma(2,1);
  alpha ~ normal(0,2);
  coef_tilde ~ std_normal();
  f_tilde ~ std_normal();
  y ~ poisson_log(log(exposure)+f);
}
