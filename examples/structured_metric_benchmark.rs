use owalnuts::walnutpie::{BlockDiagonalMass, StructuredBlockMass, StructuredCovarianceBlock};
use std::hint::black_box;
use std::time::Instant;

fn main() {
    let dimensions = [6, 250, 250, 250, 250];
    let rho: f64 = 0.5;
    let mut dense_blocks = Vec::new();
    let mut structured_blocks = Vec::new();
    for (block_index, n) in dimensions.into_iter().enumerate() {
        let scale: Vec<f64> = (0..n).map(|i| 1.0 + (i % 11) as f64 * 0.01).collect();
        let mut matrix = vec![0.0; n * n];
        for i in 0..n {
            for j in 0..n {
                matrix[i * n + j] = if block_index == 0 && i != j {
                    0.0
                } else {
                    scale[i] * scale[j] * rho.powi(i.abs_diff(j) as i32)
                };
            }
        }
        dense_blocks.push((matrix, n));
        structured_blocks.push(if block_index == 0 {
            StructuredCovarianceBlock::BidiagonalCholesky {
                diagonal: scale,
                subdiagonal: vec![0.0; n.saturating_sub(1)],
            }
        } else {
            StructuredCovarianceBlock::ScaledAr1 { scale, rho }
        });
    }
    let dense = BlockDiagonalMass::from_blocks(dense_blocks).unwrap();
    let structured = StructuredBlockMass::new(structured_blocks).unwrap();
    let momentum = vec![0.25; structured.dimension()];
    let dense_iterations = 100;
    let structured_iterations = 10_000;
    let started = Instant::now();
    for _ in 0..dense_iterations {
        black_box(dense.drift(black_box(&momentum)).unwrap());
        black_box(dense.kinetic_energy(black_box(&momentum)).unwrap());
    }
    let dense_seconds = started.elapsed().as_secs_f64();
    let started = Instant::now();
    for _ in 0..structured_iterations {
        black_box(structured.drift(black_box(&momentum)).unwrap());
        black_box(structured.kinetic_energy(black_box(&momentum)).unwrap());
    }
    let structured_seconds = started.elapsed().as_secs_f64();
    println!(
        "{{\"dimension\":{},\"dense_seconds_per_iteration\":{},\"structured_seconds_per_iteration\":{},\"speedup\":{}}}",
        structured.dimension(),
        dense_seconds / dense_iterations as f64,
        structured_seconds / structured_iterations as f64,
        (dense_seconds / dense_iterations as f64)
            / (structured_seconds / structured_iterations as f64)
    );
}
