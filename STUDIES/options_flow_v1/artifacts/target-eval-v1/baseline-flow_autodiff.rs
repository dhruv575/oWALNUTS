//! User-facing density-only implementation. All derivatives come from the existing adapter.
use super::Model;
use owalnuts_autodiff::{AutodiffTarget, Const, Data, Scalar, normal_lpdf, student_t_lpdf};

pub struct Density<'a>(&'a Model);
pub fn target(model: &Model) -> AutodiffTarget<Density<'_>> {
    AutodiffTarget::new(Density(model))
}
impl owalnuts_autodiff::Model for Density<'_> {
    fn dimension(&self) -> usize {
        4 + 2 * self.0.data.y[0].len() + self.0.data.y.len()
    }
    fn log_density<S: Scalar>(&self, q: &[S]) -> S {
        let model = self.0;
        let data = &model.data;
        let g = data.y[0].len();
        let n = data.y.len();
        let k = 4 + 2 * g;
        let sigma = q[3].exp();
        let tau = q[1].exp();
        let rho = data.rho;
        let mut lp = normal_lpdf(q[0], Const(0.0), Const(0.5))
            + normal_lpdf(q[1], Const(-1.0), Const(0.5))
            + normal_lpdf(q[2], Const(-1.0), Const(1.0))
            + normal_lpdf(q[3], Const(-1.5), Const(0.5))
            + normal_lpdf(&q[4..k], Const(0.0), Const(1.0));
        let h = if model.nc {
            // Independent innovations carry a standard-normal density directly.
            // No hand-computed derivative or transformed-density Jacobian is needed.
            lp += normal_lpdf(&q[k..], Const(0.0), Const(1.0));
            let mut h = Vec::with_capacity(n);
            h.push(q[2] + sigma * q[k] / (1.0 - rho * rho).sqrt());
            for t in 1..n {
                h.push(q[2] + (h[t - 1] - q[2]) * rho + sigma * q[k + t]);
            }
            h
        } else {
            let h = q[k..].to_vec();
            lp += normal_lpdf(h[0], q[2], sigma / (1.0 - rho * rho).sqrt());
            if n > 1 {
                let means: Vec<_> = h[..n - 1]
                    .iter()
                    .map(|&v| q[2] + (v - q[2]) * rho)
                    .collect();
                lp += normal_lpdf(&h[1..], &means, sigma);
            }
            h
        };
        let alpha: Vec<_> = q[4..4 + g].iter().map(|&v| v * 0.3).collect();
        let beta: Vec<_> = q[4 + g..k].iter().map(|&v| q[0] + tau * v).collect();
        for t in 0..n {
            let mean: Vec<_> = (0..g).map(|j| alpha[j] + beta[j] * data.x[t][j]).collect();
            lp += student_t_lpdf(Data(&data.y[t]), data.nu, &mean, (h[t] * 0.5).exp());
        }
        lp
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use owalnuts::sampler::Target;
    #[test]
    fn matches_hand_gradient_in_both_parameterizations() {
        for nc in [false, true] {
            let model = Model {
                data: super::super::Data {
                    y: vec![vec![0.2, -0.4]; 7],
                    x: vec![vec![0.8, -0.2]; 7],
                    nu: 5.0,
                    rho: 0.95,
                },
                nc,
            };
            for offset in [-0.7, 0.0, 0.8] {
                let mut q: Vec<_> = (0..model.dimension())
                    .map(|i| offset + (i as f64 * 0.7).sin() * 0.3)
                    .collect();
                q[1] = -1.2 + offset * 0.2;
                q[3] = -1.3 + offset * 0.2;
                let mut hand = vec![0.0; q.len()];
                let mut auto = hand.clone();
                let a = model.log_density_gradient(&q, &mut hand).unwrap();
                let b = target(&model).log_density_gradient(&q, &mut auto).unwrap();
                assert!((a - b).abs() < 1e-9 * (1.0 + a.abs()));
                for (i, (a, b)) in hand.iter().zip(&auto).enumerate() {
                    assert!(
                        (a - b).abs() < 1e-9 * (1.0 + a.abs()),
                        "nc={nc}, coordinate {i}: hand {a}, auto {b}"
                    );
                }
            }
        }
    }
}
