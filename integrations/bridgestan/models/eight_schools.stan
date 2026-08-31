data {
  int<lower=1> J;
  vector[J] y;
  vector<lower=0>[J] sigma;
}
parameters {
  real mu;
  real<lower=0> tau;
  vector[J] z;
}
transformed parameters {
  vector[J] theta = mu + tau * z;
}
model {
  target += normal_lpdf(mu | 0, 5);
  target += cauchy_lpdf(tau | 0, 5) + log(2);
  target += std_normal_lpdf(z);
  target += normal_lpdf(y | theta, sigma);
}
