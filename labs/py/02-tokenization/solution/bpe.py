"""Byte-level BPE from scratch: train, encode, decode, exact roundtrip."""


class BPETokenizer:
    def __init__(self, vocab_size):
        self.vocab_size = vocab_size
        # id -> bytes; base bytes 0..255
        self.vocab = {i: bytes([i]) for i in range(256)}
        self.merge_rules = []          # list of (left_bytes, right_bytes)
        self._merge_rank = {}          # (left, right) -> rank

    def train(self, corpus):
        data = corpus.encode("utf-8")
        tokens = [bytes([b]) for b in data]
        n_merges = self.vocab_size - 256
        for _ in range(n_merges):
            # count adjacent pairs
            counts = {}
            for i in range(len(tokens) - 1):
                pair = (tokens[i], tokens[i + 1])
                counts[pair] = counts.get(pair, 0) + 1
            if not counts:
                break
            # most frequent; tie-break lexicographically smallest pair
            best = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            if counts[best] < 2:
                break
            merged = best[0] + best[1]
            self.merge_rules.append(best)
            self._merge_rank[best] = len(self.merge_rules) - 1
            new_id = 256 + len(self.merge_rules) - 1
            self.vocab[new_id] = merged
            # apply the merge across the sequence
            out = []
            i = 0
            while i < len(tokens):
                if (i < len(tokens) - 1 and tokens[i] == best[0]
                        and tokens[i + 1] == best[1]):
                    out.append(merged)
                    i += 2
                else:
                    out.append(tokens[i])
                    i += 1
            tokens = out
        return self

    def encode(self, text):
        tokens = [bytes([b]) for b in text.encode("utf-8")]
        while True:
            # find the lowest-rank applicable pair anywhere in the sequence
            best_rank = None
            best_i = None
            for i in range(len(tokens) - 1):
                r = self._merge_rank.get((tokens[i], tokens[i + 1]))
                if r is not None and (best_rank is None or r < best_rank):
                    best_rank = r
                    best_i = i
            if best_rank is None:
                break
            i = best_i
            merged = tokens[i] + tokens[i + 1]
            tokens = tokens[:i] + [merged] + tokens[i + 2:]
        bytes_to_id = {v: k for k, v in self.vocab.items()}
        return [bytes_to_id[t] for t in tokens]

    def decode(self, ids):
        return b"".join(self.vocab[i] for i in ids).decode("utf-8", errors="replace")

    def vocab_growth(self, corpus, sizes):
        out = []
        for s in sizes:
            t = BPETokenizer(s)
            t.train(corpus)
            out.append((s, len(t.merge_rules)))
        return out

    @property
    def merges(self):
        return list(self.merge_rules)
