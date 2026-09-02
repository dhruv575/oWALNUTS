//! The arena tape: a struct-of-arrays Wengert list reused across calls.
//!
//! Every [`Var`](crate::Var) is an index into the thread-local tape. Index 0
//! is the shared constant slot, indices `1..=n_inputs` are the inputs (they
//! have no stored node), and every later index is one recorded operation.
//! Scalar nodes store their operand indices and partials inline; the fused
//! vector primitives record one `Nary` node made of *segments*, each covering
//! one operand: a segment over a contiguous run of tape indices stores only
//! its partials (its reverse sweep is a plain `axpy`), while a segment over
//! scattered indices stores index/partial pairs. Nothing is allocated per node
//! once the buffers have grown to a model's size.

use crate::operand::VectorPart;
use std::cell::RefCell;

/// Index of the shared constant slot. Constants are `Var`s whose adjoint is
/// accumulated into this slot and ignored, so operations never branch on
/// "is this operand a constant".
pub(crate) const CONST_INDEX: u32 = 0;

/// One recorded operation.
#[derive(Clone, Copy, Debug)]
pub(crate) enum Node {
    /// `y = f(a)` with `dy/da = da`.
    Unary { a: u32, da: f64 },
    /// `y = f(a, b)`.
    Binary { a: u32, b: u32, da: f64, db: f64 },
    /// `y = f(a, b, c)`.
    Ternary {
        a: u32,
        b: u32,
        c: u32,
        da: f64,
        db: f64,
        dc: f64,
    },
    /// A fused reduction over the segments `Tape::segments[start..start+len]`.
    Nary { start: u32, len: u32 },
    /// Placeholder for an output of a block node (its adjoint is consumed by
    /// the block node that closes the block).
    Filler,
    /// Cumulative sum `out[i] = sum_{j <= i} (scale * x[first + j] + shift)`
    /// over the contiguous inputs `first..first+len`, whose `len` outputs are
    /// the tape indices ending at this node. Its reverse sweep is one reverse
    /// scan of the output adjoints.
    Cumsum { first: u32, len: u32, scale: f64 },
}

/// One operand of a fused node.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Segment {
    /// Number of partials.
    len: u32,
    /// Offset of the partials in `Tape::partials`.
    partial_start: u32,
    /// For a contiguous segment, the first tape index; for a scattered one,
    /// the offset of the indices in `Tape::indices`.
    target: u32,
    /// True when the parents are the tape indices `target..target+len`.
    contiguous: bool,
}

/// Where a vector operand's partials go.
#[derive(Debug)]
pub(crate) enum Slot<'a> {
    /// Data: nothing recorded.
    Skip,
    /// Contiguous parents: partials only.
    Contiguous(&'a mut [f64]),
    /// Scattered parents: partial and index per element.
    Indexed(&'a mut [f64], &'a mut [u32]),
}

/// A reusable reverse-mode tape.
#[derive(Debug, Default)]
pub struct Tape {
    n_inputs: usize,
    /// Address range `[start, end)` of the input buffer handed to the model
    /// for the current evaluation; a slice inside it is contiguous on the
    /// tape by construction.
    input_range: (usize, usize),
    nodes: Vec<Node>,
    adjoint: Vec<f64>,
    partials: Vec<f64>,
    indices: Vec<u32>,
    segments: Vec<Segment>,
    inputs: Vec<crate::Var>,
}

impl Tape {
    /// An empty tape with no capacity (grows on first use, then stays).
    pub const fn new() -> Self {
        Self {
            n_inputs: 0,
            input_range: (0, 0),
            nodes: Vec::new(),
            adjoint: Vec::new(),
            partials: Vec::new(),
            indices: Vec::new(),
            segments: Vec::new(),
            inputs: Vec::new(),
        }
    }

    /// Reset for `q.len()` inputs and hand out the reusable input buffer
    /// filled with `Var`s at indices `1..=n` (returned with `return_inputs`).
    pub(crate) fn begin(&mut self, q: &[f64]) -> Vec<crate::Var> {
        self.reset(q.len());
        let mut inputs = std::mem::take(&mut self.inputs);
        inputs.clear();
        inputs.reserve(q.len());
        for (i, &x) in q.iter().enumerate() {
            inputs.push(crate::Var::new(x, i as u32 + 1));
        }
        let start = inputs.as_ptr() as usize;
        self.input_range = (start, start + q.len() * std::mem::size_of::<crate::Var>());
        inputs
    }

