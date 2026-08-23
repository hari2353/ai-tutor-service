import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { impl } from "./impl.ts";
import { DEFAULT_SEPARATORS } from "../src/types.ts";

const DOC = [
  "# Deployment guide",
  "",
  "Deploy the gateway first. It owns routing and rate limits.",
  "The retriever comes second — it needs the gateway up.",
  "",
  "Rollbacks are manual. Keep the previous image tag handy.",
].join("\n");

// ------------------------------------------------------------------ fixed

describe("fixedChunks", () => {
  const { fixedChunks } = impl;

  it("windows with stride size - overlap, last window truncated", () => {
    const chunks = fixedChunks("abcdefghij", 4, 2); // stride 2
    assert.deepEqual(chunks, ["abcd", "cdef", "efgh", "ghij"]);
  });

  it("returns [] for empty text", () => {
    assert.deepEqual(fixedChunks("", 5, 2), []);
  });

  it("rejects zero-stride and degenerate configs loudly", () => {
    assert.throws(() => fixedChunks("abc", 3, 3), { name: "RangeError", message: /overlap/ });
    assert.throws(() => fixedChunks("abc", 2, 5), { name: "RangeError", message: /overlap/ });
    assert.throws(() => fixedChunks("abc", 0, 0), { name: "RangeError", message: /size/ });
  });

  it("never emits a redundant duplicate tail window", () => {
    // Window at start 2 already reaches the end — nothing may follow it.
    const chunks = fixedChunks("abcdefgh", 6, 4);
    assert.deepEqual(chunks, ["abcdef", "cdefgh"]);
  });

  it("truncates the final window when the length does not align", () => {
    assert.deepEqual(fixedChunks("abcdefg", 4, 2), ["abcd", "cdef", "efg"]);
  });
});

// ------------------------------------------------------------------ recursive

describe("recursiveChunks", () => {
  const { recursiveChunks } = impl;

  it("keeps separators glued so overlap=0 reconstructs the text EXACTLY", () => {
    const chunks = recursiveChunks(DOC, 60);
    assert.equal(chunks.join(""), DOC);
    assert.ok(chunks.length > 1, "expected the doc to actually split");
  });

  it("prefers coarse separators before fine ones", () => {
    const para = "A\n\nB\n\nC"; // paragraph breaks exist, so they decide
    for (const c of recursiveChunks(para, 2)) {
      assert.ok(!c.includes("\n\n"), `chunk crossed a paragraph boundary: ${JSON.stringify(c)}`);
    }
  });

  it("falls through the ladder to characters for an unbreakable run", () => {
    const unbreakable = "x".repeat(95);
    const chunks = recursiveChunks(`ok ${unbreakable} end`, 20);
    assert.ok(chunks.every((c) => c.length <= 20), "every chunk must honour size");
    assert.equal(chunks.join(""), `ok ${unbreakable} end`);
  });

  it("respects custom separator ladders", () => {
    const csv = "a,b,c,d,e,f";
    const chunks = recursiveChunks(csv, 4, [","]);
    assert.deepEqual(chunks, ["a,b,", "c,d,", "e,f"]);
  });

  it("with overlap > 0 prefixes context but never exceeds size", () => {
    const long = "alpha beta gamma delta epsilon zeta eta theta iota kappa".repeat(2);
    const chunks = recursiveChunks(long, 24, DEFAULT_SEPARATORS, 6);
    assert.ok(chunks.every((c) => c.length <= 24), "no chunk may exceed size");
    // "up to `overlap` characters of context": at least one later chunk must
    // actually carry a prefix lifted from its predecessor's tail.
    const carriesContext = chunks.slice(1).some((c, i) => {
      const prev = chunks[i];
      for (let k = Math.min(6, prev.length, c.length); k > 0; k--) {
        if (c.startsWith(prev.slice(prev.length - k))) return true;
      }
      return false;
    });
    assert.ok(carriesContext, "expected overlap context between consecutive chunks");
  });

  it("satisfies the coverage property on a realistic document", () => {
    const chunks = recursiveChunks(DOC, 50);
    impl.assertNoLoss(chunks, DOC, { kind: "recursive" });
  });
});

// ------------------------------------------------------------------ sentences

describe("sentenceChunks", () => {
  const { sentenceChunks } = impl;

  it("packs whole sentences within size", () => {
    const text = "One. Two. Three. Four.";
    for (const c of sentenceChunks(text, 10)) {
      assert.ok(c.length <= 10, `chunk too big: ${JSON.stringify(c)}`);
    }
  });

  it("repeats the last overlapSentences sentences as context", () => {
    const text = "S1. S2. S3. S4. S5.";
    const chunks = sentenceChunks(text, 12, 1);
    if (chunks.length > 1) {
      assert.ok(
        chunks[1].startsWith("S3."),
        `second chunk should repeat the last sentence of chunk one: ${JSON.stringify(chunks)}`,
      );
    }
  });

  it("emits an oversize sentence alone instead of cutting mid-sentence", () => {
    const huge = `${"W".repeat(40)}. tiny.`;
    const chunks = sentenceChunks(huge, 15);
    assert.ok(
      chunks.some((c) => c.trim().startsWith(`${"W".repeat(40)}.`)),
      `the huge sentence must be emitted whole: ${JSON.stringify(chunks)}`,
    );
  });

  it("handles CJK terminals that need no trailing space", () => {
    const text = "第一文です。第二文です。第三文です。";
    const chunks = sentenceChunks(text, 12);
    assert.ok(chunks.length >= 2, JSON.stringify(chunks));
    impl.assertNoLoss(chunks, text, { kind: "sentence", size: 12 });
  });

  it("drops no sentence on a longer document", () => {
    const text =
      "Alpha beta gamma. Delta epsilon zeta! Eta theta? Iota kappa. Lambda mu nu omicron. Pi rho sigma tau.";
    const chunks = sentenceChunks(text, 30, 1);
    impl.assertNoLoss(chunks, text, { kind: "sentence", size: 30 });
  });
});

// ------------------------------------------------------------------ coverage

describe("assertNoLoss", () => {
  it("accepts correct fixed geometry", () => {
    const chunks = impl.fixedChunks("abcdefghij", 4, 2);
    impl.assertNoLoss(chunks, "abcdefghij", { kind: "fixed", size: 4, overlap: 2 });
  });

  it("names the uncovered range when the tail is dropped", () => {
    assert.throws(
      () => impl.assertNoLoss(["abcd"], "abcdefghij", { kind: "fixed", size: 4, overlap: 2 }),
      /uncovered range/,
    );
  });

  it("catches silent character loss in recursive splitting", () => {
    assert.throws(
      () => impl.assertNoLoss(["abc", "def"], "abcdefg", { kind: "recursive" }),
      /uncovered range|reconstruct/,
    );
  });
});
