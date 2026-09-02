//! oWALNUTS: the Within-orbit Adaptive Leapfrog No-U-Turn Sampler.
//!
//! Start with [`sampler`]: a builder ([`sampler::Sampler`]) over the complete
//! facade in [`walnutpie`], which documents the kernel, its numerical
//! contract, telemetry, and reproducibility guarantees. Research-only
//! facades are exported from `walnutpie` with the `research` Cargo feature.

#[allow(dead_code, unexpected_cfgs)]
mod kernel;
#[cfg(test)]
mod oracle_tests;
pub mod sampler;
mod types;
pub mod walnutpie;
