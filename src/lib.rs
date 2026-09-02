//! oWALNUTS: the Within-orbit Adaptive Leapfrog No-U-Turn Sampler
//! (Bou-Rabee, Carpenter, Kleppe, Liu; JMLR 27, 2026) in Rust. NUTS with a
//! second time scale: each macro leapfrog step is subdivided into micro-steps
//! chosen so the local energy error stays under `delta`, which samples
//! multi-scale targets such as Neal's funnel without the bias of fixed-step
//! NUTS. The kernel is tested leaf-for-leaf against the Flatiron reference
//! implementation `walnutpie`.
//!
//! Start with [`sampler`]: a builder ([`sampler::Sampler`]) over the complete
//! facade in [`walnutpie`], which documents the kernel, its numerical
//! contract, telemetry, and reproducibility guarantees. Research-only
//! facades are exported from `walnutpie` with the `research` Cargo feature.
//! [`diagnostics`] computes Stan/ArviZ-style R-hat, ESS and run summaries and
//! [`export`] writes CmdStan-format CSV that `arviz.from_cmdstan` reads.

pub mod diagnostics;
pub mod export;
#[allow(dead_code, unexpected_cfgs)]
mod kernel;
#[cfg(test)]
mod oracle_tests;
pub mod sampler;
mod types;
pub mod walnutpie;
