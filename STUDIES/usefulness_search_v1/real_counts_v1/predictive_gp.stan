data {
  int<lower=1> N;
  array[N] real x;
  array[N] int k;
  int<lower=1> N_future;
  array[N_future] real x_future;
}
parameters {
  real<lower=0> rho;
  real<lower=0> alpha;
  vector[N] f_tilde;
}
transformed parameters {
  vector[N] f;
  {
    matrix[N, N] cov = gp_exp_quad_cov(x, alpha, rho)
                       + diag_matrix(rep_vector(1e-10, N));
    matrix[N, N] L_cov = cholesky_decompose(cov);
    f = L_cov * f_tilde;
  }
}
model {
  rho ~ gamma(25, 4);
  alpha ~ normal(0, 2);
  f_tilde ~ normal(0, 1);
  k ~ poisson_log(f);
}
generated quantities {
  vector[N_future] future_mean;
  vector[N_future] future_variance;
  {
    matrix[N, N] cov = gp_exp_quad_cov(x, alpha, rho)
                      + diag_matrix(rep_vector(1e-10, N));
    matrix[N, N] L_cov = cholesky_decompose(cov);
    matrix[N, N_future] cross_cov = gp_exp_quad_cov(x, x_future, alpha, rho);
    matrix[N, N_future] A = mdivide_left_tri_low(L_cov, cross_cov);
    future_mean = A' * f_tilde;
    future_variance = rep_vector(square(alpha) + 1e-10, N_future)
                      - columns_dot_self(A)';
  }
}
