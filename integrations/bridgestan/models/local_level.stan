// Gaussian local-level model with fixed globals (matches STUDIES/exact_state_space_ground_truth_v1).
data {
  int<lower=1> T;
  vector[T] y;
  vector<lower=0>[T] r;     // observation variances
  real m0;
  real<lower=0> tau0;
  real mu;
  real<lower=0> sigma_x;
}
parameters {
  vector[T] x;
}
model {
  x[1] ~ normal(m0, tau0);
  x[2:T] ~ normal(x[1:(T - 1)] + mu, sigma_x);
  y ~ normal(x, sqrt(r));
}
