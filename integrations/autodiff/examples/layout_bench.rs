use owalnuts::walnutpie::Target;
use owalnuts_autodiff::models::{EightSchools, Funnel, LocalLevel, LocalLevelData};
use owalnuts_autodiff::{AutodiffTarget, Model};
use std::{hint::black_box, time::Instant};

fn run(name: &str, model: impl Model) {
    let target = AutodiffTarget::new(model);
    let q = vec![0.1; target.dimension()];
    let mut gradient = vec![0.0; q.len()];
    let value = target.log_density_gradient(&q, &mut gradient).unwrap();
    let fingerprint = gradient.iter().fold(value.to_bits(), |hash, v| {
        (hash ^ v.to_bits()).wrapping_mul(0x100000001b3)
    });
    let repeats = 10_000;
    let mut ns = Vec::new();
    for _ in 0..5 {
        let start = Instant::now();
        for _ in 0..repeats {
            black_box(
                target
                    .log_density_gradient(black_box(&q), &mut gradient)
                    .unwrap(),
            );
        }
        ns.push(start.elapsed().as_nanos() as f64 / repeats as f64);
    }
    println!("{name} ns={ns:?} fingerprint={fingerprint:016x}");
}
fn main() {
    run("eight-schools", EightSchools::default());
    run("funnel-100", Funnel { dimension: 100 });
    run(
        "local-level-1000",
        LocalLevel {
            data: LocalLevelData::simulate(1000, 71),
            normalised: true,
        },
    );
}
