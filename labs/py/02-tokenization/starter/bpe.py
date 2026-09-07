"""Byte-level BPE from scratch: train, encode, decode, exact roundtrip."""


class BPETokenizer:
    def __init__(self, vocab_size):
        """vocab_size includes the 256 base byte tokens. Merges = vocab_size - 256."""

    def train(self, corpus):
        """Learn merges: repeatedly merge the most frequent adjacent byte pair.
        Tie-break: lexicographically smallest pair. Store merges in learned order."""

    def encode(self, text):
        """Bytes -> list of token ids. Apply merges by rank (lowest rank first,
        anywhere in the sequence), repeating until no merge applies.
        Never produce more distinct ids than vocab_size."""

    def decode(self, ids):
        """Token ids -> exact original string. Must roundtrip any unicode text."""

    def vocab_growth(self, corpus, sizes):
        """Return [(size, n_merges)] for each requested vocab size (= size - 256)."""

    @property
    def merges(self):
        """List of learned merges in order, as (left_bytes, right_bytes) pairs."""
