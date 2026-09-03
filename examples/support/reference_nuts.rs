//! Clean-room reference NUTS (Stan's `base_nuts`, 2.21+) over any
//! [`Target`], with a diagonal metric: multinomial sampling within
//! subtrees, biased progressive sampling across doublings, the generalised
//! no-U-turn criterion on the summed momenta with the two cross checks,
//! divergence at `H - H0 > 1000`. Shared by `examples/kernel_efficiency.rs`
//! and the `STUDIES/kernel_gap_v1` harness through `#[path]`.
//!
//! Per transition it reports the leapfrog count, depth, stop cause, the
//! number of states in the final orbit and the indices of the selected and
//! the initial state within it (from the backward end), so the orbit
//! statistics can be compared one-to-one with the oWALNUTS kernel's
//! `TransitionDiagnostics`.
#![allow(dead_code)]

use owalnuts::walnutpie::Target;
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};
use rand_distr::StandardNormal;

#[derive(Clone)]
pub struct Z {
    pub q: Vec<f64>,
    pub p: Vec<f64>,
    pub g: Vec<f64>,
    pub lp: f64,
}

struct Subtree {
    valid: bool,
    rho: Vec<f64>,
    p_beg: Vec<f64>,
    p_end: Vec<f64>,
    propose: Z,
    log_weight: f64,
    /// States in the subtree.
    states: usize,
    /// Index of `propose` from the subtree's backward (earliest) end.
    selected_offset: usize,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct RefStats {
    pub depth: usize,
    pub leapfrogs: usize,
    pub divergent: bool,
    pub max_depth: bool,
    /// States in the final orbit (the initial state plus every merged leaf).
    pub orbit_states: usize,
    /// Index of the selected state within the orbit, from the backward end.
    pub selected_index: usize,
    /// Index of the initial state within the orbit.
    pub initial_index: usize,
}

pub struct RefNuts<'a, T: Target> {
    target: &'a T,
    pub step: f64,
    /// `M^-1` (diagonal).
    pub inv_mass: Vec<f64>,
    pub max_depth: usize,
    pub max_delta_h: f64,
    leapfrogs: usize,
    divergent: bool,
    sum_metro_prob: f64,
}

impl<'a, T: Target> RefNuts<'a, T> {
    pub fn new(target: &'a T, step: f64, inv_mass: Vec<f64>, max_depth: usize) -> Self {
        Self {
            target,
            step,
            inv_mass,
            max_depth,
            max_delta_h: 1000.0,
            leapfrogs: 0,
            divergent: false,
            sum_metro_prob: 0.0,
        }
    }

    pub fn hamiltonian(&self, z: &Z) -> f64 {
        let kinetic: f64 =
            z.p.iter()
                .zip(&self.inv_mass)
                .map(|(p, m)| 0.5 * p * p * m)
                .sum();
        -z.lp + kinetic
    }

    pub fn evaluate(&self, z: &mut Z) {
        match self.target.log_density_gradient(&z.q, &mut z.g) {
            Ok(lp) if lp.is_finite() && z.g.iter().all(|g| g.is_finite()) => z.lp = lp,
            _ => {
                z.lp = f64::NEG_INFINITY;
                z.g.fill(0.0);
            }
        }
    }

    pub fn initial(&self, q: Vec<f64>) -> Z {
        let d = q.len();
        let mut z = Z {
            q,
            p: vec![0.0; d],
            g: vec![0.0; d],
            lp: 0.0,
        };
        self.evaluate(&mut z);
        z
    }

    fn leapfrog(&mut self, z: &mut Z, eps: f64) {
        for (p, g) in z.p.iter_mut().zip(&z.g) {
            *p += 0.5 * eps * g;
        }
        for ((q, p), m) in z.q.iter_mut().zip(&z.p).zip(&self.inv_mass) {
            *q += eps * m * p;
        }
        self.evaluate(z);
        for (p, g) in z.p.iter_mut().zip(&z.g) {
            *p += 0.5 * eps * g;
        }
        self.leapfrogs += 1;
    }

    /// `p_sharp_plus . rho > 0 && p_sharp_minus . rho > 0`.
    fn criterion(&self, p_minus: &[f64], p_plus: &[f64], rho: &[f64]) -> bool {
        let dot = |p: &[f64]| -> f64 {
            p.iter()
                .zip(rho)
                .zip(&self.inv_mass)
                .map(|((p, r), m)| p * m * r)
                .sum()
        };
        dot(p_plus) > 0.0 && dot(p_minus) > 0.0
    }

