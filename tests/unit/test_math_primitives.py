"""Unit and property tests for CyGuide high-performance mathematical and algorithmic primitives.

Tests cover:
1. IPRadixTrie: O(W) bitwise Patricia Radix Trie for IPv4 & IPv6 prefix matching and SSRF/CIDR policy.
2. DisjointSet: O(alpha(N)) Disjoint-Set Union with path compression and union by rank.
3. MinHash: O(K) Locality-Sensitive Hashing for Jaccard similarity estimation over token/shingle streams.
4. knapsack_01: O(N * W) 0/1 Knapsack dynamic programming solver for token budget optimization.
5. dfa_strip_ansi: ECMA-48 table-driven DFA ANSI stream stripper with zero regex backtracking.
6. BloomFilter: Fast O(K) probabilistic membership test with zero false negatives.
"""

import math
import re

import pytest

pytestmark = pytest.mark.fast

from cyguide.common import dfa_strip_ansi
from cyguide.common.algorithms import (
    BloomFilter,
    DisjointSet,
    IPRadixTrie,
    MinHash,
    knapsack_01,
)

# ============================================================================
# 1. IPRadixTrie (Bitwise Patricia Radix Trie)
# ============================================================================


def test_ip_radix_trie_ipv4_longest_prefix_match():
    """Verify O(W) longest prefix match correctly prioritizes more specific CIDRs."""
    trie = IPRadixTrie()

    trie.insert("10.0.0.0/8", "corp-network")
    trie.insert("10.1.0.0/16", "engineering-subnet")
    trie.insert("10.1.5.0/24", "lab-machines")
    trie.insert("10.1.5.42/32", "target-server")

    # Exact host match
    assert trie.match_longest("10.1.5.42") == "target-server"
    # Lab machines match (/24)
    assert trie.match_longest("10.1.5.100") == "lab-machines"
    # Engineering match (/16)
    assert trie.match_longest("10.1.200.1") == "engineering-subnet"
    # Corp network match (/8)
    assert trie.match_longest("10.254.1.1") == "corp-network"
    # Outside network
    assert trie.match_longest("192.168.1.1") is None
    assert "192.168.1.1" not in trie


def test_ip_radix_trie_ipv6_longest_prefix_match():
    """Verify 128-bit IPv6 bitwise prefix matching and traversal."""
    trie = IPRadixTrie()

    trie.insert("2001:db8::/32", "doc-prefix")
    trie.insert("2001:db8:abcd::/48", "sub-site")
    trie.insert("fd00:ec2::254/128", "imds-v6")

    assert trie.match_longest("2001:db8::1") == "doc-prefix"
    assert trie.match_longest("2001:db8:abcd:1234::1") == "sub-site"
    assert trie.match_longest("fd00:ec2::254") == "imds-v6"
    assert trie.match_longest("2001:4860:4860::8888") is None


def test_ip_radix_trie_membership_and_invalid_inputs():
    """Verify membership operator (__contains__) and invalid IP handling."""
    trie = IPRadixTrie()
    trie.insert("169.254.0.0/16", "link-local")

    assert "169.254.169.254" in trie
    assert "169.254.0.1" in trie
    assert "192.168.1.1" not in trie

    # Invalid string does not raise unhandled exception and returns None
    assert trie.match_longest("invalid-ip-string") is None
    assert "invalid-ip-string" not in trie


# ============================================================================
# 2. DisjointSet (Union-Find with Path Compression and Rank)
# ============================================================================


def test_disjoint_set_union_and_find():
    """Verify DisjointSet performs union, path compression, and partition grouping."""
    dsu = DisjointSet()

    # Initial state: elements are their own parents
    assert dsu.find("A") == "A"
    assert not dsu.connected("A", "B")

    dsu.union("A", "B")
    dsu.union("B", "C")
    dsu.union("D", "E")

    assert dsu.connected("A", "C")
    assert dsu.connected("B", "C")
    assert not dsu.connected("A", "D")

    # Union two distinct components
    dsu.union("C", "D")
    assert dsu.connected("A", "E")

    # Verify partition components
    components = dsu.get_components()
    assert len(components) == 1
    root = dsu.find("A")
    assert set(components[root]) == {"A", "B", "C", "D", "E"}


def test_disjoint_set_large_chain_path_compression():
    """Verify path compression flattens a long linear chain to O(1) amortized depth."""
    dsu = DisjointSet()
    n = 1000

    for i in range(n - 1):
        dsu.union(f"node_{i}", f"node_{i + 1}")

    # All nodes must be in the same component
    assert dsu.connected("node_0", f"node_{n - 1}")

    canonical_root = dsu.find("node_0")
    for i in range(n):
        assert dsu.find(f"node_{i}") == canonical_root


# ============================================================================
# 3. MinHash (Locality-Sensitive Hashing for Jaccard Similarity)
# ============================================================================


def test_minhash_jaccard_similarity_identical_and_disjoint():
    """Verify MinHash computes ~1.0 for identical token sets and ~0.0 for disjoint sets."""
    mh_a = MinHash(num_perm=128, seed=42)
    mh_b = MinHash(num_perm=128, seed=42)
    mh_c = MinHash(num_perm=128, seed=42)

    tokens_1 = ["apache", "httpd", "2.4.49", "path", "traversal", "cve-2021-41773"]
    tokens_2 = ["apache", "httpd", "2.4.49", "path", "traversal", "cve-2021-41773"]
    tokens_3 = ["proftpd", "1.3.5", "mod_copy", "command", "execution"]

    mh_a.update(tokens_1)
    mh_b.update(tokens_2)
    mh_c.update(tokens_3)

    # Identical sets -> exactly 1.0 similarity
    assert mh_a.jaccard_similarity(mh_b) == 1.0

    # Disjoint sets -> 0.0 similarity
    assert mh_a.jaccard_similarity(mh_c) == 0.0


