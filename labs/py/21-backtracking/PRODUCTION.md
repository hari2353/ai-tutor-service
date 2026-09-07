# Production notes — backtracking

## Where backtracking ships

- **SAT solvers & constraint propagators** — DPLL is backtracking plus clause learning; the Sudoku solver you wrote is DPLL minus learning. CDCL solvers (what verifies chips and proofs) add *propagation* and *conflict analysis* to the same skeleton.
- **Crossword compilers & puzzle generators** — fill grids word-by-word with undo; the crossword industry literally runs your algorithm with a dictionary trie.
- **Scheduling & timetabling** — university course timetables, nurse rostering, tournament brackets: DFS over assignments with feasibility pruning; OR-tools CP-SAT adds propagation to make it scale.
- **Register allocation & instruction scheduling** — compilers graph-color via backtracking over interference graphs (with coalescing heuristics).
- **Regex engines** — bounded backtracking for NFA simulation; catastrophic backtracking (nested quantifiers) is why RE2/Go regexes use Thompson NFA automata instead.
- **Game AI / puzzle solvers** — KenKen, N-Queens visualizations, packing problems; constraint propagation beats raw search by orders of magnitude.

## Complexity table

| Problem | Search space | With pruning | Notes |
|---|---|---|---|
| subsets | 2ⁿ | 2ⁿ (exhaustive by design) | output is exponential |
| permutations | n! | n! | output is factorial |
| combinations | C(n,k) | C(n,k) | lexicographic via start index |
| N-Queens | n^n placements | ~O(n!) with 3 bitmask checks/board | n=12 in ms; n=16 in minutes |
| word search | 4^L paths | far less with early mismatch abort | board mutation trick for visited |
| generate parentheses | Catalan(n) | Catalan(n) | bounded by open/close counts |
| Sudoku | 9^81 naïve | ~10³-10⁴ nodes with sets/bitmasks | propagation (singles) drops it further |

## When backtracking is the wrong tool

- **Branching factor × depth explodes** (100-city TSP ≈ 100! states) — use DP, branch-and-bound with an LP bound, or heuristics (2-opt, simulated annealing).
- **You only need one answer and a greedy/DP exists** (shortest path → Dijkstra, not DFS).
- **The output itself is exponential** and the user asked for "all of it" — nothing can save you; negotiate a k-best or streaming contract.
- **Untrusted regex** — unbounded backtracking is a DoS vector (ReDoS); use a linear-time engine.

## The 3 questions an interviewer asks

1. *"What's the single biggest speedup for a backtracking solver?"* — propagation before branching (naked/hidden singles in Sudoku, unit clauses in SAT): it prunes entire subtrees the search would otherwise discover one contradiction at a time.
2. *"N-Queens complexity?"* — search space O(n!) with the row-by-row structure and O(1) diagonal checks; be honest that it is exponential and that n=20 needs bitmask + symmetry breaking.
3. *"When is the visited-set-in-place trick (mutating the board) wrong?"* — when the caller keeps a reference, or in concurrent contexts; also when cells must be revisited after a failure you forgot to restore — the un-choose step is the whole contract.
