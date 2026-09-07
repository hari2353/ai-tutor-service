# Production notes — monotonic stacks

## Where monotonic stacks ship

- **Watermark / threshold alerting** — "alert when a metric exceeds its highest value in the last N days" is next-greater-element / sliding-window-maximum over a stream; the stack/deque keeps it O(1) amortized per tick instead of re-scanning the window.
- **Image processing scanlines** — largest-rectangle-in-histogram is *the* subroutine of row-sweep object recognition and OMR (optical mark recognition); maximal-rectangle over binary matrices segments text lines in document scanners.
- **Compilers & constraint solving** — dominance frontiers in SSA construction use nearest-greater queries on the dominator tree; interval scheduling and resource-feasibility checks in CP solvers (unary resource propagation) run monotonic-stack sweeps.
- **Computational finance** — stock span / rolling max for "N-week high" screens; drawdown calculators sweep a monotonic deque once.
- **Text editors & diff** — "next smaller element" variants appear in line-wrap optimization and histogram equalization of whitespace runs.

## Complexity table

| Problem | Monotonic stack | Brute force | Notes |
|---|---|---|---|
| next/prev greater element | O(n) | O(n²) | each index pushed & popped once |
| daily temperatures | O(n) | O(n²) | distance, not value |
| largest rectangle (histogram) | O(n) | O(n²) | sentinel flush empties the stack |
| maximal square (DP) | O(r·c) | O(r·c·min(r,c)) | `min(up,left,diag)+1` |
| maximal rectangle | O(r·c) | O(r²·c²) | per-row histogram compression |
| stock span | O(n) | O(n²) | stack holds (price, span) pairs |

## The 3 questions an interviewer asks

1. *"Why is it O(n) if there's a while inside the for?"* — amortization: each element enters the stack once and leaves at most once; total work ≤ 2n comparisons. The invariant, not the loop shape, is the proof.
2. *"Strictly greater vs greater-or-equal — does it matter?"* — yes, with duplicates it changes both correctness (double-count in rectangles) and stack behaviour; decide from the problem statement and say it out loud.
3. *"What breaks in streaming?"* — next-greater needs the *future*; only previous-greater variants stream naturally. Rolling max windows use a deque because the expiry side needs deletion — that's why stretch goal 1 is a different structure.
