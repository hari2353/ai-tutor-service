//! Lab tests. Run:
//!   cargo test                        → starter, MUST FAIL (todo! panics)
//!   cargo test --features solution    → reference, MUST PASS

use bpe_tokenizer::{decode, encode, train, DecodeError};

// ------------------------------------------------------------------ training

#[test]
fn vocab_starts_at_256_and_each_merge_appends_one_id() {
    // "abab" → one merge is enough to reach vocab_size 257.
    let merges = train("abab", 257);
    assert_eq!(merges, vec![(97, 98)]);
}

#[test]
fn ties_break_to_the_lowest_pair() {
    // All three pairs occur once; ("c","d") is seen FIRST while scanning,
    // but ("a","b") is the lowest tuple and must win.
    let merges = train("cdab", 257);
    assert_eq!(merges[0], (97, 98), "got {:?}", merges);
}

#[test]
fn crafted_corpus_full_merge_chain() {
    // abcabcabc: (a,b) ties with (b,c) — lowest wins; then (AB,c); then (ABc,ABc).
    let m = train("abcabcabc", 259);
    assert_eq!(m, vec![(97, 98), (256, 99), (257, 257)]);
    // The learned chain compresses the training fragment to ONE id.
    assert_eq!(encode("abcabc", &m), vec![258]);
}

#[test]
fn training_stops_early_when_the_corpus_runs_out_of_pairs() {
    assert!(train("x", 300).is_empty(), "a single byte has no pairs");
    // "aaaa" → ("a","a")→X, then (X,X)→Y, then one token left: stop.
    let merges = train("aaaa", 999);
    assert_eq!(merges.len(), 2);
    assert_eq!(merges[0], (97, 97));
    assert_eq!(merges[1], (256, 256));
}

#[test]
fn training_is_deterministic() {
    let a = train("the quick brown fox jumps over the lazy dog", 280);
    let b = train("the quick brown fox jumps over the lazy dog", 280);
    assert_eq!(a, b);
}

// ------------------------------------------------------------------ encoding

#[test]
fn encoding_applies_the_earliest_learned_merge_first() {
    // Both merges apply to [97,98,99]; rank 0 — (98,99) here — must win even
    // though (97,98) starts further left. Lowest RANK beats leftmost position.
    let merges = vec![(98u32, 99u32), (97u32, 98u32)];
    assert_eq!(encode("abc", &merges), vec![97, 256]);
}

#[test]
fn unknown_text_stays_as_raw_bytes_there_is_no_unk() {
    assert_eq!(encode("xyz", &[]), vec![120, 121, 122]);
}

// --------------------------------------------------------------- round-trips

#[test]
fn round_trips_ascii() {
    let s = "the quick brown fox";
    let m = train(s, 262);
    let ids = encode(s, &m);
    assert_eq!(decode(&ids, &m).unwrap(), s);
}

#[test]
fn round_trips_unicode_emoji_cjk() {
    for s in ["café", "☕ rust ☕", "日本語のテキスト", "family 🚀 👨‍👩‍👧"] {
        let m = train(s, 300.min(256 + s.len()));
        let ids = encode(s, &m);
        assert_eq!(
            decode(&ids, &m).as_deref(),
            Ok(s),
            "round-trip failed for {s:?}"
        );
    }
}

#[test]
fn trained_merges_compress_the_training_text() {
    let corpus = "aaabbaab aaabbaab aaabbaab aaabbaab";
    let m = train(corpus, 270);
    let n = encode(corpus, &m).len();
    assert!(
        n < corpus.bytes().len(),
        "expected compression, got {n} tokens for {} bytes",
        corpus.bytes().len()
    );
}

// ------------------------------------------------------------------ decoding

#[test]
fn decoding_an_unknown_id_is_a_clean_error() {
    let err = decode(&[9999], &[(97, 98)]).unwrap_err();
    assert_eq!(err, DecodeError::UnknownId(9999));
}

#[test]
fn decoding_bytes_that_are_not_utf8_surfaces_as_invalidutf8() {
    // 0xFF alone can never start a valid UTF-8 sequence.
    assert_eq!(decode(&[255], &[]), Err(DecodeError::InvalidUtf8));
}
