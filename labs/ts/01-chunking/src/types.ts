// Shared contract for both implementations. Always compiled.

export const DEFAULT_SEPARATORS: readonly string[] = ["\n\n", "\n", ". ", " ", ""];

/** How assertNoLoss should verify coverage. */
export type Scheme =
  | { kind: "fixed"; size: number; overlap: number }
  | { kind: "recursive" }
  | { kind: "sentence"; size: number };

export interface Chunker {
  fixedChunks(text: string, size: number, overlap: number): string[];
  recursiveChunks(
    text: string,
    size: number,
    separators?: readonly string[],
    overlap?: number,
  ): string[];
  sentenceChunks(text: string, size: number, overlapSentences?: number): string[];
  assertNoLoss(chunks: string[], text: string, scheme: Scheme): void;
}
