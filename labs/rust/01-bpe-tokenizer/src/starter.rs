//! STARTER — compiles, panics at runtime. Make the tests pass without
//! touching lib.rs or tests/.

use crate::{DecodeError, Merge};

/// Train byte-level BPE. The vocabulary starts as the 256 raw byte ids
/// (`0..=255`); every merge appends id `256 + merge_index`. At each step,
/// count adjacent pairs in the current id sequence and merge the MOST
/// FREQUENT one — ties break to the LOWEST pair (lexicographic tuple order).
/// Stop early if the corpus runs out of pairs before `vocab_size`.
pub fn train(_text: &str, _vocab_size: usize) -> Vec<Merge> {
    todo!("step 1: counting + merging loop")
}

/// Encode text: start from UTF-8 bytes, then repeatedly apply the
/// EARLIEST-LEARNED applicable merge (lowest rank wins) until none applies.
/// Bytes whose pairs were never merged simply stay raw — there is no <UNK>.
pub fn encode(_text: &str, _merges: &[Merge]) -> Vec<u32> {
    todo!("step 2: rank-driven merge loop")
}

/// Decode ids back to a String by rebuilding the id → bytes table from the
/// merges. Errors are clean: unknown ids and invalid UTF-8 are `DecodeError`s.
pub fn decode(_ids: &[u32], _merges: &[Merge]) -> Result<String, DecodeError> {
    todo!("step 3: rebuild the vocabulary and join")
}
