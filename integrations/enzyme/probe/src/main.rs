#![feature(autodiff)]
use std::autodiff::autodiff_reverse;

#[autodiff_reverse(d_square, Duplicated, Active)]
fn square(x: &[f64]) -> f64 { x.iter().map(|v| v * v).sum() }

fn main() {
    let x = [1.0, 2.0, 3.0];
    let mut dx = [0.0; 3];
    let (y, ()) = d_square(&x, &mut dx, 1.0);
    println!("{y} {dx:?}");
}
