//! Byte-level BPE tokenizer, from scratch.
//!
//! Shared infrastructure lives here (compiled in every configuration).
//! The primitives are selected at compile time:
//! - default:      `src/starter.rs`  — compiles, fails at runtime (that is the point)
//! - `--features solution`: `src/solution.rs` — the reference implementation

/// One learned merge: `(left_id, right_id)` joined into id `256 + rank`.
pub type Merge = (u32, u32);

#[derive(Debug, PartialEq, Eq)]
pub enum DecodeError {
    /// An id outside `[0, 256 + merges.len())`.
    UnknownId(u32),
    /// The decoded byte sequence is not valid UTF-8.
    InvalidUtf8,
}

#[cfg(not(feature = "solution"))]
mod starter;
#[cfg(not(feature = "solution"))]
pub use starter::{decode, encode, train};

#[cfg(feature = "solution")]
mod solution;
#[cfg(feature = "solution")]
pub use solution::{decode, encode, train};
