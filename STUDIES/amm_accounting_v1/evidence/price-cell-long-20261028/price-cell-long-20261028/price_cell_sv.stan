// Independent autodiff implementation of the candidate joint price-cell model.
data {
  int<lower=1> n;
  vector[n] lower_cell;
  vector[n] upper_cell;
  real initial;
  real<lower=-1,upper=1> rho;
}
transformed data {
  if (abs(rho) >= 1) reject("rho must be stationary");
  for (i in 1:n)
    if (upper_cell[i] <= lower_cell[i]) reject("positive cell widths required");
}
parameters {
  real mu;
  real log_sigma;
  real beta;
  vector[n] z;
  vector[n] u;
}
model {
  vector[n] h;
  vector[n] x = lower_cell + (upper_cell-lower_cell) .* inv_logit(u);
  real sigma = exp(log_sigma);
  h[1] = mu + sigma*z[1]/sqrt(1-square(rho));
  if (n > 1)
    for (i in 2:n) h[i] = mu + rho*(h[i-1]-mu) + sigma*z[i];
  mu ~ normal(2*log(0.005),1);
  log_sigma ~ normal(log(0.2),0.5);
  beta ~ normal(0,0.002);
  z ~ std_normal();
  for (i in 1:n) {
    real previous = initial;
    if (i > 1) previous = x[i-1];
    target += student_t_lpdf(x[i]-previous | 5,beta,exp(h[i]/2));
    target += log(upper_cell[i]-lower_cell[i]) + log_inv_logit(u[i]) + log1m_inv_logit(u[i]);
  }
}