    pub(crate) fn return_inputs(&mut self, inputs: Vec<crate::Var>) {
        self.input_range = (0, 0);
        self.inputs = inputs;
    }

    /// If `x` lies inside the current input buffer, the tape index of its
    /// first element.
    #[inline]
    pub(crate) fn input_slice_start(&self, x: &[crate::Var]) -> Option<u32> {
        let start = x.as_ptr() as usize;
        let end = start + std::mem::size_of_val(x);
        if start >= self.input_range.0 && end <= self.input_range.1 {
            let offset = (start - self.input_range.0) / std::mem::size_of::<crate::Var>();
            Some(offset as u32 + 1)
        } else {
            None
        }
    }

    /// Clear all recorded operations (keeping capacity) and declare
    /// `n_inputs` inputs at indices `1..=n_inputs`.
    pub fn reset(&mut self, n_inputs: usize) {
        self.n_inputs = n_inputs;
        self.nodes.clear();
        self.partials.clear();
        self.indices.clear();
        self.segments.clear();
    }

    /// Number of recorded operations (inputs and the constant slot excluded).
    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    /// True when no operation is recorded.
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    /// Number of partials stored for fused nodes.
    pub fn partials_len(&self) -> usize {
        self.partials.len()
    }

    /// Number of scattered indices stored for fused nodes.
    pub fn indices_len(&self) -> usize {
        self.indices.len()
    }

    #[inline]
    fn push(&mut self, node: Node) -> u32 {
        let index = (self.n_inputs + 1 + self.nodes.len()) as u32;
        self.nodes.push(node);
        index
    }

    #[inline]
    pub(crate) fn push_unary(&mut self, a: u32, da: f64) -> u32 {
        self.push(Node::Unary { a, da })
    }

    #[inline]
    pub(crate) fn push_binary(&mut self, a: u32, b: u32, da: f64, db: f64) -> u32 {
        self.push(Node::Binary { a, b, da, db })
    }

    #[inline]
    pub(crate) fn push_ternary(
        &mut self,
        a: u32,
        b: u32,
        c: u32,
        da: f64,
        db: f64,
        dc: f64,
    ) -> u32 {
        self.push(Node::Ternary {
            a,
            b,
            c,
            da,
            db,
            dc,
        })
    }

    /// Record a cumulative-sum block over the contiguous inputs
    /// `first..first+len`; returns the tape index of the first output.
    #[inline]
    pub(crate) fn push_cumsum(&mut self, first: u32, len: usize, scale: f64) -> u32 {
        let start = (self.n_inputs + 1 + self.nodes.len()) as u32;
        self.nodes
            .extend(std::iter::repeat_n(Node::Filler, len - 1));
        self.nodes.push(Node::Cumsum {
            first,
            len: len as u32,
            scale,
        });
        start
    }

    /// Begin a fused node: returns the segment offset to pass to `push_nary`.
    #[inline]
    pub(crate) fn nary_begin(&self) -> u32 {
        self.segments.len() as u32
    }

    /// Open one segment per operand for a fused node of broadcast length `n`,
    /// returning the slots to fill (in operand order).
    #[inline]
    pub(crate) fn open_segments<const K: usize>(
        &mut self,
        parts: [VectorPart; K],
        n: usize,
    ) -> [Slot<'_>; K] {
        let n_vector = parts
            .iter()
            .filter(|p| !matches!(p, VectorPart::Skip))
            .count();
        let n_indexed = parts
            .iter()
            .filter(|p| matches!(p, VectorPart::Indexed))
            .count();
        let p_start = self.partials.len();
        let i_start = self.indices.len();
        self.partials.resize(p_start + n * n_vector, 0.0);
        self.indices.resize(i_start + n * n_indexed, CONST_INDEX);
        let Tape {
            partials,
            indices,
            segments,
            ..
        } = self;
        let mut rest_p: &mut [f64] = &mut partials[p_start..];
        let mut rest_i: &mut [u32] = &mut indices[i_start..];
        let mut p_off = p_start;
        let mut i_off = i_start;
        parts.map(|part| match part {
            VectorPart::Skip => Slot::Skip,
            VectorPart::Contiguous(first) => {
                let (head, tail) = std::mem::take(&mut rest_p).split_at_mut(n);
                rest_p = tail;
                segments.push(Segment {
                    len: n as u32,
                    partial_start: p_off as u32,
                    target: first,
                    contiguous: true,
                });
                p_off += n;
                Slot::Contiguous(head)
            }
            VectorPart::Indexed => {
                let (head, tail) = std::mem::take(&mut rest_p).split_at_mut(n);
                rest_p = tail;
                let (ihead, itail) = std::mem::take(&mut rest_i).split_at_mut(n);
                rest_i = itail;
                segments.push(Segment {
                    len: n as u32,
                    partial_start: p_off as u32,
                    target: i_off as u32,
                    contiguous: false,
                });
                p_off += n;
                i_off += n;
                Slot::Indexed(head, ihead)
            }
        })
    }

