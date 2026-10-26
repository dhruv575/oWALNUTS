/* WP88 Python extra: the SV density/gradient as a C-ABI target for owalnuts.from_cfunc.
 * ABI: double f(intptr_t dim, const double* q, double* grad, void* user_data).
 * A line-by-line translation of the Rust target (rust/src/main.rs); lgamma from libm instead of
 * the Lanczos series (a constant offset of ~1e-15, irrelevant to sampling). Returns -inf (zero
 * density) on a non-finite log density or gradient, as the Rust target rejects the proposal. */
#include <math.h>
#include <stdint.h>

typedef struct {
    int64_t n;
    double rho, nu, mu_mean, mu_sd, ls_mean, ls_sd, beta_sd;
    const double *y;
    double *h;   /* scratch, length n, owned by the caller (one target per thread-free call site) */
    double *dh;  /* scratch, length n */
} SvData;

static double norm_lp(double x, double m, double s, double *g) {
    double u = (x - m) / s;
    *g = -u / s;
    return -0.5 * u * u - log(s) - 0.5 * log(2.0 * M_PI);
}

double sv_logp_grad(intptr_t dim, const double *q, double *g, void *user_data) {
    const SvData *d = (const SvData *)user_data;
    const int64_t n = d->n;
    const double rho = d->rho, nu = d->nu;
    const double ln2pi = log(2.0 * M_PI);
    const double cst = lgamma((nu + 1.0) / 2.0) - lgamma(nu / 2.0) - 0.5 * log(nu * M_PI);
    (void)dim;
    double mu = q[0], ls = q[1], beta = q[2];
    double sigma = exp(ls);
    double lp = norm_lp(mu, d->mu_mean, d->mu_sd, &g[0]);
    lp += norm_lp(ls, d->ls_mean, d->ls_sd, &g[1]);
    lp += norm_lp(beta, 0.0, d->beta_sd, &g[2]);
    for (int64_t i = 0; i < n; i++) {
        double z = q[3 + i];
        lp += -0.5 * z * z - 0.5 * ln2pi;
        g[3 + i] = -z;
    }
    double s0 = sigma / sqrt(1.0 - rho * rho);
    /* h and dh on the stack would be n doubles each; use a local VLA for thread safety. */
    double h[n], dh[n];
    h[0] = mu + s0 * q[3];
    for (int64_t i = 1; i < n; i++) h[i] = mu + rho * (h[i - 1] - mu) + sigma * q[3 + i];
    for (int64_t i = 0; i < n; i++) {
        double r = d->y[i] - beta;
        double e = exp(-h[i]);
        double a = r * r * e / nu;
        lp += cst - 0.5 * h[i] - 0.5 * (nu + 1.0) * log1p(a);
        dh[i] = -0.5 + 0.5 * (nu + 1.0) * a / (1.0 + a);
        g[2] += (nu + 1.0) * r * e / nu / (1.0 + a);
    }
    for (int64_t i = n - 1; i >= 0; i--) {
        double m = (i == 0) ? s0 : sigma;
        g[3 + i] += dh[i] * m;
        g[1] += dh[i] * m * q[3 + i];
        g[0] += dh[i] * ((i == 0) ? 1.0 : 1.0 - rho);
        if (i > 0) dh[i - 1] += rho * dh[i];
    }
    if (!isfinite(lp)) return -INFINITY;
    for (int64_t i = 0; i < 3 + n; i++) {
        if (!isfinite(g[i])) return -INFINITY;
    }
    return lp;
}
