//! Broadcasting operands for the fused vector primitives.
//!
//! A fused primitive such as [`normal_lpdf`](crate::normal_lpdf) accepts each
//! argument as anything implementing [`Operand`]: a scalar `S`, a slice
//! `&[S]`, a `&Vec<S>`, or one of the explicit wrappers [`Const`], [`Data`],
//! [`Shifted`] and [`Linear`]. Slices broadcast against scalars; all slice
//! arguments must have equal length. Data operands contribute nothing to the
//! tape, so `normal_lpdf(Data(&y), &theta, Data(&sigma))` records exactly one
//! node with `theta.len()` partials.
//!
//! The recording protocol (everything except `len` and `value`) is only
//! exercised by the [`Var`](crate::Var) implementation of the primitives; the
//! `f64` implementations read values only.

use crate::tape::CONST_INDEX;
use crate::{Scalar, Tape};

/// How a vector operand's per-element partials map onto the tape.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum VectorPart {
    /// No per-element parents (data, constants, broadcast scalars).
    Skip,
    /// Element `i` has parent `first + i`: partials are stored without indices
    /// and swept with a contiguous `axpy`.
    Contiguous(u32),
    /// Element `i` has parent `index(i)`: stored as index/partial pairs.
    Indexed,
}

/// A (possibly broadcast) argument to a fused primitive.
pub trait Operand<S: Scalar>: Copy {
    /// True when the operand carries no gradient (data or constants).
    const IS_DATA: bool;
    /// Number of scalar parents shared by all elements (a broadcast `Var`, or
    /// the slope and intercept of a [`Linear`]).
    const SCALAR_PARENTS: usize = 0;
    /// True when each element has at most one parent, reached with chain
    /// factor one, and there are no extra scalar parents beyond a broadcast
    /// scalar. Enables the single-node fast path when the broadcast length is
    /// one.
    const SIMPLE: bool = true;

    /// `None` for scalars (broadcast), `Some(n)` for vectors.
    fn len(&self) -> Option<usize>;
    /// True for a zero-length vector operand.
    fn is_empty(&self) -> bool {
        self.len() == Some(0)
    }
    /// Element value.
    fn value(&self, i: usize) -> f64;

    /// Layout of the per-element parents on `tape`.
    fn vector_part(&self, _tape: &Tape) -> VectorPart {
        VectorPart::Skip
    }
    /// Tape index of the parent of element `i` (scattered layouts and the
    /// single-element fast path).
    fn index(&self, _i: usize) -> u32 {
        CONST_INDEX
    }
    /// `d value(i) / d parent(i)`.
    fn chain(&self, _i: usize) -> f64 {
        1.0
    }
    /// Tape index of scalar parent `k`.
    fn scalar_parent(&self, _k: usize) -> u32 {
        CONST_INDEX
    }
    /// `d value(i) / d scalar_parent(k)`.
    fn scalar_weight(&self, _k: usize, _i: usize) -> f64 {
        1.0
    }
}

/// A constant scalar argument.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Const(pub f64);

/// A slice of data (no gradient).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Data<'a>(pub &'a [f64]);

/// A slice of scalars shifted by a constant: element `i` is `x[i] + shift`.
///
/// Because `d(x + c)/dx = 1`, this costs no tape node. Use it, for instance,
/// to express a random-walk mean `x[t-1] + drift` without materialising a
/// shifted vector.
#[derive(Clone, Copy, Debug)]
pub struct Shifted<'a, S>(pub &'a [S], pub f64);

/// A linear predictor `intercept + slope * x[i]` with scalar `intercept` and
/// `slope`, recorded inside the consuming primitive instead of as `2 * n`
/// scalar nodes. Typical use: `normal_lpdf(Data(&y), Linear::new(mu, tau, &z),
/// Data(&se))` for a noncentered hierarchical mean.
#[derive(Clone, Copy, Debug)]
pub struct Linear<'a, S> {
    /// Added to every element.
    pub intercept: S,
    /// Multiplies every element of `x`.
    pub slope: S,
    /// The vector.
    pub x: &'a [S],
}

impl<'a, S: Scalar> Linear<'a, S> {
    /// `intercept + slope * x[i]`.
    pub fn new(intercept: S, slope: S, x: &'a [S]) -> Self {
        Self {
            intercept,
            slope,
            x,
        }
    }
}

/// Layout of a slice: a sub-slice of the input buffer is contiguous by
/// construction (an `O(1)` address check); otherwise the indices are scanned.
#[inline]
pub(crate) fn slice_part<S: Scalar>(x: &[S], tape: &Tape) -> VectorPart {
    let Some(first) = x.first() else {
        return VectorPart::Contiguous(CONST_INDEX);
    };
    if let Some(start) = S::input_slice_start(x, tape) {
        return VectorPart::Contiguous(start);
    }
    let first = first.tape_index();
    if x.iter()
        .enumerate()
        .all(|(i, v)| v.tape_index() == first + i as u32)
    {
        VectorPart::Contiguous(first)
    } else {
        VectorPart::Indexed
    }
}

