# In-Place Linked List Reversal

> **Track:** T02 DSA: 21 Patterns · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-07-27
> **Module id:** `T02-p06-ll-reversal` · **Tags:** pattern, linked-list, pointers

## The 30-second version

In-Place Linked List Reversal rewires a singly linked list's `next` pointers one node at a time using three tracking references — `prev`, `curr`, and a saved `next_temp` — so that no node is ever lost even though you're mutating the exact pointers you're currently walking. The invariant: before you overwrite `curr.next`, you must have already saved the node it points to, because that overwrite is what severs your only path forward. This gives O(n) time and O(1) extra space, versus a recursive formulation that's equally O(n) time but costs O(n) stack space — a real distinction when the list can be long enough to blow the call stack. Recognize it from "reverse a linked list" in any form: whole list, a sub-range between two positions, groups of k nodes, or pairs — and from any problem that internally needs a reversed sub-list as a building block (palindrome check, reorder list, add-two-numbers variants). The entire pattern is: never lose the "rest of the list" reference before you finish repointing the node you're currently on.

## Why this gets asked

The interviewer is testing disciplined pointer manipulation under a self-inflicted constraint: you're allowed no extra data structure (no stack, no array copy) even though the natural instinct — collect values, reverse the collection, rebuild the list — trivially works at O(n) space. That constraint mirrors real systems work: any hand-rolled pointer-based structure (an LRU cache's doubly linked list, a custom skip list, an intrusive linked list in a kernel or embedded context) requires exactly this kind of "rewire without losing your place" discipline, and getting it wrong there means corrupted or leaked memory, not just a failed test case. Reverse Nodes in k-Group (LC25) is the sharper follow-up that actually separates levels, because it forces you to compose the base reversal as a subroutine, correctly reconnect a reversed group's new tail to the next group's new head, and handle the boundary case of a final partial group — which is precisely where memorized-but-not-understood implementations fall apart.

---

## Lineage: past → present → future

**What came before.** The naive approach to reversing a linked list is to walk it once, push every value onto a stack (or into an array), then walk it again popping values back into place, or to build an entirely new list from those popped values — both O(n) time but O(n) extra space, and both throw away the fact that a linked list can be reversed by rewiring pointers alone with no auxiliary storage. Recursive reversal (`reverse(head.next)` first, then fix up `head.next.next = head; head.next = null`) is taught early in most CS curricula because it's easy to state correctly, but it costs O(n) stack space — one frame per node — which is the same expressiveness with the exact same asymptotic space problem as the naive approach, just hidden in the call stack instead of an explicit data structure.

**Where it stands now.** The iterative three-pointer technique (`prev`, `curr`, `next_temp`) is the unambiguous industry-standard answer whenever O(1) space is required or implied, which is nearly always the case once a candidate reaches senior-level interviews; there's no live disagreement about which technique is correct. What separates fluency levels is composability: reversing a bounded sub-range (LC92) requires correctly anchoring the node *before* the range so the reversed segment reconnects properly, and reversing in k-sized groups (LC25) requires reversing subroutine-style, tracking each group's boundaries, and explicitly deciding what to do with a trailing partial group — LC25's official spec says leave it unreversed, but the "reverse it anyway" variant is a legitimate follow-up interviewers sometimes ask to see if you can adapt cleanly.

**Where it's heading.** This is a closed, decades-old technique with essentially no room to evolve algorithmically; what continues to shift is which compositions get asked as the "harder sibling" question. Expect continued emphasis on k-group reversal and its variants (reverse only even-length groups, reverse alternating groups) precisely because they require you to track multiple pointers across subroutine boundaries without a stack trace to lean on, which remains an efficient way to test implementation rigor even as interview formats shift toward more debugging-style prompts (e.g., "here's a reversal with the `next_temp` save removed — what breaks, and on which input?").

---

## Mental model

```
Reversing 1 -> 2 -> 3 -> None

prev=None  curr=1->2->3->None

step 1: next_temp = curr.next (= node 2)   -- SAVE before you cut the rope
        curr.next = prev (1.next = None)   -- rewire
        prev = curr (prev = 1)
        curr = next_temp (curr = 2)
        state: None <- 1    2 -> 3 -> None

step 2: next_temp = curr.next (= node 3)
        curr.next = prev (2.next = 1)
        prev = curr (prev = 2)
        curr = next_temp (curr = 3)
        state: None <- 1 <- 2    3 -> None

step 3: next_temp = curr.next (= None)
        curr.next = prev (3.next = 2)
        prev = curr (prev = 3)
        curr = next_temp (curr = None)
        state: None <- 1 <- 2 <- 3     (curr is None, loop ends)

return prev (= node 3, the new head)
```

