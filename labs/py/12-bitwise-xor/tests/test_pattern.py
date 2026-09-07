"""Lab 12 tests — XOR patterns. Pure, deterministic, no sleeps."""
import random
import time

import pytest


# ------------------------------------------------------------------ single_number
def test_single_number_basic(P):
    assert P.single_number([4, 1, 2, 1, 2]) == 4


def test_single_number_all_duplicates_and_one(P):
    nums = []
    for i in range(100):
        nums.extend([i, i])
    nums.append(12345)
    random.Random(7).shuffle(nums)
    assert P.single_number(nums) == 12345


def test_single_number_single_element(P):
    assert P.single_number([9]) == 9


def test_single_number_empty_is_identity(P):
    assert P.single_number([]) == 0


def test_single_number_is_o1_space_no_sorting_side_effect(P):
    """Purity: identical input, identical output — and the input is untouched."""
    nums = [5, 3, 5, 8, 8]
    assert P.single_number(nums) == 3
    assert nums == [5, 3, 5, 8, 8]


# ------------------------------------------------------------------ single_number_iii
def test_single_number_iii_basic(P):
    assert P.single_number_iii([1, 2, 1, 3, 2, 5]) == (3, 5)


def test_single_number_iii_sorted_tuple(P):
    assert P.single_number_iii([2, 2, 0, 1]) == (0, 1)


def test_single_number_iii_many_pairs(P):
    nums = [10, 10, 7, 7, 99, 2, 2, 0, 0, 4]      # uniques: 4, 99
    assert P.single_number_iii(nums) == (4, 99)


def test_single_number_iii_smallest_inputs(P):
    assert P.single_number_iii([3, 8]) == (3, 8)


# ------------------------------------------------------------------ missing_number
def test_missing_number_basic(P):
    assert P.missing_number([3, 0, 1]) == 2


def test_missing_number_edges(P):
    assert P.missing_number([]) == 0          # permutation of {0}, hole is 0
    assert P.missing_number([0]) == 1         # permutation of {0,1}, hole is 1
    assert P.missing_number([1]) == 0


def test_missing_number_last_index(P):
    n = 50
    nums = list(range(n))                     # complete 0..n-1, so hole is n
    assert P.missing_number(nums) == n


def test_missing_number_matches_brute_force(P):
    rng = random.Random(11)
    for _ in range(25):
        n = rng.randrange(0, 12)
        full = list(range(n + 1))
        hole = rng.randrange(len(full))
        nums = full[:hole] + full[hole + 1:]
        rng.shuffle(nums)
        assert P.missing_number(nums) == hole


# ------------------------------------------------------------------ xor linked list
def test_xor_list_roundtrip(P):
    head, mem = P.build_xor_list([10, 20, 30, 40])
    assert P.xor_list_to_list(head, mem) == [10, 20, 30, 40]


def test_xor_list_empty(P):
    head, mem = P.build_xor_list([])
    assert head == 0
    assert mem == {}
    assert P.xor_list_to_list(head, mem) == []


def test_xor_list_single_element(P):
    head, mem = P.build_xor_list([7])
    assert head == 1
    assert mem[1] == (7, 0)                  # both = 0 ^ 0 = NULL both sides
    assert P.xor_list_to_list(head, mem) == [7]
    assert P.xor_get_nth(head, mem, 0) == 7


def test_xor_list_both_field_is_prev_xor_next(P):
    head, mem = P.build_xor_list([1, 2, 3])
    assert head == 1
    assert mem[1] == (1, 0 ^ 2)
    assert mem[2] == (2, 1 ^ 3)
    assert mem[3] == (3, 2 ^ 0)


def test_xor_get_nth(P):
    head, mem = P.build_xor_list([5, 6, 7, 8, 9])
    assert P.xor_get_nth(head, mem, 0) == 5
    assert P.xor_get_nth(head, mem, 2) == 7
    assert P.xor_get_nth(head, mem, 4) == 9


def test_xor_list_many_values(P):
    vals = list(range(1, 101))
    head, mem = P.build_xor_list(vals)
    assert P.xor_list_to_list(head, mem) == vals
    assert P.xor_get_nth(head, mem, 99) == 100


# ------------------------------------------------------------------ bits
def test_count_bits(P):
    assert P.count_bits(0) == 0
    assert P.count_bits(1) == 1
    assert P.count_bits(7) == 3
    assert P.count_bits(255) == 8
    assert P.count_bits(256) == 1
    assert P.count_bits((1 << 20) - 1) == 20


def test_parity(P):
    assert P.parity(0) == 0
    assert P.parity(1) == 1
    assert P.parity(3) == 0
    assert P.parity(7) == 1
    assert P.parity(0b1011) == 1
    assert P.parity(0b1111) == 0


def test_count_bits_agrees_with_bin(P):
    for n in range(0, 512):
        assert P.count_bits(n) == bin(n).count("1")


# ------------------------------------------------------------------ complexity witness
def _brute_single(nums):
    """O(n^2) reference: linear scan with .count()."""
    for v in nums:
        if nums.count(v) == 1:
            return v
    return 0


def test_single_number_linear_vs_brute_force_quadratic(P):
    """The XOR scan is O(n); the count-scan is O(n^2). At 10x the data the
    linear scan must still be faster than the quadratic one."""
    rng = random.Random(3)
    base = list(range(4000)) * 2
    rng.shuffle(base)

    small = base[:8000]
    small.append(424242)                      # n = 8001
    big = base + [515151]                      # ~x80 data for the witness below

    t0 = time.perf_counter()
    assert _brute_single(small) == 424242
    t_brute = time.perf_counter() - t0

    t0 = time.perf_counter()
    assert P.single_number(big) == 515151
    t_fast = time.perf_counter() - t0

    assert t_fast < t_brute, (
        f"O(n) scan took {t_fast:.3f}s on {len(big)} items but the O(n^2) "
        f"reference took only {t_brute:.3f}s on {len(small)}"
    )


def test_single_number_huge_input_under_2s(P):
    n = 200_000
    nums = list(range(n))
    nums += nums                              # every value twice
    nums.append(987654321)
    t0 = time.perf_counter()
    assert P.single_number(nums) == 987654321
    assert time.perf_counter() - t0 < 2.0
