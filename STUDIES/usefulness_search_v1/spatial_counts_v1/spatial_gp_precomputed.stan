data {
  int<lower=1> N;
  array[N] vector[2] x;
  matrix[N,3] design;
  vector<lower=0>[3] coef_scale;
  real<lower=0> exposure;
  array[N] int<lower=0> y;
}
transformed data {
  matrix[N,N] squared_distances;
  for (i in 1:N) {
    for (j in 1:N) squared_distances[i,j] = squared_distance(x[i],x[j]);
  }
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
    matrix[N,N] cov;
    real alpha_squared = square(alpha);
    real inverse_two_rho_squared = -0.5 / square(rho);
    for (i in 1:N) {
      cov[i,i] = alpha_squared + 1e-10;
      if (i < N) for (j in (i+1):N) {
        cov[i,j] = alpha_squared * exp(inverse_two_rho_squared * squared_distances[i,j]);
        cov[j,i] = cov[i,j];
      }
    }
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
