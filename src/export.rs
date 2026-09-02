//! CmdStan-format CSV export of retained draws and per-draw sampler statistics.
//!
//! [`CmdStanCsv`] writes one CSV per chain in the layout CmdStan's `output`
//! files use — `#`-prefixed configuration comments, a header row, then one
//! row per retained draw — so the files load directly with
//! `arviz.from_cmdstan(posterior=[...])`, `cmdstanpy`-style tooling, or any
//! CSV reader. Column names ending in `__` are sampler statistics; the rest
//! are parameters.
//!
//! Only statistics the fixed WALNUTS kernel actually records per transition
//! are emitted:
//!
//! | column | source |
//! |---|---|
//! | `lp__` | the target's log density at the draw, recomputed with the target passed to [`CmdStanCsv::with_log_density`] (omitted otherwise: the sampler does not store it) |
//! | `stepsize__` | the retained-phase macro step size (`RunMetadata::tuning().step_size()`) |
//! | `treedepth__` | `TransitionDiagnostics::depth` |
//! | `n_leapfrog__` | `TransitionDiagnostics::target_evaluations`, the fused log-density/gradient calls of the transition (WALNUTS refines micro-steps within macro steps, so this counts every gradient evaluation, not macro leapfrog steps) |
//! | `divergent__` | `TransitionDiagnostics::divergent` |
//! | `energy__` | `TransitionDiagnostics::initial_hamiltonian`, the Hamiltonian at the start of the transition after the momentum refresh |
//!
//! `accept_stat__` is deliberately absent: the kernel's acceptance statistic
//! is only captured during dual-averaging warmup and is not recorded for
//! retained draws.

use std::{
    fmt, fs,
    io::{self, BufWriter, Write},
    path::{Path, PathBuf},
};

use crate::{
    diagnostics::default_parameter_names,
    walnutpie::{ChainOutput, MultiChainOutput, Target, TargetError},
};

/// Why an export failed.
#[derive(Debug)]
#[non_exhaustive]
pub enum ExportError {
    Io(io::Error),
    /// The log-density target failed on a retained draw.
    Target(TargetError),
    /// The log-density target's dimension differs from the chain's.
    DimensionMismatch {
        chain: usize,
        target: usize,
    },
    /// The supplied parameter-name list does not have one entry per dimension.
    NameCountMismatch {
        expected: usize,
        got: usize,
    },
}

impl fmt::Display for ExportError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(error) => write!(f, "I/O error: {error}"),
            Self::Target(error) => write!(f, "log-density target failed: {error}"),
            Self::DimensionMismatch { chain, target } => write!(
                f,
                "log-density target has dimension {target} but the chain has {chain}"
            ),
            Self::NameCountMismatch { expected, got } => write!(
                f,
                "parameter names must have exactly {expected} entries (got {got})"
            ),
        }
    }
}

impl std::error::Error for ExportError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(error) => Some(error),
            Self::Target(error) => Some(error),
            _ => None,
        }
    }
}

impl From<io::Error> for ExportError {
    fn from(error: io::Error) -> Self {
        Self::Io(error)
    }
}

/// Sampler-statistic columns always written, in order.
pub const SAMPLER_STAT_COLUMNS: [&str; 5] = [
    "stepsize__",
    "treedepth__",
    "n_leapfrog__",
    "divergent__",
    "energy__",
];

/// CmdStan-format CSV writer. See the [module documentation](self).
#[derive(Clone, Copy, Default)]
pub struct CmdStanCsv<'a> {
    names: Option<&'a [String]>,
    log_density: Option<&'a dyn Target>,
}

impl fmt::Debug for CmdStanCsv<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("CmdStanCsv")
            .field("names", &self.names)
            .field("log_density", &self.log_density.map(|t| t.dimension()))
            .finish()
    }
}

impl<'a> CmdStanCsv<'a> {
    /// Writer with default names (`theta.1 ..= theta.d`) and no `lp__`.
    pub fn new() -> Self {
        Self::default()
    }

    /// Label the parameter columns. Must have one entry per dimension; names
    /// containing `.` are read by ArviZ as vector/array indices, as CmdStan's
    /// `theta.1` is.
    pub fn with_parameter_names(mut self, names: &'a [String]) -> Self {
        self.names = Some(names);
        self
    }

    /// Emit `lp__` by re-evaluating `target` at every retained draw (one
    /// fused call per draw; the gradient is discarded).
    pub fn with_log_density(mut self, target: &'a dyn Target) -> Self {
        self.log_density = Some(target);
        self
    }

    /// Header row for a chain of `dimension` parameters.
    pub fn columns(&self, dimension: usize) -> Result<Vec<String>, ExportError> {
        let names = match self.names {
            Some(names) if names.len() != dimension => {
                return Err(ExportError::NameCountMismatch {
                    expected: dimension,
                    got: names.len(),
                });
            }
            Some(names) => names.to_vec(),
            None => default_parameter_names(dimension),
        };
        let mut columns = Vec::with_capacity(SAMPLER_STAT_COLUMNS.len() + 1 + dimension);
        if self.log_density.is_some() {
            columns.push("lp__".to_string());
        }
        columns.extend(SAMPLER_STAT_COLUMNS.iter().map(|s| s.to_string()));
        columns.extend(names);
        Ok(columns)
    }