impl<S: Scalar> Operand<S> for S {
    const IS_DATA: bool = false;
    const SCALAR_PARENTS: usize = 1;
    #[inline]
    fn len(&self) -> Option<usize> {
        None
    }
    #[inline]
    fn value(&self, _i: usize) -> f64 {
        Scalar::value(*self)
    }
    #[inline]
    fn index(&self, _i: usize) -> u32 {
        self.tape_index()
    }
    #[inline]
    fn scalar_parent(&self, _k: usize) -> u32 {
        self.tape_index()
    }
}

impl<S: Scalar> Operand<S> for &[S] {
    const IS_DATA: bool = false;
    #[inline]
    fn len(&self) -> Option<usize> {
        Some(<[S]>::len(self))
    }
    #[inline]
    fn value(&self, i: usize) -> f64 {
        Scalar::value(self[i])
    }
    #[inline]
    fn vector_part(&self, tape: &Tape) -> VectorPart {
        slice_part(self, tape)
    }
    #[inline]
    fn index(&self, i: usize) -> u32 {
        self[i].tape_index()
    }
}

impl<S: Scalar> Operand<S> for &Vec<S> {
    const IS_DATA: bool = false;
    #[inline]
    fn len(&self) -> Option<usize> {
        Some(Vec::len(self))
    }
    #[inline]
    fn value(&self, i: usize) -> f64 {
        Scalar::value(self[i])
    }
    #[inline]
    fn vector_part(&self, tape: &Tape) -> VectorPart {
        slice_part(self, tape)
    }
    #[inline]
    fn index(&self, i: usize) -> u32 {
        self[i].tape_index()
    }
}

impl<S: Scalar> Operand<S> for Shifted<'_, S> {
    const IS_DATA: bool = false;
    #[inline]
    fn len(&self) -> Option<usize> {
        Some(self.0.len())
    }
    #[inline]
    fn value(&self, i: usize) -> f64 {
        Scalar::value(self.0[i]) + self.1
    }
    #[inline]
    fn vector_part(&self, tape: &Tape) -> VectorPart {
        slice_part(self.0, tape)
    }
    #[inline]
    fn index(&self, i: usize) -> u32 {
        self.0[i].tape_index()
    }
}

impl<S: Scalar> Operand<S> for Linear<'_, S> {
    const IS_DATA: bool = false;
    const SCALAR_PARENTS: usize = 2;
    const SIMPLE: bool = false;
    #[inline]
    fn len(&self) -> Option<usize> {
        Some(self.x.len())
    }
    #[inline]
    fn value(&self, i: usize) -> f64 {
        Scalar::value(self.intercept) + Scalar::value(self.slope) * Scalar::value(self.x[i])
    }
    #[inline]
    fn vector_part(&self, tape: &Tape) -> VectorPart {
        slice_part(self.x, tape)
    }
    #[inline]
    fn index(&self, i: usize) -> u32 {
        self.x[i].tape_index()
    }
    #[inline]
    fn chain(&self, _i: usize) -> f64 {
        Scalar::value(self.slope)
    }
    #[inline]
    fn scalar_parent(&self, k: usize) -> u32 {
        if k == 0 {
            self.slope.tape_index()
        } else {
            self.intercept.tape_index()
        }
    }
    #[inline]
    fn scalar_weight(&self, k: usize, i: usize) -> f64 {
        if k == 0 {
            Scalar::value(self.x[i])
        } else {
            1.0
        }
    }
}

impl<S: Scalar> Operand<S> for Const {
    const IS_DATA: bool = true;
    #[inline]
    fn len(&self) -> Option<usize> {
        None
    }
    #[inline]
    fn value(&self, _i: usize) -> f64 {
        self.0
    }
}

impl<S: Scalar> Operand<S> for Data<'_> {
    const IS_DATA: bool = true;
    #[inline]
    fn len(&self) -> Option<usize> {
        Some(self.0.len())
    }
    #[inline]
    fn value(&self, i: usize) -> f64 {
        self.0[i]
    }
}

/// Broadcast length of a set of operands; panics on mismatched vector lengths.
#[inline]
pub(crate) fn broadcast_len(lens: &[Option<usize>]) -> usize {
    let mut n: Option<usize> = None;
    for l in lens.iter().flatten() {
        match n {
            None => n = Some(*l),
            Some(m) => assert_eq!(
                m, *l,
                "fused primitive: vector operands must have equal length"
            ),
        }
    }
    n.unwrap_or(1)
}
