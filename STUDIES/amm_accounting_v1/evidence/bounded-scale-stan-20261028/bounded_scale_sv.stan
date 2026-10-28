// Separate normalized bounded-scale candidate, including explicit eta Jacobian.
data {
  int<lower=1> n;
  vector[n] y;
  real<lower=0> cap;
  real<lower=-1,upper=1> rho;
}
transformed data {
  if (cap <= 0 || abs(rho) >= 1) reject("positive cap and stationary rho");
}
parameters {
  real mu;
  real eta;
  real beta;
  vector[n] z;
}
transformed parameters {
  real log_sigma = log(cap)-log1p_exp(eta);
  real sigma = exp(log_sigma);
  vector[n] h;
  h[1] = mu+sigma*z[1]/sqrt(1-square(rho));
  if (n>1)
    for (i in 2:n) h[i] = mu+rho*(h[i-1]-mu)+sigma*z[i];
}
model {
  mu ~ normal(2*log(.005),1);
  beta ~ normal(0,.002);
  z ~ std_normal();
  target += normal_lpdf(log_sigma | log(.2),.5)
            -normal_lcdf(log(cap) | log(.2),.5)+log_inv_logit(eta);
  y ~ student_t(5,beta,exp(h/2));
}
