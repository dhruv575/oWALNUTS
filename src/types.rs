use std::fmt;

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct ValidationError(pub(crate) String);

impl fmt::Display for ValidationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for ValidationError {}

#[derive(Clone, Debug)]
pub(crate) struct State {
    pub(crate) theta: Vec<f64>,
    pub(crate) rho: Vec<f64>,
    pub(crate) log_prob: f64,
    pub(crate) grad: Vec<f64>,
}
