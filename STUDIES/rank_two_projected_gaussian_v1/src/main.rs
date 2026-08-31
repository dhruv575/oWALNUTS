use std::num::NonZeroUsize;

use owalnuts::walnutpie::{
    DirectOriginalQMass, LowRankArrowheadMass, ProjectedArrowheadWarmup,
    InitialStepSearchConfig, ProjectedMetricOutcome, RunConfig, RunControl,
    StructuredCovarianceBlock, Target, TargetError, WarmupConfig, WarmupWindowConfig,
    sample_direct_original_q,
    sample_projected_arrowhead,
};

struct Gaussian { precision: Vec<f64> }

impl Target for Gaussian {
    fn dimension(&self) -> usize { 10 }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        for i in 0..10 {
            gradient[i] = -(0..10).map(|j| self.precision[i * 10 + j] * q[j]).sum::<f64>();
        }
        Ok(0.5 * q.iter().zip(gradient.iter()).map(|(q, g)| q * g).sum::<f64>())
    }
}

fn inverse(mut a: Vec<f64>, n: usize) -> Vec<f64> {
    let mut out = vec![0.0; n * n];
    for i in 0..n { out[i * n + i] = 1.0; }
    for i in 0..n {
        let pivot = (i..n).max_by(|&x, &y| a[x*n+i].abs().total_cmp(&a[y*n+i].abs())).unwrap();
        for j in 0..n { a.swap(i*n+j, pivot*n+j); out.swap(i*n+j, pivot*n+j); }
        let scale = a[i*n+i];
        for j in 0..n { a[i*n+j] /= scale; out[i*n+j] /= scale; }
        for k in 0..n {
            if k == i { continue; }
            let f = a[k*n+i];
            for j in 0..n { a[k*n+j] -= f*a[i*n+j]; out[k*n+j] -= f*out[i*n+j]; }
        }
    }
    out
}

fn metrics(samples: &[f64], covariance: &[f64]) -> (f64, f64) {
    let draws = samples.len() / 10;
    let mut esjd = 0.0;
    for t in 1..draws {
        for j in 0..10 {
            let d = samples[t*10+j] - samples[(t-1)*10+j];
            esjd += d*d / covariance[j*10+j];
        }
    }
    esjd /= (draws - 1) as f64;
    let mut ineff = 0.0;
    for j in 0..10 {
        let mean = (0..draws).map(|t| samples[t*10+j]).sum::<f64>() / draws as f64;
        let den = (0..draws).map(|t| (samples[t*10+j]-mean).powi(2)).sum::<f64>();
        let num = (1..draws).map(|t| (samples[t*10+j]-mean)*(samples[(t-1)*10+j]-mean)).sum::<f64>();
        let rho = (num / den).clamp(-0.99, 0.99);
        ineff += (1.0 + rho) / (1.0 - rho);
    }
    (esjd, ineff / 10.0)
}

fn main() {
    let mut covariance = vec![0.0; 100];
    for i in 0..10 { covariance[i*10+i] = 1.0; }
    covariance[0] = 9.0; covariance[11] = 4.0; covariance[66] = 5.0; covariance[77] = 3.0;
    for (i,j,v) in [(0,6,4.8), (1,7,-2.4), (2,6,0.8), (3,7,0.6)] {
        covariance[i*10+j]=v; covariance[j*10+i]=v;
    }
    let target = Gaussian { precision: inverse(covariance.clone(), 10) };
    let basis = vec![vec![1.0,0.0],vec![0.0,1.0],vec![0.0,0.0],vec![0.0,0.0]];
    let identity6 = (0..6).map(|i| (0..6).map(|j| f64::from(i==j)).collect()).collect();
    let mass = LowRankArrowheadMass::new(
        identity6,
        StructuredCovarianceBlock::ScaledAr1 { scale: vec![1.0;4], rho: 0.0 },
        basis.clone(), vec![vec![0.0;2];6],
    ).unwrap();
    let projected = ProjectedArrowheadWarmup::new(
        basis, NonZeroUsize::new(30).unwrap(), 0.08, 1e-6, 1e8,
    ).unwrap();
    let windows = WarmupWindowConfig::new(30, NonZeroUsize::new(50).unwrap(), 30).unwrap();
    let seeds = [71001_u64,71002,71003,71004];
    let mut log_esjd = 0.0;
    let mut log_ineff = 0.0;
    let mut rows = Vec::new();
    for seed in seeds {
        let warmup = WarmupConfig::new(0.8)
            .unwrap()
            .with_windows(windows.clone())
            .with_initial_step_search(InitialStepSearchConfig::default());
        let adaptive_config = RunConfig::new(180, NonZeroUsize::new(300).unwrap(), seed)
            .with_warmup(warmup);
        let baseline_config = RunConfig::new(180, NonZeroUsize::new(300).unwrap(), seed)
            .with_warmup(WarmupConfig::new(0.8).unwrap().with_mass_adaptation(false).with_windows(windows.clone()));
        let adaptive = sample_projected_arrowhead(
            &target, &[0.0;10], &mass, &projected, &adaptive_config, &RunControl::new(),
        ).unwrap();
        let baseline = sample_direct_original_q(
            &target, &[0.0;10], &DirectOriginalQMass::LowRankArrowhead(mass.clone()), &baseline_config,
        ).unwrap();
        let (ae, ai) = metrics(adaptive.chain().samples(), &covariance);
        let (be, bi) = metrics(baseline.samples(), &covariance);
        let healthy = adaptive.chain().diagnostics().iter().chain(baseline.diagnostics())
            .all(|d| !d.divergent() && !matches!(d.stop(), owalnuts::walnutpie::StopReason::MaximumDepth));
        let installed = adaptive.metric_updates().iter().any(|u| u.outcome()==ProjectedMetricOutcome::Installed);
        log_esjd += (ae/be).ln();
        log_ineff += (bi/ai).ln();
        rows.push((seed,healthy,installed,ae,be,ai,bi));
    }
    let esjd_ratio=(log_esjd/4.0).exp();
    let ineff_ratio=(log_ineff/4.0).exp();
    let passed=rows.iter().all(|r|r.1&&r.2)&&esjd_ratio>=1.05&&ineff_ratio>=1.05;
    println!("{{\"passed\":{passed},\"esjd_ratio\":{esjd_ratio},\"inefficiency_improvement\":{ineff_ratio},\"rows\":[");
    for (i,r) in rows.iter().enumerate() {
        println!("{}{{\"seed\":{},\"healthy\":{},\"installed\":{},\"adaptive_esjd\":{},\"baseline_esjd\":{},\"adaptive_ineff\":{},\"baseline_ineff\":{}}}",
            if i==0{""}else{","},r.0,r.1,r.2,r.3,r.4,r.5,r.6);
    }
    println!("]}}");
    if !passed { std::process::exit(2); }
}
