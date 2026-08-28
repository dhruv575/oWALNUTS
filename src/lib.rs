//! oWALNUTS fixed-diagonal sampling facade.
//!
//! This crate is an internal beta with a frozen, non-adaptive kernel. See
//! [`walnutpie`] for the complete support and numerical contract.

#[allow(dead_code, unexpected_cfgs)]
mod kernel;
#[cfg(test)]
mod oracle_tests;
mod types;
pub mod walnutpie;