    fn build_tree(
        &mut self,
        depth: usize,
        z: &mut Z,
        sign: f64,
        h0: f64,
        rng: &mut SmallRng,
    ) -> Subtree {
        if depth == 0 {
            self.leapfrog(z, sign * self.step);
            let mut h = self.hamiltonian(z);
            if h.is_nan() {
                h = f64::INFINITY;
            }
            if h - h0 > self.max_delta_h {
                self.divergent = true;
            }
            self.sum_metro_prob += (h0 - h).min(0.0).exp();
            return Subtree {
                valid: !self.divergent,
                rho: z.p.clone(),
                p_beg: z.p.clone(),
                p_end: z.p.clone(),
                propose: z.clone(),
                log_weight: h0 - h,
                states: 1,
                selected_offset: 0,
            };
        }
        let init = self.build_tree(depth - 1, z, sign, h0, rng);
        if !init.valid {
            return init;
        }
        let fin = self.build_tree(depth - 1, z, sign, h0, rng);
        if !fin.valid {
            return fin;
        }
        let log_weight = log_sum_exp(init.log_weight, fin.log_weight);
        // Multinomial sampling within the subtree.
        let take_fin = rng.random::<f64>().ln() < fin.log_weight - log_weight;
        // Physical order: forward builds `init` then `fin`, backward the
        // reverse.
        let selected_offset = match (sign > 0.0, take_fin) {
            (true, true) => init.states + fin.selected_offset,
            (true, false) => init.selected_offset,
            (false, true) => fin.selected_offset,
            (false, false) => fin.states + init.selected_offset,
        };
        let propose = if take_fin { fin.propose } else { init.propose };
        let rho: Vec<f64> = init.rho.iter().zip(&fin.rho).map(|(a, b)| a + b).collect();
        let mut persist = self.criterion(&init.p_beg, &fin.p_end, &rho);
        let ext: Vec<f64> = init
            .rho
            .iter()
            .zip(&fin.p_beg)
            .map(|(a, b)| a + b)
            .collect();
        persist &= self.criterion(&init.p_beg, &fin.p_beg, &ext);
        let ext: Vec<f64> = fin
            .rho
            .iter()
            .zip(&init.p_end)
            .map(|(a, b)| a + b)
            .collect();
        persist &= self.criterion(&init.p_end, &fin.p_end, &ext);
        Subtree {
            valid: persist,
            rho,
            p_beg: init.p_beg,
            p_end: fin.p_end,
            propose,
            log_weight,
            states: init.states + fin.states,
            selected_offset,
        }
    }

    pub fn transition(&mut self, current: &Z, rng: &mut SmallRng) -> (Z, RefStats) {
        let mut z = current.clone();
        for (p, m) in z.p.iter_mut().zip(&self.inv_mass) {
            *p = rng.sample::<f64, _>(StandardNormal) / m.sqrt();
        }
        self.leapfrogs = 0;
        self.divergent = false;
        self.sum_metro_prob = 0.0;
        let h0 = self.hamiltonian(&z);
        let mut z_fwd = z.clone();
        let mut z_bck = z.clone();
        let mut sample = z.clone();
        let mut rho = z.p.clone();
        let (mut p_bck, mut p_fwd) = (z.p.clone(), z.p.clone());
        let mut log_weight = 0.0;
        let mut depth = 0;
        let mut hit_max = true;
        let mut orbit_states = 1usize;
        let mut selected_index = 0usize;
        let mut initial_index = 0usize;
        while depth < self.max_depth {
            let forward = rng.random::<f64>() > 0.5;
            let sub = if forward {
                self.build_tree(depth, &mut z_fwd, 1.0, h0, rng)
            } else {
                self.build_tree(depth, &mut z_bck, -1.0, h0, rng)
            };
            if !sub.valid {
                hit_max = false;
                break;
            }
            depth += 1;
            // Biased progressive sampling across doublings.
            let take_new = sub.log_weight > log_weight
                || rng.random::<f64>().ln() < sub.log_weight - log_weight;
            if forward {
                if take_new {
                    selected_index = orbit_states + sub.selected_offset;
                }
            } else {
                initial_index += sub.states;
                selected_index = if take_new {
                    sub.selected_offset
                } else {
                    selected_index + sub.states
                };
            }
            orbit_states += sub.states;
            if take_new {
                sample = sub.propose;
            }
            log_weight = log_sum_exp(log_weight, sub.log_weight);
            let merged: Vec<f64> = rho.iter().zip(&sub.rho).map(|(a, b)| a + b).collect();
            let (tree_near, tree_far) = if forward {
                (&p_fwd, &p_bck)
            } else {
                (&p_bck, &p_fwd)
            };
            let mut persist = self.criterion(tree_far, &sub.p_end, &merged);
            let ext: Vec<f64> = rho.iter().zip(&sub.p_beg).map(|(a, b)| a + b).collect();
            persist &= self.criterion(tree_far, &sub.p_beg, &ext);
            let ext: Vec<f64> = sub.rho.iter().zip(tree_near).map(|(a, b)| a + b).collect();
            persist &= self.criterion(tree_near, &sub.p_end, &ext);
            rho = merged;
            if forward {
                p_fwd = sub.p_end;
            } else {
                p_bck = sub.p_end;
            }
            if !persist {
                hit_max = false;
                break;
            }
        }
        let stats = RefStats {
            depth,
            leapfrogs: self.leapfrogs,
            divergent: self.divergent,
            max_depth: hit_max,
            orbit_states,
            selected_index,
            initial_index,
        };
        (sample, stats)
    }
}

pub fn log_sum_exp(a: f64, b: f64) -> f64 {
    if a == f64::NEG_INFINITY {
        return b;
    }
    if b == f64::NEG_INFINITY {
        return a;
    }
    let m = a.max(b);
    m + ((a - m).exp() + (b - m).exp()).ln()
}

/// One chain of `draws` transitions from `start` at a fixed step and
/// diagonal inverse metric; returns the draw-major samples and the
/// per-transition statistics.
pub fn run_chain<T: Target>(
    target: &T,
    step: f64,
    inv_mass: Vec<f64>,
    start: &[f64],
    draws: usize,
    max_depth: usize,
    seed: u64,
) -> (Vec<f64>, Vec<RefStats>) {
    let mut nuts = RefNuts::new(target, step, inv_mass, max_depth);
    let mut rng = SmallRng::seed_from_u64(seed);
    let mut z = nuts.initial(start.to_vec());
    let d = start.len();
    let mut samples = Vec::with_capacity(draws * d);
    let mut stats = Vec::with_capacity(draws);
    for _ in 0..draws {
        let (next, s) = nuts.transition(&z, &mut rng);
        z = next;
        samples.extend_from_slice(&z.q);
        stats.push(s);
    }
    (samples, stats)
}
