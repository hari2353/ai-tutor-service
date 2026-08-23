//! SOLUTION — the reference. Read it AFTER your own version passes.

use std::collections::HashMap;

use crate::{DecodeError, Merge};

/// Replace every non-overlapping occurrence of `pair` in `ids` with `new_id`,
/// scanning left to right.
fn merge_pass(ids: &[u32], pair: (u32, u32), new_id: u32) -> Vec<u32> {
    let mut out = Vec::with_capacity(ids.len());
    let mut i = 0;
    while i < ids.len() {
        if i + 1 < ids.len() && (ids[i], ids[i + 1]) == pair {
            out.push(new_id);
            i += 2;
        } else {
            out.push(ids[i]);
            i += 1;
        }
    }
    out
}

pub fn train(text: &str, vocab_size: usize) -> Vec<Merge> {
    let mut ids: Vec<u32> = text.bytes().map(u32::from).collect();
    let mut merges: Vec<Merge> = Vec::new();

    while 256 + merges.len() < vocab_size && ids.len() >= 2 {
        let mut counts: HashMap<(u32, u32), usize> = HashMap::new();
        for w in ids.windows(2) {
            *counts.entry((w[0], w[1])).or_insert(0) += 1;
        }
        // Most frequent pair; ties break to the LOWEST pair. `max_by` with a
        // count-then-reversed-pair comparator makes the smallest tied pair win.
        let best = match counts
            .iter()
            .max_by(|a, b| a.1.cmp(b.1).then_with(|| b.0.cmp(a.0)))
            .map(|(p, _)| *p)
        {
            Some(p) => p,
            None => break,
        };
        let new_id = (256 + merges.len()) as u32;
        merges.push(best);
        ids = merge_pass(&ids, best, new_id);
    }
    merges
}

pub fn encode(text: &str, merges: &[Merge]) -> Vec<u32> {
    let mut ids: Vec<u32> = text.bytes().map(u32::from).collect();
    let ranks: HashMap<&Merge, usize> =
        merges.iter().enumerate().map(|(i, m)| (m, i)).collect();

    loop {
        // Find the applicable pair with the LOWEST rank (earliest learned).
        let mut best: Option<(usize, Merge)> = None;
        for w in ids.windows(2) {
            if let Some(&r) = ranks.get(&(w[0], w[1])) {
                if best.map_or(true, |(br, _)| r < br) {
                    best = Some((r, (w[0], w[1])));
                }
            }
        }
        match best {
            None => break,
            Some((r, pair)) => {
                ids = merge_pass(&ids, pair, (256 + r) as u32);
            }
        }
    }
    ids
}

pub fn decode(ids: &[u32], merges: &[Merge]) -> Result<String, DecodeError> {
    let mut vocab: HashMap<u32, Vec<u8>> = (0..=255u32).map(|b| (b, vec![b as u8])).collect();
    for (i, &(l, r)) in merges.iter().enumerate() {
        let lt = vocab
            .get(&l)
            .cloned()
            .ok_or(DecodeError::UnknownId(l))?;
        let rt = vocab
            .get(&r)
            .cloned()
            .ok_or(DecodeError::UnknownId(r))?;
        let mut bytes = lt;
        bytes.extend(rt);
        vocab.insert((256 + i) as u32, bytes);
    }

    let mut out: Vec<u8> = Vec::new();
    for &id in ids {
        match vocab.get(&id) {
            Some(bytes) => out.extend_from_slice(bytes),
            None => return Err(DecodeError::UnknownId(id)),
        }
    }
    String::from_utf8(out).map_err(|_| DecodeError::InvalidUtf8)
}
