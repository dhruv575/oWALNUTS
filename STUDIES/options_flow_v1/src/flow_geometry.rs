//! Fixed prior-Fisher affine coordinates; no observed values or generating truth.
use owalnuts::sampler::{Target, TargetError};
use serde_json::{Value, json};

#[derive(Clone)]
pub struct FixedGeometry {
    pub globals: usize,
    pub diagonal: Vec<f64>,
    pub subdiagonal: Vec<f64>,
    pub shear: Vec<f64>,
    pub log_jacobian: f64,
    mean_shear: bool,
}
impl FixedGeometry {
    pub fn new(
        n: usize,
        groups: usize,
        rho: f64,
        nu: f64,
        mean_shear: bool,
    ) -> Result<Self, TargetError> {
        if n == 0
            || groups == 0
            || !rho.is_finite()
            || rho.abs() >= 1.0
            || !nu.is_finite()
            || nu <= 2.0
        {
            return Err(TargetError::new("invalid Fisher geometry inputs"));
        }
        let inv = 3.0f64.exp();
        let c = groups as f64 * nu / (2.0 * (nu + 3.0));
        let mut prior = vec![(1.0 + rho * rho) * inv; n];
        if n == 1 {
            prior[0] = (1.0 - rho * rho) * inv;
        } else {
            prior[0] = inv;
            prior[n - 1] = inv;
        }
        let off = -rho * inv;
        let mut diagonal = vec![0.0; n];
        let mut subdiagonal = vec![0.0; n - 1];
        for i in 0..n {
            let pivot = if i == 0 {
                prior[i] + c
            } else {
                subdiagonal[i - 1] = off / diagonal[i - 1];
                prior[i] + c - subdiagonal[i - 1] * subdiagonal[i - 1]
            };
            if !pivot.is_finite() || pivot <= 0.0 {
                return Err(TargetError::new("nonpositive Fisher Cholesky pivot"));
            }
            diagonal[i] = pivot.sqrt();
        }
        let log_jacobian = -diagonal.iter().map(|v| v.ln()).sum::<f64>();
        let mut result = Self {
            globals: 4 + 2 * groups,
            diagonal,
            subdiagonal,
            shear: vec![0.0; n],
            log_jacobian,
            mean_shear,
        };
        if mean_shear {
            let mut qones = prior;
            for i in 0..n - 1 {
                qones[i] += off;
                qones[i + 1] += off;
            }
            result.solve_lower_in_place(&mut qones);
            result.solve_upper_in_place(&mut qones);
            result.shear = qones;
        }
        Ok(result)
    }
    pub fn dimension(&self) -> usize {
        self.globals + self.diagonal.len()
    }
    fn solve_lower_in_place(&self, value: &mut [f64]) {
        for i in 0..value.len() {
            value[i] = (value[i]
                - if i == 0 {
                    0.0
                } else {
                    self.subdiagonal[i - 1] * value[i - 1]
                })
                / self.diagonal[i];
        }
    }
    fn solve_upper_in_place(&self, value: &mut [f64]) {
        for i in (0..value.len()).rev() {
            value[i] = (value[i]
                - if i + 1 == value.len() {
                    0.0
                } else {
                    self.subdiagonal[i] * value[i + 1]
                })
                / self.diagonal[i];
        }
    }
    pub fn canonical(&self, u: &[f64]) -> Vec<f64> {
        let mut q = u.to_vec();
        self.solve_upper_in_place(&mut q[self.globals..]);
        for i in 0..self.diagonal.len() {
            q[self.globals + i] += -1.0 + self.shear[i] * (u[2] + 1.0);
        }
        q
    }
    pub fn transformed(&self, q: &[f64]) -> Vec<f64> {
        let mut u = q.to_vec();
        let offset: Vec<_> = (0..self.diagonal.len())
            .map(|i| q[self.globals + i] + 1.0 - self.shear[i] * (q[2] + 1.0))
            .collect();
        for i in 0..offset.len() {
            u[self.globals + i] = self.diagonal[i] * offset[i]
                + if i + 1 < offset.len() {
                    self.subdiagonal[i] * offset[i + 1]
                } else {
                    0.0
                };
        }
        u
    }
    fn pullback_in_place(&self, gradient: &mut [f64]) {
        gradient[2] += gradient[self.globals..]
            .iter()
            .zip(&self.shear)
            .map(|(g, a)| g * a)
            .sum::<f64>();
        self.solve_lower_in_place(&mut gradient[self.globals..]);
    }
    pub fn metadata(&self) -> Value {
        json!({"kind":if self.mean_shear{"fixed_prior_fisher_mean_shear"}else{"fixed_prior_fisher"},"sigma_reference":(-1.5f64).exp(),"mu_reference":-1.0,"global_dimension":self.globals,"path_dimension":self.diagonal.len(),"log_abs_det_jacobian":self.log_jacobian,"uses_observed_values":false,"uses_truth":false})
    }
}

