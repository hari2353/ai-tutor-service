import { DEFAULT_SEPARATORS, type Chunker } from "./types.ts";

// STARTER — every function below compiles but does not work yet.
// The suite fails against this file; that is the point. Make it pass
// without touching types.ts or tests/.

export function fixedChunks(_text: string, _size: number, _overlap: number): string[] {
  throw new Error("TODO: hard character windows with stride size - overlap");
}

export function recursiveChunks(
  _text: string,
  _size: number,
  _separators: readonly string[] = DEFAULT_SEPARATORS,
  _overlap = 0,
): string[] {
  throw new Error("TODO: separator-ladder recursion with glue");
}

export function sentenceChunks(
  _text: string,
  _size: number,
  _overlapSentences = 1,
): string[] {
  throw new Error("TODO: sentence packing with sentence overlap");
}

export function assertNoLoss(_chunks: string[], _text: string, _scheme: never): void {
  throw new Error("TODO: the coverage property");
}

// Satisfies the Chunker shape once implemented.
export default {
  fixedChunks,
  recursiveChunks,
  sentenceChunks,
  assertNoLoss,
} as unknown as Chunker;
