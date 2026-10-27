// WP84 price-only SV model, same unconstrained coordinates as the Rust target:
// q = [mu, log_sigma, beta, z[n]].
data {
  int<lower=1> n;
  vector[n] y;
  real rho;
  real nu;
  real mu_mean; real mu_sd; real log_sigma_mean; real log_sigma_sd; real beta_sd;
}
parameters {
  real mu;
  real log_sigma;
  real beta;
  vector[n] z;
}
model {
  real sigma = exp(log_sigma);
  vector[n] h;
  h[1] = mu + sigma * z[1] / sqrt(1 - rho^2);
  for (i in 2:n) h[i] = mu + rho * (h[i - 1] - mu) + sigma * z[i];
  mu ~ normal(mu_mean, mu_sd);
  log_sigma ~ normal(log_sigma_mean, log_sigma_sd);
  beta ~ normal(0, beta_sd);
  z ~ std_normal();
  y ~ student_t(nu, beta, exp(h / 2));
}
generated quantities {
  real h_last;
  {
    real sigma = exp(log_sigma);
    h_last = mu + sigma * z[1] / sqrt(1 - rho^2);
    for (i in 2:n) h_last = mu + rho * (h_last - mu) + sigma * z[i];
  }
}
