//! oWALNUTS fixed-diagonal sampling facade.
//!
//! This crate is an internal beta with a frozen, non-adaptive kernel. See
//! [`walnutpie`] for the complete support and numerical contract,
//! [`diagnostics`] for Stan/ArviZ-style R-hat, ESS and run summaries, and
//! [`export`] for CmdStan-format CSV output that `arviz.from_cmdstan` reads.

pub mod diagnostics;
pub mod export;
#[allow(dead_code, unexpected_cfgs)]
mod kernel;
#[cfg(test)]
mod oracle_tests;
mod types;
pub mod walnutpie;