def test_minhash_jaccard_overlap_accuracy():
    """Verify MinHash Jaccard estimation error stays within statistical bounds."""
    num_perm = 256
    mh_1 = MinHash(num_perm=num_perm, seed=1337)
    mh_2 = MinHash(num_perm=num_perm, seed=1337)

    # Construct sets with known Jaccard index:
    # Set 1: items 0..99 (100 items)
    # Set 2: items 50..149 (100 items)
    # Intersection: 50 items (50..99)
    # Union: 150 items (0..149)
    # True Jaccard = 50 / 150 = 1/3 ≈ 0.3333
    set1 = [f"token_{i}" for i in range(100)]
    set2 = [f"token_{i}" for i in range(50, 150)]

    mh_1.update(set1)
    mh_2.update(set2)

    estimated_jaccard = mh_1.jaccard_similarity(mh_2)
    true_jaccard = 50.0 / 150.0

    # Standard error of MinHash is 1 / sqrt(num_perm) = 1 / 16 = 0.0625
    margin = 3.0 / math.sqrt(num_perm)  # 3 standard deviations
    assert abs(estimated_jaccard - true_jaccard) < margin


# ============================================================================
# 4. knapsack_01 (0/1 Dynamic Programming Solver)
# ============================================================================


def test_knapsack_01_optimal_selection():
    """Verify 0/1 knapsack dynamic programming selects items yielding maximal value."""
    # (weight, value, name)
    items = [
        (2, 40, "Finding A"),
        (3, 50, "Finding B"),
        (1, 20, "Finding C"),
        (4, 70, "Finding D"),
    ]
    budget = 5

    # Optimal for budget 5:
    # B (3, 50) + A (2, 40) -> weight 5, value 90
    # D (4, 70) + C (1, 20) -> weight 5, value 90
    selected = knapsack_01(
        items,
        max_weight=budget,
        weight_fn=lambda x: x[0],
        value_fn=lambda x: x[1],
    )
    total_val = sum(item[1] for item in selected)
    total_weight = sum(item[0] for item in selected)
    assert total_val == 90
    assert total_weight <= budget


def test_knapsack_01_edge_cases():
    """Verify knapsack boundary conditions: zero budget, empty items, items exceeding capacity."""
    # Zero budget
    sel = knapsack_01(
        [(5, 100, "X")], max_weight=0, weight_fn=lambda x: x[0], value_fn=lambda x: x[1]
    )
    assert sel == []

    # Empty items
    sel = knapsack_01([], max_weight=100, weight_fn=lambda x: x[0], value_fn=lambda x: x[1])
    assert sel == []

    # All items exceed budget
    sel = knapsack_01(
        [(15, 100, "Heavy")], max_weight=10, weight_fn=lambda x: x[0], value_fn=lambda x: x[1]
    )
    assert sel == []


# ============================================================================
# 5. dfa_strip_ansi (ECMA-48 Table-Driven ANSI Stripper)
# ============================================================================


def test_dfa_strip_ansi_parity_with_regex():
    """Verify table-driven DFA ANSI parser matches standard regex on rich ANSI codes."""
    regex_ansi = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    sample_stream = (
        "\x1b[31;1m[!] CRITICAL VULNERABILITY DETECTED\x1b[0m\n"
        "\x1b[32m[+] Port 80/tcp open (http)\x1b[0m\r\n"
        "\x1b[38;2;255;128;0mOrange TrueColor Text\x1b[0m\n"
        "\x1b[2J\x1b[H\x1b[?25lCursor Hidden\x1b[?25h"
    )

    dfa_result = dfa_strip_ansi(sample_stream)
    regex_result = regex_ansi.sub("", sample_stream)

    assert dfa_result == regex_result
    assert "[!] CRITICAL VULNERABILITY DETECTED" in dfa_result
    assert "Cursor Hidden" in dfa_result
    assert "\x1b" not in dfa_result


def test_dfa_strip_ansi_clean_string_fast_path():
    """Verify plain string with no escape codes returns unchanged without modification."""
    plain = "Standard scan log with no ANSI codes 192.168.1.1 port 443"
    assert dfa_strip_ansi(plain) == plain


# ============================================================================
# 6. BloomFilter (Probabilistic Membership with Zero False Negatives)
# ============================================================================


def test_bloom_filter_zero_false_negatives():
    """Verify BloomFilter has 0% false negatives across 1,000 inserted keys."""
    bloom = BloomFilter(capacity=2000, error_rate=0.01)
    keys = [f"node_sha256_{i:06d}" for i in range(1000)]

    for k in keys:
        bloom.add(k)

    # Invariant: Every inserted key MUST test positive (zero false negatives)
    for k in keys:
        assert k in bloom


def test_bloom_filter_false_positive_bound():
    """Verify BloomFilter false positive rate stays well within statistical bound."""
    capacity = 10000
    bloom = BloomFilter(capacity=capacity, error_rate=0.01)

    for i in range(5000):
        bloom.add(f"inserted_{i}")

    # Test 5,000 uninserted keys
    false_positives = 0
    test_count = 5000
    for i in range(test_count):
        if f"unseen_{i}" in bloom:
            false_positives += 1

    observed_fp_rate = false_positives / test_count
    # Should be close to target 0.01 (allowing 3x headroom for random variance)
    assert observed_fp_rate < 0.03