/// Generic affine wrapper: density-only targets continue to supply automatic gradients.
pub struct AffineTarget<'a, T: Target> {
    pub base: &'a T,
    pub geometry: &'a FixedGeometry,
}
impl<T: Target> Target for AffineTarget<'_, T> {
    fn dimension(&self) -> usize {
        self.geometry.dimension()
    }
    fn log_density_gradient(&self, u: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        if u.len() != self.dimension()
            || gradient.len() != u.len()
            || self.base.dimension() != u.len()
        {
            return Err(TargetError::new("affine target dimension mismatch"));
        }
        let q = self.geometry.canonical(u);
        let lp = self.base.log_density_gradient(&q, gradient)? + self.geometry.log_jacobian;
        self.geometry.pullback_in_place(gradient);
        if !lp.is_finite() || gradient.iter().any(|v| !v.is_finite()) {
            return Err(TargetError::recoverable("nonfinite affine target"));
        }
        Ok(lp)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn gaussian_whitening_and_roundtrip() {
        for n in [1usize, 2, 12, 1000] {
            for shear in [false, true] {
                let geom = FixedGeometry::new(n, 4, 0.95, 5.0, shear).unwrap();
                let q: Vec<_> = (0..geom.dimension())
                    .map(|i| (i as f64 * 0.37).sin())
                    .collect();
                let recovered = geom.canonical(&geom.transformed(&q));
                for (a, b) in q.iter().zip(recovered) {
                    assert!((a - b).abs() < 1e-12);
                }
                let mut x: Vec<_> = (0..n).map(|i| (i as f64 * 0.23).cos()).collect();
                let squared = x.iter().map(|v| v * v).sum::<f64>();
                geom.solve_upper_in_place(&mut x);
                let inv = 3.0f64.exp();
                let c = 4.0 * 5.0 / 16.0;
                let mut quadratic = 0.0;
                for i in 0..n {
                    let diag = if n == 1 {
                        (1.0 - 0.95f64.powi(2)) * inv
                    } else if i == 0 || i + 1 == n {
                        inv
                    } else {
                        (1.0 + 0.95f64.powi(2)) * inv
                    };
                    quadratic += (diag + c) * x[i] * x[i];
                    if i + 1 < n {
                        quadratic += 2.0 * (-0.95 * inv) * x[i] * x[i + 1];
                    }
                }
                assert!((quadratic - squared).abs() < 1e-10 * (1.0 + squared));
            }
        }
    }
    #[test]
    fn normalized_density_pullback_and_autodiff_parity() {
        for n in [1usize, 2, 7] {
            for shear in [false, true] {
                let model = super::super::Model {
                    data: super::super::Data {
                        y: vec![vec![0.2, -0.4]; n],
                        x: vec![vec![0.8, -0.2]; n],
                        nu: 5.0,
                        rho: 0.95,
                        initial_positions: None,
                    },
                    nc: false,
                };
                let geom = FixedGeometry::new(n, 2, 0.95, 5.0, shear).unwrap();
                let target = AffineTarget {
                    base: &model,
                    geometry: &geom,
                };
                let auto = super::super::flow_autodiff::target(&model);
                let adtarget = AffineTarget {
                    base: &auto,
                    geometry: &geom,
                };
                let q: Vec<_> = (0..target.dimension())
                    .map(|i| -0.2 + (i as f64 * 0.41).sin() * 0.1)
                    .collect();
                let u = geom.transformed(&q);
                let mut gradient = vec![0.0; q.len()];
                let mut other = gradient.clone();
                let lp = target.log_density_gradient(&u, &mut gradient).unwrap();
                let base = model.log_density_gradient(&q, &mut other).unwrap();
                assert!((lp - base - geom.log_jacobian).abs() < 1e-10);
                let adlp = adtarget.log_density_gradient(&u, &mut other).unwrap();
                assert!((adlp - lp).abs() < 1e-10);
                let autodiff_gradient = other.clone();
                for i in 0..u.len() {
                    assert!((gradient[i] - autodiff_gradient[i]).abs() < 1e-9);
                    let mut plus = u.clone();
                    plus[i] += 1e-5;
                    let a = target.log_density_gradient(&plus, &mut other).unwrap();
                    plus[i] -= 2e-5;
                    let b = target.log_density_gradient(&plus, &mut other).unwrap();
                    let fd = (a - b) / 2e-5;
                    assert!((fd - gradient[i]).abs() < 1e-6 * (1.0 + fd.abs()));
                }
            }
        }
    }
}
