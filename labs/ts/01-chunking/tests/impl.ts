// Picks the implementation under test.
//   default:             src/starter.ts   (must FAIL — that is the point)
//   CHUNK_IMPL=solution: src/solution.ts (must PASS)
import type { Chunker } from "../src/types.ts";

const which = process.env.CHUNK_IMPL === "solution" ? "solution" : "starter";
const mod = await import(`../src/${which}.ts`);

export const impl: Chunker = mod.default;