    /// Record one scattered parent as a one-element segment.
    #[inline]
    pub(crate) fn single_parent(&mut self, index: u32, partial: f64) {
        self.segments.push(Segment {
            len: 1,
            partial_start: self.partials.len() as u32,
            target: self.indices.len() as u32,
            contiguous: false,
        });
        self.partials.push(partial);
        self.indices.push(index);
    }

    /// Close the fused node whose segments start at `begin`.
    #[inline]
    pub(crate) fn push_nary(&mut self, begin: u32) -> u32 {
        let len = self.segments.len() as u32 - begin;
        self.push(Node::Nary { start: begin, len })
    }

    /// Reverse sweep from `output`, writing `d output / d input_k` for the
    /// inputs at indices `1..=gradient.len()` into `gradient`.
    pub fn gradient(&mut self, output: u32, gradient: &mut [f64]) {
        let n_inputs = self.n_inputs;
        debug_assert_eq!(gradient.len(), n_inputs);
        let base = n_inputs + 1;
        let total = base + self.nodes.len();
        self.adjoint.clear();
        self.adjoint.resize(total, 0.0);
        self.adjoint[output as usize] = 1.0;
        let adj = &mut self.adjoint;
        let partials = &self.partials;
        let indices = &self.indices;
        let segments = &self.segments;
        for (k, node) in self.nodes.iter().enumerate().rev() {
            let a_out = adj[base + k];
            if let Node::Cumsum { first, len, scale } = *node {
                // Reverse scan: d/dx_j = scale * sum_{i >= j} adjoint(out_i).
                let out_start = base + k + 1 - len as usize;
                let mut acc = 0.0;
                for i in (0..len as usize).rev() {
                    acc += adj[out_start + i];
                    adj[first as usize + i] += scale * acc;
                }
                continue;
            }
            if a_out == 0.0 {
                continue;
            }
            match *node {
                Node::Filler | Node::Cumsum { .. } => {}
                Node::Unary { a, da } => {
                    adj[a as usize] += a_out * da;
                }
                Node::Binary { a, b, da, db } => {
                    adj[a as usize] += a_out * da;
                    adj[b as usize] += a_out * db;
                }
                Node::Ternary {
                    a,
                    b,
                    c,
                    da,
                    db,
                    dc,
                } => {
                    adj[a as usize] += a_out * da;
                    adj[b as usize] += a_out * db;
                    adj[c as usize] += a_out * dc;
                }
                Node::Nary { start, len } => {
                    for seg in &segments[start as usize..(start + len) as usize] {
                        let ps = seg.partial_start as usize;
                        let len = seg.len as usize;
                        let par = &partials[ps..ps + len];
                        if seg.contiguous {
                            let t = seg.target as usize;
                            for (a, p) in adj[t..t + len].iter_mut().zip(par) {
                                *a += a_out * p;
                            }
                        } else {
                            let t = seg.target as usize;
                            for (&j, p) in indices[t..t + len].iter().zip(par) {
                                adj[j as usize] += a_out * p;
                            }
                        }
                    }
                }
            }
        }
        gradient.copy_from_slice(&self.adjoint[1..=n_inputs]);
    }
}

thread_local! {
    pub(crate) static TAPE: RefCell<Tape> = const { RefCell::new(Tape::new()) };
}

/// Run `f` with exclusive access to this thread's tape.
///
/// Must not be called re-entrantly (no `Var` arithmetic inside `f`).
#[inline]
pub(crate) fn with_tape<R>(f: impl FnOnce(&mut Tape) -> R) -> R {
    TAPE.with(|t| f(&mut t.borrow_mut()))
}