The one rule that generates the whole algorithm: **save `curr.next` into `next_temp` before you overwrite `curr.next`**, because the overwrite is the only step that destroys your path to the rest of the original list. Every bug in this pattern traces back to violating that ordering.

---

## Recognition heuristics

- **"Reverse a linked list"** in any framing — whole list, a range between two 1-indexed positions, groups of a fixed size `k`, or adjacent pairs — is this pattern by name.
- **"In O(1) extra space"** stated or implied for a linked-list problem — rules out the stack/array trick and points straight at the three-pointer rewire.
- **A sub-list needs to be reversed as an intermediate step inside a larger problem** — Palindrome Linked List (find middle via fast/slow, reverse the second half, compare), Reorder List (find middle, reverse second half, merge by interleaving), Add Two Numbers where digits are stored most-significant-first (reverse both lists first so addition can proceed digit-by-digit from the least-significant end).
- **"Reverse in groups of k" / "swap adjacent pairs" / "reverse every other group"** — all variants of segmenting the list into fixed-size chunks, reversing each chunk with the base technique, then correctly reconnecting each chunk's new tail to the next chunk's new head (or leaving an under-sized trailing chunk untouched, per the specific problem's rule).
- **You need a pointer to the node *before* the segment you're reversing**, so the reversed segment can be spliced back in — this is why range-reversal and k-group reversal implementations almost always use a dummy/sentinel node preceding the head, avoiding special-casing "what if the range starts at the head."

**Anti-signal:** "rotate a linked list by k positions" (LC61) sounds like it might involve reversal but doesn't — it's solved by finding the new tail/head via `k mod length` and relinking three pointers (old tail to old head, forming a temporary cycle, then breaking it at the new boundary), with no `next`-pointer reversal anywhere in the solution.

---

## Template code (Python, Java, Go)

Base reversal (whole list) plus the position-bounded variant (LC92-style), the two skeletons the rest of the family builds on:

**Python**
```python
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def reverse_list(head: ListNode | None) -> ListNode | None:
    """Reverse an entire singly linked list. O(n) time, O(1) space."""
    prev = None
    curr = head
    while curr:
        next_temp = curr.next   # save before overwriting
        curr.next = prev
        prev = curr
        curr = next_temp
    return prev   # new head

def reverse_between(head: ListNode | None, left: int, right: int) -> ListNode | None:
    """Reverse the sublist from 1-indexed position left to right, in place."""
    dummy = ListNode(0, head)
    prev_of_range = dummy
    for _ in range(left - 1):
        prev_of_range = prev_of_range.next   # walk to the node just before the range

    curr = prev_of_range.next
    prev = None
    for _ in range(right - left + 1):
        next_temp = curr.next
        curr.next = prev
        prev = curr
        curr = next_temp

    # prev is now the new head of the reversed segment; curr is the node after it
    prev_of_range.next.next = curr          # old range-head (now range-tail) connects past the segment
    prev_of_range.next = prev               # node before the range connects to the new segment head
    return dummy.next
```

**Java**
```java
public ListNode reverseList(ListNode head) {
    ListNode prev = null, curr = head;
    while (curr != null) {
        ListNode nextTemp = curr.next;
        curr.next = prev;
        prev = curr;
        curr = nextTemp;
    }
    return prev;
}

public ListNode reverseBetween(ListNode head, int left, int right) {
    ListNode dummy = new ListNode(0, head);
    ListNode prevOfRange = dummy;
    for (int i = 0; i < left - 1; i++) prevOfRange = prevOfRange.next;

    ListNode curr = prevOfRange.next;
    ListNode prev = null;
    for (int i = 0; i < right - left + 1; i++) {
        ListNode nextTemp = curr.next;
        curr.next = prev;
        prev = curr;
        curr = nextTemp;
    }
    prevOfRange.next.next = curr;
    prevOfRange.next = prev;
    return dummy.next;
}
```

**Go**
```go
type ListNode struct {
	Val  int
	Next *ListNode
}

func reverseList(head *ListNode) *ListNode {
	var prev *ListNode
	curr := head
	for curr != nil {
		nextTemp := curr.Next
		curr.Next = prev
		prev = curr
		curr = nextTemp
	}
	return prev
}

func reverseBetween(head *ListNode, left int, right int) *ListNode {
	dummy := &ListNode{Next: head}
	prevOfRange := dummy
	for i := 0; i < left-1; i++ {
		prevOfRange = prevOfRange.Next
	}

	curr := prevOfRange.Next
	var prev *ListNode
	for i := 0; i < right-left+1; i++ {
		nextTemp := curr.Next
		curr.Next = prev
		prev = curr
		curr = nextTemp
	}
	prevOfRange.Next.Next = curr
	prevOfRange.Next = prev
	return dummy.Next
}
```

---

## Complexity, derived

Each node's `next` pointer is read exactly once (to save it into `next_temp`) and written exactly once (to point backward), and the loop advances `curr` exactly once per node with no revisits — so the whole-list reversal is **O(n) time**. Only three pointer-sized variables (`prev`, `curr`, `next_temp`) exist regardless of list length: **O(1) extra space**. For the range-bounded and k-group variants, the extra walk to reach the start of the range (`left - 1` steps) and the reversal itself (`right - left + 1` steps) are both linear in the affected range, so the total remains **O(n)** for a single pass over the list, still **O(1) space**. Contrast with the recursive formulation: it performs the identical O(n) pointer rewrites, but each recursive call adds one stack frame that isn't released until the entire unwind completes, so it costs **O(n) stack space** — for a list of 100,000 nodes, that's 100,000 stack frames, which exceeds Python's default recursion limit (1,000) outright and risks a native `StackOverflowError` in Java or Go for sufficiently long lists even though those runtimes tolerate deeper recursion before Python does.

---

## The 5 variants interviewers actually ask

1. **Reverse Linked List (LC206).** The base three-pointer walk over the whole list, exactly as in the template above.
2. **Reverse Linked List II (LC92) — reverse between positions `left` and `right`.** Modification: use a dummy node preceding the head, walk to the node just before position `left`, run the base reversal for exactly `right - left + 1` nodes, then splice: the original node at `left` (now the tail of the reversed segment) connects to whatever follows the range, and the node before the range connects to the new head of the reversed segment.
3. **Reverse Nodes in k-Group (LC25).** Modification: reverse the list in fixed-size chunks of `k`. For each chunk, first confirm at least `k` nodes remain (if fewer than `k` remain, per LC25's spec, leave that final partial group unreversed); reverse the chunk with the base technique, then connect the *previous* chunk's new tail to this chunk's new head, and continue from where this chunk's original head (now its tail) points next.
4. **Swap Nodes in Pairs (LC24).** The `k = 2` special case of group reversal, but usually implemented directly without the general k-group machinery: for each pair, rewire so the second node points to the first and the first points to whatever follows the pair, then advance past the pair.
5. **Reverse Nodes in Even Length Groups (LC2074).** Modification: group sizes increase by one each time (1, 2, 3, 4, ...), capped by remaining list length, and only groups with an *even* number of actual nodes get reversed — the last group may be short due to running out of nodes, and its evenness (not the originally intended group size) determines whether it's reversed.

---

## Common bugs

- **Overwriting `curr.next` before saving it.** This is the defining bug of the entire pattern — once `curr.next = prev` executes, the original next node is unreachable unless it was captured into `next_temp` beforehand. Every other bug in this pattern is a variation on getting this ordering wrong.
- **Losing the anchor node before a sub-range.** In range or group reversal, forgetting to keep a pointer to the node *immediately before* the segment being reversed means you have no way to splice the reversed segment back into the rest of the list — this is why a dummy/sentinel node predecessor is standard practice, not just convenience.
- **Forgetting to reconnect the old range-head (now the range-tail) to what comes after the range**, leaving the reversed segment's tail dangling with a stale `next` pointer (often still pointing at whatever it pointed to before reversal, silently truncating the rest of the list or creating an unintended cycle).
- **Reversing a trailing partial group in k-Group Reversal when the spec says not to** (LC25 requires leaving a final group of fewer than `k` nodes in its original order) — this requires counting ahead to confirm a full group exists *before* starting to reverse it, not reversing first and checking after.
- **Recursive implementation blowing the call stack on long lists.** Correct logic, wrong space profile — for lists in the tens of thousands of nodes or more, recursion depth becomes a real failure mode (Python raises `RecursionError` past its default limit of 1,000 frames), not just a theoretical concern.
- **Confusing this pattern with Rotate List (LC61).** Attempting to solve list rotation via reversal-based tricks (some array-rotation solutions do use triple-reversal) is unnecessary complexity for a linked list, where finding the new head/tail via `k mod length` and relinking three pointers directly is simpler and requires no reversal at all.

---

## Interview questions

### Q1 — Reverse Linked List (LC206)
**Testing:** the base three-pointer mechanism, done cleanly.
**Answer:** `prev`, `curr`, `next_temp` walk; save before overwrite. O(n) time, O(1) space.
**Follow-up trap:** *"Now do it recursively — what's the space complexity?"* — the code is arguably cleaner, but it's O(n) stack space, one frame per node, which is a real liability on very long lists; say this explicitly rather than presenting recursion as strictly better.

### Q2 — Reverse Linked List II (LC92)
**Testing:** correctly anchoring and splicing a bounded sub-range.
**Answer:** Dummy node, walk to the node before `left`, run the base reversal for `right - left + 1` nodes, then reconnect both ends of the reversed segment.
**Follow-up trap:** *"What if `left == 1`?"* — the node before the range would be the head itself, which doesn't exist; the dummy node sidesteps this special case entirely by guaranteeing there's always a "node before" to walk from, even when the range starts at the very first node.

### Q3 — Reverse Nodes in k-Group (LC25)
**Testing:** composing the base reversal as a repeated subroutine with correct group-to-group reconnection.
**Answer:** Count ahead to confirm a full group of `k` exists; if not, stop and leave the remainder unreversed; otherwise reverse the group, connect the previous group's tail to this group's new head, and continue.
**Follow-up trap:** *"Do it with O(1) extra space — no recursion, no array of node references."* — the iterative version must track the previous group's tail across iterations using a single pointer updated after each group, without ever materializing a list of node pointers; candidates who solve it by collecting nodes into an array to reverse them lose the O(1) space property the problem is testing for.

### Q4 — Swap Nodes in Pairs (LC24)
**Testing:** whether you can special-case k=2 directly instead of forcing the general k-group machinery.
**Answer:** For each pair, rewire the second node to point at the first, the first to point at whatever follows the pair, and advance the "previous tail" pointer to the first node (now the pair's tail).
**Follow-up trap:** *"Solve it recursively in one line of core logic — what's the recursive relation?"* — `head.next = swapPairs(head.next.next)`, then swap `head` and `head.next`, returning the new pair head; note this still costs O(n/2) stack depth, same space caveat as any recursive reversal.

### Q5 — Rotate List (LC61)
**Testing:** whether you correctly recognize this is *not* a reversal problem despite superficial similarity.
**Answer:** Compute length, `k %= length`, find the new tail at position `length - k - 1` and new head right after it, connect old tail to old head (forming a temporary cycle), then break the cycle at the new tail/head boundary.
**Follow-up trap:** *"Some array-rotation solutions use triple reversal — does that technique apply here?"* — it's unnecessary for a linked list; triple-reversal is a trick for in-place *array* rotation where you can't easily "jump" to an arbitrary position, but a linked list lets you directly relink three pointers once you know the new boundary, with no reversal involved at all.

### Q6 — Palindrome Linked List (LC234), reversal half
**Testing:** whether you handle the case where the list must remain unmodified after the check.
**Answer:** Find the middle (fast/slow), reverse the second half in place, compare values from both ends, then re-reverse the second half and re-attach it before returning, if the list must stay unmodified.
**Follow-up trap:** *"If a colleague's code returns the correct boolean but never restores the list, is that a bug?"* — yes, if the function's contract doesn't explicitly allow mutation; a "read-only-looking" check silently mutating the caller's data structure is a real production bug pattern, not a nitpick.

### Q7 — Reorder List (LC143)
**Testing:** composing three patterns — find middle, reverse a half, then merge by interleaving.
**Answer:** Find the middle, split the list into two halves (severing the first half's tail), reverse the second half, then merge the two halves by alternating nodes from each.
**Follow-up trap:** *"What breaks if you forget to sever the first half's tail before reversing the second half?"* — the first half's original tail still points into what's about to become the reversed second half, which after reversal either creates an unintended cycle or corrupts the reversal's boundary; the split must happen strictly before the reversal step.

### Q8 — Add Two Numbers II (LC445, digits stored most-significant-first)
**Testing:** recognizing reversal as an enabling preprocessing step for a problem that otherwise wants least-significant-first access.
**Answer:** Reverse both input lists (or use two stacks as an O(n)-space alternative), then add digit-by-digit from what is now the least-significant end, building the result and reversing it back (or building it via prepending) to restore most-significant-first order.
**Follow-up trap:** *"Can you do it without reversing the inputs, if you're not allowed to modify them?"* — yes, using two stacks to process digits from the end without touching the original lists' pointers, trading the O(1)-space property for O(n) space when input mutation is disallowed; state this tradeoff explicitly rather than assuming reversal is always available.

### Q9 — Reverse Nodes in Even Length Groups (LC2074)
**Testing:** adapting group reversal when group sizes are variable and the reversal decision depends on the *actual* remaining group size, not a fixed `k`.
**Answer:** Walk the list computing successive intended group sizes (1, 2, 3, ...), capping each at however many nodes actually remain; reverse a group only if its *actual* size (after capping) is even.
**Follow-up trap:** *"What if the very last group is short due to running out of nodes — does the original intended size or the actual size decide whether it gets reversed?"* — the actual (possibly capped) size decides; a group intended to be size 4 that only has 3 nodes remaining is evaluated as size 3 (odd) and left unreversed, which candidates who hardcode the intended sequence of sizes get wrong.

### Q10 — Reverse a Doubly Linked List
**Testing:** whether you understand this is structurally simpler than the singly linked case, not harder.
**Answer:** For every node, swap its `next` and `prev` references; at the end, swap the list's head and tail pointers. No `prev`/`curr`/`next_temp` walk is needed because each node already holds both directions.
**Follow-up trap:** *"Why doesn't this need the three-pointer technique the singly linked version needs?"* — the singly linked technique exists specifically to avoid losing the forward reference after overwriting it; a doubly linked node never loses anything because it retains its `prev` pointer as the "way back" even after its `next` gets rewritten, so a single pass just swapping both pointers per node suffices.

### Q11 — Detect and fix a linked list reversal that forgot to save `next` before overwriting
**Testing:** debugging skill — can you spot the exact defect from a description of symptoms, not just write correct code from scratch.
**Answer:** Symptom: the reversed result contains only the original head node (or a very short prefix), because `curr.next = prev` destroys the path forward before it's captured, so the loop's next iteration has nothing left to advance into (`curr` becomes `None`/`null` immediately, or worse, becomes `prev`'s old value, forming a two-node cycle in the buggy variant where the assignment order is fully reversed).
**Follow-up trap:** *"What's the fix, in one line?"* — insert `next_temp = curr.next` immediately before `curr.next = prev`; the fix is always about read-before-write ordering, never about the pointer *values* themselves being wrong.

---

## Red flags that fail you

- Overwriting `curr.next` before saving it to a temporary variable, losing the rest of the list.
- Forgetting the "node before the range" anchor in Reverse Linked List II or k-Group Reversal, making correct splicing impossible.
- Reversing a trailing partial group in k-Group Reversal when the spec requires leaving it untouched.
- Claiming a recursive reversal is "the same" as the iterative one without acknowledging the O(n) stack-space cost.
- Solving Rotate List by reaching for a reversal trick instead of the simpler cycle-and-break relinking.
- Not restoring a temporarily-reversed second half in Palindrome Linked List when the function's contract requires the list to remain unmodified.

---

## Cheat card

```
CORE RULE       save next_temp = curr.next BEFORE curr.next = prev -- the entire pattern in one line
BASE REVERSAL   prev=None, curr=head; loop: next_temp=curr.next; curr.next=prev; prev=curr; curr=next_temp
COMPLEXITY      O(n) time, O(1) space iterative; O(n) time, O(n) STACK space recursive
RANGE REVERSAL  dummy node -> walk to node BEFORE left -> reverse (right-left+1) nodes -> splice both ends
K-GROUP         confirm k nodes remain BEFORE reversing; connect prev group's tail to this group's new head
PARTIAL GROUP   LC25 spec: leave a final group of < k nodes UNREVERSED
SWAP PAIRS      k=2 special case; can also be done as one-line recursion (still O(n) stack)
NOT REVERSAL    Rotate List (LC61): relink 3 pointers via k mod length, no next-pointer flipping at all
DOUBLY LINKED   swap next/prev on every node, then swap head/tail -- no prev/curr walk needed
COMPOSES WITH   fast/slow (find middle) for Palindrome LL and Reorder List
RECURSION RISK  long lists (10k+ nodes) can exceed default recursion limits -- prefer iterative in production
```

## Sources
- [Reverse Linked List — LeetCode](https://leetcode.com/problems/reverse-linked-list/) — accessed 2026-07-27
- [Reverse Linked List II — LeetCode](https://leetcode.com/problems/reverse-linked-list-ii/) — accessed 2026-07-27
- [Reverse Nodes in k-Group — LeetCode](https://leetcode.com/problems/reverse-nodes-in-k-group/) — accessed 2026-07-27
- [Rotate List — LeetCode](https://leetcode.com/problems/rotate-list/) — accessed 2026-07-27
- [Reverse Nodes in Even Length Groups — LeetCode](https://leetcode.com/problems/reverse-nodes-in-even-length-groups/) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
