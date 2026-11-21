"""High-performance mathematical and algorithmic primitives for CyGuide.

This unified deep module provides foundational data structures and discrete algorithms:
1. IPRadixTrie: O(W) binary Patricia Radix Trie for IPv4 & IPv6 longest-prefix matching.
2. BloomFilter: Space-efficient probabilistic set with zero false negatives for database query pre-filtering.
3. DisjointSet: Disjoint-Set Union (Union-Find) with path compression and rank optimization.
4. MinHash: Locality-Sensitive Hashing for O(K) Jaccard similarity estimation across token sets.
5. knapsack_01: Dynamic programming 0/1 Knapsack solver for optimal context budgeting under token constraints.
"""

import hashlib
import ipaddress
import math
import struct
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

T = TypeVar("T")


# ============================================================================
# 1. Binary Patricia Radix Trie for IP & CIDR Prefix Matching
# ============================================================================


class _TrieNode:
    __slots__ = ("children", "is_terminal", "data")

    def __init__(self) -> None:
        self.children: list[Optional[_TrieNode]] = [None, None]
        self.is_terminal: bool = False
        self.data: Any = None


class IPRadixTrie:
    """A bitwise binary radix trie supporting exact and longest-prefix IP and CIDR matching.

    Matches IPv4 (32-bit) and IPv6 (128-bit) addresses in strict O(W) bitwise steps
    where W <= 32 for IPv4 and W <= 128 for IPv6, eliminating O(N) list-scanning.
    """

    def __init__(self) -> None:
        self._root_v4 = _TrieNode()
        self._root_v6 = _TrieNode()
        self._count = 0

    def insert(
        self,
        network: Union[
            str,
            ipaddress.IPv4Network,
            ipaddress.IPv6Network,
            ipaddress.IPv4Address,
            ipaddress.IPv6Address,
        ],
        data: Any = True,
    ) -> None:
        """Insert an IP address, CIDR string, or network object into the trie."""
        if isinstance(network, str):
            net = ipaddress.ip_network(network.strip(), strict=False)
        elif isinstance(network, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            net = ipaddress.ip_network(f"{network}/{network.max_prefixlen}")
        else:
            net = network

        root = self._root_v4 if net.version == 4 else self._root_v6
        total_bits = 32 if net.version == 4 else 128
        net_int = int(net.network_address)
        prefix_len = net.prefixlen

        curr = root
        for i in range(prefix_len):
            bit = (net_int >> (total_bits - 1 - i)) & 1
            if curr.children[bit] is None:
                curr.children[bit] = _TrieNode()
            curr = curr.children[bit]

        curr.is_terminal = True
        curr.data = data
        self._count += 1

    def contains(
        self, ip: Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address, int], version: int = 4
    ) -> bool:
        """Check if an IP address falls within any inserted CIDR prefix."""
        return self.match_longest(ip, version=version) is not None

    def match_longest(
        self, ip: Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address, int], version: int = 4
    ) -> Optional[Any]:
        """Find the longest matching prefix for the given IP address, returning associated data."""
        if isinstance(ip, str):
            try:
                ip_obj = ipaddress.ip_address(ip.strip())
                version = ip_obj.version
                ip_int = int(ip_obj)
            except ValueError:
                return None
        elif isinstance(ip, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            version = ip.version
            ip_int = int(ip)
        else:
            ip_int = int(ip)

        root = self._root_v4 if version == 4 else self._root_v6
        total_bits = 32 if version == 4 else 128

        curr = root
        longest_match = curr.data if curr.is_terminal else None

        for i in range(total_bits):
            bit = (ip_int >> (total_bits - 1 - i)) & 1
            curr = curr.children[bit]
            if curr is None:
                break
            if curr.is_terminal:
                longest_match = curr.data

        return longest_match

    def __contains__(self, ip: Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
        return self.contains(ip)

    def __len__(self) -> int:
        return self._count


# ============================================================================
# 2. Optimal In-Memory Bloom Filter for Query Pre-Filtering
# ============================================================================


class BloomFilter:
    """A space-efficient probabilistic set with zero false negatives.

    Uses optimal bit array size m = - (n * ln(p)) / (ln(2)^2) and
    optimal number of hash functions k = (m / n) * ln(2).
    """

    def __init__(self, capacity: int = 10000, error_rate: float = 0.01) -> None:
        self.capacity = max(100, capacity)
        self.error_rate = min(0.5, max(0.0001, error_rate))

        # Optimal bit array size (m) and hash function count (k)
        num_bits = -1.0 * (self.capacity * math.log(self.error_rate)) / (math.log(2) ** 2)
        self.size = max(64, int(math.ceil(num_bits)))
        num_hashes = (self.size / self.capacity) * math.log(2)
        self.hash_count = max(1, int(round(num_hashes)))

        # Using a bytearray as compact bitvector
        self._bytes = bytearray(math.ceil(self.size / 8))
        self._count = 0

    def _get_hashes(self, item: str) -> list[int]:
        """Generate k hash indices using Kirsch-Mitzenmacher double hashing from a single 128-bit hash."""
        digest = hashlib.md5(item.encode("utf-8")).digest()
        h1, h2 = struct.unpack(">QQ", digest)
        indices = []
        for i in range(self.hash_count):
            combined = (h1 + i * h2) % self.size
            indices.append(combined)
        return indices

    def add(self, item: str) -> None:
        """Add an item key to the Bloom filter."""
        for bit_index in self._get_hashes(item):
            byte_idx = bit_index // 8
            bit_offset = bit_index % 8
            self._bytes[byte_idx] |= 1 << bit_offset
        self._count += 1

    def contains(self, item: str) -> bool:
        """Test whether an item may be in the set.

        Returns False if the item is DEFINITELY NOT in the set (zero false negatives).
        Returns True if the item is probably in the set.
        """
        for bit_index in self._get_hashes(item):
            byte_idx = bit_index // 8
            bit_offset = bit_index % 8
            if not (self._bytes[byte_idx] & (1 << bit_offset)):
                return False
        return True

    def __contains__(self, item: str) -> bool:
        return self.contains(item)

    def __len__(self) -> int:
        return self._count


# ============================================================================
# 3. Disjoint-Set Union (Union-Find)
# ============================================================================


class DisjointSet(Generic[T]):
    """Disjoint-Set Union (DSU) data structure with near O(α(N)) inverse Ackermann complexity.

    Supports dynamic entity equivalence partitioning, host alias resolution, and
    deterministic canonical representative selection.
    """

    def __init__(self) -> None:
        self._parent: Dict[T, T] = {}
        self._rank: Dict[T, int] = {}
        self._count = 0

    def add(self, item: T) -> None:
        """Register a new element if not already present."""
        if item not in self._parent:
            self._parent[item] = item
            self._rank[item] = 0
            self._count += 1

    def find(self, item: T) -> T:
        """Find the canonical representative of the partition containing item (with path compression)."""
        if item not in self._parent:
            self.add(item)
            return item

        # Two-pass path compression
        root = item
        while root != self._parent[root]:
            root = self._parent[root]

        curr = item
        while curr != root:
            nxt = self._parent[curr]
            self._parent[curr] = root
            curr = nxt

        return root

    def union(self, a: T, b: T) -> T:
        """Merge the sets containing elements a and b using union-by-rank.

        Returns the resulting canonical representative.
        """
        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return root_a

        rank_a = self._rank[root_a]
        rank_b = self._rank[root_b]

        if rank_a < rank_b:
            self._parent[root_a] = root_b
            winner = root_b
        elif rank_a > rank_b:
            self._parent[root_b] = root_a
            winner = root_a
        else:
            # Deterministic tie-breaking: prefer lexicographically lower str representation
            if str(root_a) <= str(root_b):
                self._parent[root_b] = root_a
                self._rank[root_a] += 1
                winner = root_a
            else:
                self._parent[root_a] = root_b
                self._rank[root_b] += 1
                winner = root_b

        self._count -= 1
        return winner

    def connected(self, a: T, b: T) -> bool:
        """Check if elements a and b belong to the same equivalence partition."""
        return self.find(a) == self.find(b)

    def get_components(self) -> Dict[T, List[T]]:
        """Return a mapping of canonical representative -> list of connected member elements."""
        groups: Dict[T, List[T]] = {}
        for item in self._parent:
            root = self.find(item)
            groups.setdefault(root, []).append(item)
        return groups

    def __len__(self) -> int:
        """Return the number of disjoint sets / components."""
        return self._count


# ============================================================================
# 4. Locality-Sensitive Hashing (MinHash)
# ============================================================================


class MinHash:
    """MinHash signature generator for estimating Jaccard similarity between text/token sets in O(K) time.

    Uses universal hash family: h_i(x) = (a_i * x + b_i) mod p.
    """

    # Large Mersenne prime 2^61 - 1
    PRIME = (1 << 61) - 1

    def __init__(self, num_perm: int = 64, seed: int = 42) -> None:
        self.num_perm = num_perm
        self.seed = seed
        self._a, self._b = self._init_permutations(num_perm, seed)
        self.signature = [self.PRIME] * num_perm

    @staticmethod
    def _init_permutations(num_perm: int, seed: int) -> tuple[List[int], List[int]]:
        import random

        rng = random.Random(seed)
        a: List[int] = []
        b: List[int] = []
        for _ in range(num_perm):
            val_a = rng.randint(1, MinHash.PRIME - 1)
            val_b = rng.randint(0, MinHash.PRIME - 1)
            a.append(val_a)
            b.append(val_b)
        return a, b

    def update(self, tokens: Iterable[str]) -> None:
        """Update the MinHash signature with a collection of string tokens or shingles."""
        for token in tokens:
            h = struct.unpack(">Q", hashlib.sha256(token.encode("utf-8")).digest()[:8])[0]
            for i in range(self.num_perm):
                ph = ((self._a[i] * h) + self._b[i]) % self.PRIME
                if ph < self.signature[i]:
                    self.signature[i] = ph

    def jaccard_similarity(self, other: "MinHash") -> float:
        """Estimate the Jaccard similarity J(A, B) = |A ∩ B| / |A ∪ B| against another MinHash."""
        if self.num_perm != other.num_perm:
            raise ValueError(f"Permutations mismatch: {self.num_perm} vs {other.num_perm}")
        matches = sum(1 for i in range(self.num_perm) if self.signature[i] == other.signature[i])
        return matches / self.num_perm

    @classmethod
    def from_text(cls, text: str, k_shingle: int = 3, num_perm: int = 64) -> "MinHash":
        """Convenience factory creating a MinHash signature from a string via k-shingling."""
        clean = text.strip().lower()
        shingles = [clean[i : i + k_shingle] for i in range(max(1, len(clean) - k_shingle + 1))]
        mh = cls(num_perm=num_perm)
        mh.update(shingles)
        return mh


# ============================================================================
# 5. 0/1 Knapsack Dynamic Programming Optimizer
# ============================================================================


def knapsack_01(
    items: Sequence[T],
    max_weight: int,
    weight_fn: Callable[[T], int],
    value_fn: Callable[[T], float],
) -> List[T]:
    """Solve the 0/1 Knapsack problem using dynamic programming to find the maximum-utility

    subset of items whose total weight (e.g. token cost) does not exceed max_weight.

    Returns the selected subset of items in their original relative order.
    """
    if max_weight <= 0 or not items:
        return []

    n = len(items)
    weights = [max(1, int(weight_fn(item))) for item in items]
    values = [float(value_fn(item)) for item in items]

    if sum(weights) <= max_weight:
        return list(items)

    dp = [[0.0] * (max_weight + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        w_i = weights[i - 1]
        v_i = values[i - 1]
        for w in range(max_weight + 1):
            if w_i <= w:
                candidate = dp[i - 1][w - w_i] + v_i
                if candidate > dp[i - 1][w]:
                    dp[i][w] = candidate
                else:
                    dp[i][w] = dp[i - 1][w]
            else:
                dp[i][w] = dp[i - 1][w]

    # Backtrack to reconstruct selected items
    selected: List[T] = []
    curr_w = max_weight
    for i in range(n, 0, -1):
        if dp[i][curr_w] != dp[i - 1][curr_w]:
            selected.append(items[i - 1])
            curr_w -= weights[i - 1]

    selected.reverse()
    return selected