    /// Write one chain. `chain_index` is recorded in the comment header only.
    pub fn write<W: Write>(
        &self,
        chain: &ChainOutput,
        chain_index: usize,
        writer: W,
    ) -> Result<(), ExportError> {
        let dimension = chain.dimension();
        let columns = self.columns(dimension)?;
        if let Some(target) = self.log_density
            && target.dimension() != dimension
        {
            return Err(ExportError::DimensionMismatch {
                chain: dimension,
                target: target.dimension(),
            });
        }
        let metadata = chain.metadata();
        let mut out = BufWriter::new(writer);
        writeln!(out, "# owalnuts_version = {}", metadata.crate_version())?;
        writeln!(
            out,
            "# algorithm_revision = {}",
            metadata.algorithm_revision()
        )?;
        writeln!(out, "# method = sample")?;
        writeln!(out, "# algorithm = walnuts")?;
        writeln!(out, "# chain = {chain_index}")?;
        writeln!(out, "# num_samples = {}", metadata.retained())?;
        writeln!(out, "# num_warmup = {}", metadata.discarded())?;
        writeln!(out, "# save_warmup = 0")?;
        writeln!(out, "# thin = 1")?;
        writeln!(out, "# seed = {}", metadata.base_seed())?;
        writeln!(out, "# chain_seed = {}", metadata.effective_seed())?;
        writeln!(out, "# max_depth = {}", metadata.max_depth())?;
        writeln!(
            out,
            "# max_refinement_levels = {}",
            metadata.max_refinement_levels()
        )?;
        writeln!(out, "# max_error = {}", fmt_float(metadata.max_error()))?;
        writeln!(
            out,
            "# divergence_threshold = {}",
            fmt_float(metadata.divergence_threshold())
        )?;
        writeln!(out, "# Adaptation terminated")?;
        writeln!(
            out,
            "# Step size = {}",
            fmt_float(metadata.tuning().step_size())
        )?;
        writeln!(out, "# Diagonal elements of inverse mass matrix:")?;
        let inverse: Vec<String> = metadata
            .mass_diagonal()
            .iter()
            .map(|m| fmt_float(1.0 / m))
            .collect();
        writeln!(out, "# {}", inverse.join(", "))?;
        writeln!(out, "{}", columns.join(","))?;

        let discarded = metadata.discarded();
        let step_size = fmt_float(metadata.tuning().step_size());
        let mut gradient = vec![0.0; dimension];
        let mut cells: Vec<String> = Vec::with_capacity(columns.len());
        for (draw_index, draw) in chain.samples().chunks_exact(dimension).enumerate() {
            cells.clear();
            if let Some(target) = self.log_density {
                let lp = target
                    .log_density_gradient(draw, &mut gradient)
                    .map_err(ExportError::Target)?;
                cells.push(fmt_float(lp));
            }
            let diagnostic = chain.diagnostics().get(discarded + draw_index);
            cells.push(step_size.clone());
            match diagnostic {
                Some(d) => {
                    cells.push(d.depth().to_string());
                    cells.push(d.target_evaluations().to_string());
                    cells.push(u8::from(d.divergent()).to_string());
                    cells.push(fmt_float(d.initial_hamiltonian()));
                }
                None => cells.extend(["nan", "nan", "nan", "nan"].map(str::to_string)),
            }
            cells.extend(draw.iter().map(|value| fmt_float(*value)));
            writeln!(out, "{}", cells.join(","))?;
        }
        out.flush()?;
        Ok(())
    }

    /// Write every chain of `output` to `dir/{stem}-{k}.csv` (`k` from 1, as
    /// CmdStan numbers chains) and return the paths, in chain order.
    pub fn write_dir(
        &self,
        output: &MultiChainOutput,
        dir: impl AsRef<Path>,
        stem: &str,
    ) -> Result<Vec<PathBuf>, ExportError> {
        let dir = dir.as_ref();
        fs::create_dir_all(dir)?;
        let mut paths = Vec::with_capacity(output.chains().len());
        for (index, chain) in output.chains().iter().enumerate() {
            let path = dir.join(format!("{stem}-{}.csv", index + 1));
            let file = fs::File::create(&path)?;
            self.write(chain, index + 1, file)?;
            paths.push(path);
        }
        Ok(paths)
    }
}

/// Round-trip float text that Python's `float()` and Stan tooling parse.
fn fmt_float(value: f64) -> String {
    if value.is_nan() {
        "nan".to_string()
    } else if value.is_infinite() {
        if value > 0.0 { "inf" } else { "-inf" }.to_string()
    } else if value == 0.0 || (1e-4..1e15).contains(&value.abs()) {
        format!("{value}")
    } else {
        format!("{value:e}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn float_formatting_round_trips() {
        for value in [0.0, 1.5, -2.25e-7, 3e20, 1e-4, 123456.789] {
            assert_eq!(fmt_float(value).parse::<f64>().unwrap(), value);
        }
        assert_eq!(fmt_float(f64::NAN), "nan");
        assert_eq!(fmt_float(f64::NEG_INFINITY), "-inf");
    }

    #[test]
    fn columns_follow_cmdstan_layout() {
        let writer = CmdStanCsv::new();
        assert_eq!(
            writer.columns(2).unwrap(),
            [
                "stepsize__",
                "treedepth__",
                "n_leapfrog__",
                "divergent__",
                "energy__",
                "theta.1",
                "theta.2"
            ]
        );
        let names = ["a".to_string()];
        assert!(matches!(
            CmdStanCsv::new().with_parameter_names(&names).columns(2),
            Err(ExportError::NameCountMismatch {
                expected: 2,
                got: 1
            })
        ));
    }
}
