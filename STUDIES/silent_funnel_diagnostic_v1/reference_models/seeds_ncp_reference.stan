// Non-centred rewrite of posteriordb seeds_data-seeds_centered_model (WP55
// reference only). Same posterior over (alpha0, alpha1, alpha12, alpha2, c,
// sigma) and the same transformed parameter b: c = sigma * c_raw with
// c_raw ~ normal(0, 1) is the standard non-centring of c ~ normal(0, sigma).
data {
  int<lower=0> I;
  array[I] int<lower=0> n;
  array[I] int<lower=0> N;
  vector[I] x1; // seed type
  vector[I] x2; // root extract
}
transformed data {
  vector[I] x1x2;
  x1x2 = x1 .* x2;
}
parameters {
  real alpha0;
  real alpha1;
  real alpha12;
  real alpha2;
  vector[I] c_raw;
  real<lower=0> sigma;
}
transformed parameters {
  vector[I] c = sigma * c_raw;
  vector[I] b;
  b = c - mean(c);
}
model {
  alpha0 ~ normal(0.0, 1.0);
  alpha1 ~ normal(0.0, 1.0);
  alpha2 ~ normal(0.0, 1.0);
  alpha12 ~ normal(0.0, 1.0);
  sigma ~ cauchy(0, 1);

  c_raw ~ normal(0.0, 1.0);
  n ~ binomial_logit(N,
                     alpha0 + alpha1 * x1 + alpha2 * x2 + alpha12 * x1x2 + b);
}
