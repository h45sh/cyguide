"""Attack path analysis, blast radius calculation, and graph intelligence."""

import json
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple


class GraphAnalyticsEngine:
    """In-memory directed graph intelligence engine for security operations.

    Provides deterministic attack path computation (BFS shortest path),
    blast-radius calculations (transitive descendant reachability), and
    crown-jewel critical asset identification across session findings.
    """

    CRITICAL_PORTS: Set[int] = {
        21,  # FTP
        22,  # SSH
        23,  # Telnet
        88,  # Kerberos
        389,  # LDAP
        445,  # SMB / Active Directory
        636,  # LDAPS
        1433,  # MS-SQL
        1521,  # Oracle DB
        3306,  # MySQL
        3389,  # RDP
        5432,  # PostgreSQL
        5985,  # WinRM HTTP
        5986,  # WinRM HTTPS
        6379,  # Redis
        8443,  # HTTPS Admin
        9200,  # Elasticsearch
        27017,  # MongoDB
    }

    def __init__(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        self.nodes_by_id: Dict[str, Dict[str, Any]] = {n["id"]: n for n in nodes}
        self.edges = edges

        # Adjacency lists: source_id -> list of (target_id, relation_type)
        self._adj: Dict[str, List[Tuple[str, str]]] = {n_id: [] for n_id in self.nodes_by_id}
        # Reverse adjacency: target_id -> list of (source_id, relation_type)
        self._rev_adj: Dict[str, List[Tuple[str, str]]] = {n_id: [] for n_id in self.nodes_by_id}

        for edge in edges:
            src = edge.get("source_id")
            tgt = edge.get("target_id")
            rel = edge.get("relation_type", "related_to")
            if src in self._adj and tgt in self.nodes_by_id:
                self._adj[src].append((tgt, rel))
            if tgt in self._rev_adj and src in self.nodes_by_id:
                self._rev_adj[tgt].append((src, rel))

    def find_shortest_attack_path(
        self, source_id: str, target_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Compute the shortest directed attack path between two entities via BFS.

        Returns an ordered list of node dictionaries representing the path from
        source to target, or None if no directed path exists.
        """
        if source_id not in self.nodes_by_id or target_id not in self.nodes_by_id:
            return None

        if source_id == target_id:
            return [self.nodes_by_id[source_id]]

        queue: deque[Tuple[str, List[str]]] = deque([(source_id, [source_id])])
        visited: Set[str] = {source_id}

        while queue:
            curr, path = queue.popleft()

            for neighbor, _ in self._adj.get(curr, []):
                if neighbor == target_id:
                    full_path = path + [neighbor]
                    return [self.nodes_by_id[nid] for nid in full_path]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def calculate_blast_radius(self, compromised_node_id: str, max_depth: int = 10) -> Set[str]:
        """Compute the compromise blast radius (all transitively reachable nodes).

        Traverses both outgoing relationships and bi-directional associations
        to determine everything an attacker can pivot to or affect from this asset.
        """
        if compromised_node_id not in self.nodes_by_id:
            return set()

        reachable: Set[str] = set()
        queue: deque[Tuple[str, int]] = deque([(compromised_node_id, 0)])
        visited: Set[str] = {compromised_node_id}

        while queue:
            curr, depth = queue.popleft()
            if depth >= max_depth:
                continue

            # Check forward links
            for neighbor, _ in self._adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    reachable.add(neighbor)
                    queue.append((neighbor, depth + 1))

            # Also consider services on the same host (reverse links for running_on)
            for parent, _rel in self._rev_adj.get(curr, []):
                if parent not in visited:
                    visited.add(parent)
                    reachable.add(parent)
                    queue.append((parent, depth + 1))

        return reachable

    def identify_critical_assets(self) -> List[Dict[str, Any]]:
        """Identify high-value crown-jewel assets from graph intelligence.

        Flags:
        - Compromised credentials (`credential.found`)
        - High / Critical vulnerabilities (`vulnerability.found`, `web.vulnerability`)
        - Database, management, or authentication services (`network.service`)
        - Internal corporate hosts (`host_internal`)
        """
        critical_assets: List[Dict[str, Any]] = []

        for node in self.nodes_by_id.values():
            schema = node.get("schema_type", "")
            data_raw = node.get("data_json", "{}")
            pik_raw = node.get("pik_json", "{}")

            try:
                data = json.loads(data_raw) if isinstance(data_raw, str) else data_raw
            except Exception:
                data = {}

            try:
                pik = json.loads(pik_raw) if isinstance(pik_raw, str) else pik_raw
            except Exception:
                pik = {}

            # 1. Credentials are high-value
            if schema == "credential.found":
                critical_assets.append(node)
                continue

            # 2. Critical or High Vulnerabilities
            if schema in ("vulnerability.found", "web.vulnerability"):
                severity = str(data.get("severity", "")).upper()
                if severity in ("CRITICAL", "HIGH"):
                    critical_assets.append(node)
                    continue

            # 3. High-impact services (Databases, SSH, SMB, RDP)
            if schema == "network.service":
                port = pik.get("port")
                if port is not None:
                    try:
                        if int(port) in self.CRITICAL_PORTS:
                            critical_assets.append(node)
                            continue
                    except (ValueError, TypeError):
                        pass

            # 4. Internal / High-value hosts
            if schema == "host_internal":
                critical_assets.append(node)
                continue

        return critical_assets

    def find_all_attack_paths_to_critical(
        self, perimeter_types: Optional[Set[str]] = None
    ) -> Dict[str, List[List[Dict[str, Any]]]]:
        """Map shortest attack paths from all perimeter entrypoints to critical assets.

        Returns a dictionary mapping critical asset node IDs to lists of paths.
        """
        if perimeter_types is None:
            perimeter_types = {"dns.record", "web.endpoint", "network.host"}

        critical_assets = self.identify_critical_assets()
        entrypoints = [
            n for n in self.nodes_by_id.values() if n.get("schema_type") in perimeter_types
        ]

        results: Dict[str, List[List[Dict[str, Any]]]] = {}

        for asset in critical_assets:
            target_id = asset["id"]
            paths_for_asset = []
            for entry in entrypoints:
                source_id = entry["id"]
                if source_id == target_id:
                    continue
                path = self.find_shortest_attack_path(source_id, target_id)
                if path:
                    paths_for_asset.append(path)

            if paths_for_asset:
                results[target_id] = paths_for_asset

        return results

    def calculate_betweenness_centrality(self) -> Dict[str, float]:
        """Compute betweenness centrality for all nodes using Brandes' algorithm.

        Time complexity: O(V * E). Identifies critical pivot nodes, dual-homed gateways,
        and choke points across the session entity topology.
        """
        nodes = list(self.nodes_by_id.keys())
        cb: Dict[str, float] = {v: 0.0 for v in nodes}

        for s in nodes:
            stack: List[str] = []
            predecessors: Dict[str, List[str]] = {w: [] for w in nodes}
            sigma: Dict[str, float] = {w: 0.0 for w in nodes}
            sigma[s] = 1.0
            dist: Dict[str, int] = {w: -1 for w in nodes}
            dist[s] = 0

            q: deque[str] = deque([s])
            while q:
                v = q.popleft()
                stack.append(v)
                v_dist = dist[v]
                v_sigma = sigma[v]

                for w, _ in self._adj.get(v, []):
                    # Path discovery
                    if dist[w] < 0:
                        dist[w] = v_dist + 1
                        q.append(w)
                    # Path counting
                    if dist[w] == v_dist + 1:
                        sigma[w] += v_sigma
                        predecessors[w].append(v)

            delta: Dict[str, float] = {w: 0.0 for w in nodes}
            # Accumulation: back-propagate dependencies
            while stack:
                w = stack.pop()
                coeff = (1.0 + delta[w]) / sigma[w]
                for v in predecessors[w]:
                    delta[v] += sigma[v] * coeff
                if w != s:
                    cb[w] += delta[w]

        # For directed graph, normalize by (N-1)(N-2) if N > 2
        n = len(nodes)
        if n > 2:
            scale = 1.0 / ((n - 1) * (n - 2))
            for v in cb:
                cb[v] *= scale

        return cb

    def find_strongly_connected_components(self) -> List[List[str]]:
        """Identify strongly connected components (SCC) in O(V + E) using Tarjan's algorithm."""
        index = 0
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        on_stack: Set[str] = set()
        stack: List[str] = []
        sccs: List[List[str]] = []

        def _strongconnect(v: str) -> None:
            nonlocal index
            indices[v] = index
            lowlinks[v] = index
            index += 1
            stack.append(v)
            on_stack.add(v)

            for w, _ in self._adj.get(v, []):
                if w not in indices:
                    _strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                sccs.append(scc)

        for node_id in self.nodes_by_id:
            if node_id not in indices:
                _strongconnect(node_id)

        return sccs

    def compute_transitive_closure(self) -> Dict[str, Set[str]]:
        """Compute the full transitive reachability closure matrix for all nodes in the graph."""
        reachability: Dict[str, Set[str]] = {}
        for node_id in self.nodes_by_id:
            visited: Set[str] = set()
            q: deque[str] = deque([node_id])
            while q:
                curr = q.popleft()
                for neighbor, _ in self._adj.get(curr, []):
                    if neighbor not in visited and neighbor != node_id:
                        visited.add(neighbor)
                        q.append(neighbor)
            reachability[node_id] = visited
        return reachability

    def to_networkx(self) -> Optional[Any]:
        """Convert in-memory graph to a networkx.DiGraph instance if networkx is available."""
        try:
            import networkx as nx

            g = nx.DiGraph()
            for n_id, n in self.nodes_by_id.items():
                g.add_node(n_id, **n)
            for edge in self.edges:
                g.add_edge(
                    edge["source_id"],
                    edge["target_id"],
                    relation_type=edge.get("relation_type", "related_to"),
                )
            return g
        except ImportError:
            return None
