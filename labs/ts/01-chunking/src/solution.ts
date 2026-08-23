import { DEFAULT_SEPARATORS, type Chunker, type Scheme } from "./types.ts";

// SOLUTION — the reference. Read it AFTER your own version passes.

// ---------------------------------------------------------------- fixed

export function fixedChunks(text: string, size: number, overlap: number): string[] {
  if (!Number.isInteger(size) || size < 1) {
    throw new RangeError("size must be an integer >= 1");
  }
  if (overlap < 0 || overlap >= size) {
    throw new RangeError("need 0 <= overlap < size (zero stride = infinite loop)");
  }
  if (!text) return [];
  const stride = size - overlap;
  const out: string[] = [];
  for (let start = 0; start < text.length; start += stride) {
    const chunk = text.slice(start, start + size); // last window truncates
    if (out.length && chunk === out[out.length - 1]) break; // never a redundant duplicate
    out.push(chunk);
    if (start + size >= text.length) break; // this window already reached the end
  }
  return out;
}

// ---------------------------------------------------------------- recursive

/** Split on `sep`, keeping each separator glued to the piece it follows. */
function splitWithGlue(text: string, sep: string): string[] {
  if (sep === "") return [...text]; // character fallback
  const parts: string[] = [];
  let pos = 0;
  for (;;) {
    const idx = text.indexOf(sep, pos);
    if (idx === -1) break;
    parts.push(text.slice(pos, idx + sep.length));
    pos = idx + sep.length;
  }
  if (pos < text.length) parts.push(text.slice(pos));
  return parts;
}

function recurse(
  text: string,
  size: number,
  seps: readonly string[],
  overlap: number,
): string[] {
  if (text.length <= size) return text ? [text] : [];
  if (seps.length === 0) seps = [""]; // never fail to split — degrade to chars
  const [sep, ...rest] = seps;

  const pieces = splitWithGlue(text, sep);
  if (sep !== "" && pieces.length <= 1) {
    return recurse(text, size, rest, overlap); // separator useless here — finer one
  }

  // Greedy pack consecutive pieces into chunks <= size. Concatenation of all
  // emitted pieces (overlap=0) is byte-identical to the input by construction.
  const out: string[] = [];
  let cur = "";
  const flush = () => {
    if (cur) out.push(cur);
    cur = "";
  };
  for (const p of pieces) {
    if (p.length > size) {
      flush();
      out.push(...recurse(p, size, rest, overlap));
      continue;
    }
    if (cur.length + p.length > size) {
      flush();
      cur = p;
    } else {
      cur += p;
    }
  }
  flush();

  // Overlap: prefix later chunks with up to `overlap` chars of context,
  // capped so no chunk ever exceeds `size`.
  if (overlap > 0) {
    return out.map((c, i) => {
      if (i === 0) return c;
      const prev = out[i - 1];
      const room = Math.max(0, size - c.length);
      const take = Math.min(overlap, room, prev.length);
      return prev.slice(prev.length - take) + c;
    });
  }
  return out;
}

export function recursiveChunks(
  text: string,
  size: number,
  separators: readonly string[] = DEFAULT_SEPARATORS,
  overlap = 0,
): string[] {
  if (!Number.isInteger(size) || size < 1) {
    throw new RangeError("size must be an integer >= 1");
  }
  if (overlap < 0) throw new RangeError("overlap must be >= 0");
  return recurse(text, size, separators, overlap);
}

// ---------------------------------------------------------------- sentences

const ASCII_TERMINALS = new Set([".", "!", "?", "…"]);
const CJK_TERMINALS = new Set(["。", "！", "？"]); // no trailing space needed

export function splitSentences(text: string): string[] {
  const out: string[] = [];
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ASCII_TERMINALS.has(ch)) {
      let j = i + 1;
      while (j < text.length && /\s/.test(text[j])) j++; // glue trailing space
      out.push(text.slice(start, j));
      start = j;
      i = j - 1;
    } else if (CJK_TERMINALS.has(ch)) {
      out.push(text.slice(start, i + 1));
      start = i + 1;
    }
  }
  if (start < text.length) out.push(text.slice(start));
  return out.filter((s) => s.length > 0);
}

export function sentenceChunks(
  text: string,
  size: number,
  overlapSentences = 1,
): string[] {
  if (!Number.isInteger(size) || size < 1) {
    throw new RangeError("size must be an integer >= 1");
  }
  const sents = splitSentences(text);
  if (!sents.length) return [];

  const out: string[] = [];
  let cur: string[] = [];

  const flush = () => {
    if (cur.length) out.push(cur.join(""));
    cur = [];
  };

  for (const s of sents) {
    if (s.length > size) {
      // An honest boundary beats a dishonest cut.
      flush();
      out.push(s);
      continue;
    }
    const candidate = [...cur, s].join("");
    if (candidate.length > size) {
      // Capture the overlap seed BEFORE flush clears the chunk.
      const seed = cur.slice(-Math.max(0, overlapSentences));
      flush();
      cur = seed;
      if ([...cur, s].join("").length > size) cur = [];
    }
    cur.push(s);
  }
  flush();
  return out;
}

// ---------------------------------------------------------------- coverage

export function assertNoLoss(chunks: string[], text: string, scheme: Scheme): void {
  if (scheme.kind === "recursive") {
    const joined = chunks.join("");
    for (let i = 0; i < Math.min(joined.length, text.length); i++) {
      if (joined[i] !== text[i]) {
        throw new Error(`uncovered range at index ${i}: recursive chunks diverge from source`);
      }
    }
    if (joined.length !== text.length) {
      throw new Error(
        `uncovered range [${Math.min(joined.length, text.length)}, ${text.length}): ` +
          "chunks do not reconstruct the source exactly",
      );
    }
    return;
  }

  if (scheme.kind === "fixed") {
    const { size, overlap } = scheme;
    const stride = size - overlap;
    for (let i = 0; i < chunks.length; i++) {
      const at = i * stride; // head must be 0, steps follow the geometry
      if (!text.startsWith(chunks[i], at)) {
        throw new Error(`uncovered range starting at ${at}: chunk ${i} is not where geometry says`);
      }
    }
    const last = chunks.length - 1;
    const coveredEnd = last < 0 ? 0 : last * stride + chunks[last].length;
    if (coveredEnd !== text.length) {
      throw new Error(`uncovered range [${coveredEnd}, ${text.length}): the tail is missing`);
    }
    return;
  }

  // sentence scheme: every sentence of the source must appear in some chunk
  for (const s of splitSentences(text)) {
    if (!chunks.some((c) => c.includes(s))) {
      throw new Error(`uncovered range: sentence ${JSON.stringify(s.slice(0, 30))}… dropped by the packer`);
    }
  }
}

export default {
  fixedChunks,
  recursiveChunks,
  sentenceChunks,
  assertNoLoss,
} satisfies Chunker;
