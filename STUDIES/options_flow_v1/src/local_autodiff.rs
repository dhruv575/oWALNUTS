//! The application model written once as a normalized density, without manual gradients.
use super::Model;
use owalnuts_autodiff::{AutodiffTarget, Const, Data, Scalar, cumsum, normal_lpdf, student_t_lpdf};

pub struct Density<'a>(&'a Model);
pub fn target(model: &Model) -> AutodiffTarget<Density<'_>> {
    AutodiffTarget::new(Density(model))
}
impl owalnuts_autodiff::Model for Density<'_> {
    fn dimension(&self) -> usize {
        self.0.data.y.len() + 2
    }
    fn log_density<S: Scalar>(&self, q: &[S]) -> S {
        let model = self.0;
        let data = &model.data;
        let n = data.y.len();
        let obs = q[n].exp();
        let rw = q[n + 1].exp();
        let mut lp = normal_lpdf(q[n], Const(0.08f64.ln()), Const(1.0))
            + normal_lpdf(q[n + 1], Const(0.12f64.ln()), Const(1.0));
        let h = if model.nc {
            lp += normal_lpdf(&q[..n], Const(0.0), Const(1.0));
            let first = q[0] * 1.5 + data.anchor;
            let mut innovations = Vec::with_capacity(n);
            innovations.push(first);
            for (&innovation, &dt) in q[1..n].iter().zip(&data.dt) {
                innovations.push(rw * innovation * dt.sqrt());
            }
            cumsum(&innovations)
        } else {
            let h = q[..n].to_vec();
            lp += normal_lpdf(h[0], Const(data.anchor), Const(1.5));
            if n > 1 {
                let scales: Vec<_> = data.dt.iter().map(|v| rw * v.sqrt()).collect();
                lp += normal_lpdf(&h[1..], &h[..n - 1], &scales);
            }
            h
        };
        lp + student_t_lpdf(Data(&data.y), data.nu, &h, obs)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use owalnuts::sampler::Target;
    #[test]
    fn matches_hand_gradient_with_irregular_time() {
        for nc in [false, true] {
            for n in [1usize, 5] {
                let model = Model {
                    data: super::super::Data {
                        y: vec![0.2; n],
                        anchor: 0.2,
                        nu: 5.0,
                        dt: (1..n).map(|i| i as f64 * 0.5).collect(),
                        anchor_mode: "exogenous".into(),
                    },
                    nc,
                };
                for offset in [-0.5, 0.0, 0.7] {
                    let mut q: Vec<_> = (0..model.dimension())
                        .map(|i| offset + (i as f64).sin() * 0.2)
                        .collect();
                    q[n] = -2.0;
                    q[n + 1] = -1.5;
                    let mut hand = vec![0.0; q.len()];
                    let mut auto = hand.clone();
                    let a = model.log_density_gradient(&q, &mut hand).unwrap();
                    let b = target(&model).log_density_gradient(&q, &mut auto).unwrap();
                    assert!((a - b).abs() < 1e-9 * (1.0 + a.abs()));
                    for (i, (a, b)) in hand.iter().zip(&auto).enumerate() {
                        assert!(
                            (a - b).abs() < 1e-9 * (1.0 + a.abs()),
                            "nc={nc},n={n},coordinate{i}:hand{a},auto{b}"
                        );
                    }
                }
            }
        }
    }
}
