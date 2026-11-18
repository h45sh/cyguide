# Quantitative Invariants & Performance Contracts (Tier 2)

## 1. Runtime Performance Thresholds
- **Cold Application Launch**: $< 600\text{ms}$ cold import time; hard ceiling is **$950\text{ms}$** (`python -c "import cyguide.app"`).
- **Terminal Stream RAM Buffer**: Heap footprint strictly bounded to $\le 5\text{MB}$ via bounded ring buffer (`deque(maxlen=5000)`).
- **Terminal Stream Throughput**: Sustained rendering rate $\ge 50,000\text{ lines/sec}$ (stress tested to $> 90,000\text{ lines/sec}$) with quad markup disabled (`markup=False`).
- **GraphStore Ingestion Rate**: Bulk findings ingestion $\ge 2,000\text{ entities/sec}$ (hard CI floor $\ge 1,200\text{ entities/sec}$ under virtualized runners).
- **GraphStore Scale Queries**: 5,000 nodes and 2,500 edges queried in $\le 500\text{ms}$ in SQLite via parameter-bound queries and indexed foreign keys.
- **EntityBrowser Virtualization**: 5,000 nodes refresh & filter in $\le 500\text{ms}$; 10k item DOM rebuild $< 60\text{ms}$ (ceiling $160\text{ms}$); category roots capped at `MAX_DISPLAY_PER_CATEGORY = 200`.
- **Explanation Stream Rendering**: Single `Static` widget via `render_markdown()`; zero per-paragraph DOM sub-widget churn ($O(1)$ memory allocation).

## 2. CI Runner Variance & Benchmark Rules
- **No Microsecond Assertions**: In-memory operations running in 15–35ms on bare metal can take 150–250ms on shared GitHub Actions runners due to multi-tenant CPU contention and virtualized I/O scheduling.
- **Benchmark Threshold Standard**: For operations processing 5,000+ entities, set CI performance bounds to $< 500\text{ms}$. This accommodates hypervisor jitter while reliably catching $O(N^2)$ algorithmic regressions ($> 5,000\text{ms}$).
- **UI Debounce Settle Time**: Bounded settle loop $\le 1000\text{ms}$ total (max 20–30 iterations at $0.05\text{s}$ pause).
- **CI Execution Time**: Target $\le 3\text{ minutes}$ per matrix job with optimized pip caching and concurrency cancellation enabled.

## 3. Security, Operational & Release Boundaries
- **Ephemeral Release Authentication**: PyPI and GHCR release jobs use strictly short-lived GitHub Actions OIDC tokens (`id-token: write`); zero long-lived API secrets.
- **Packaging Integrity**: 100% packaged asset verification by building and testing the real distribution wheel artifact (`dist/*.whl`) in CI.
- **SSRF Blocklist Preservation**: `ActionGateway.BLOCKED_TARGETS` must permanently block AWS IMDSv2, Alibaba metadata, IPv4 link-local (`169.254.0.0/16`), and hexadecimal/decimal IP encodings.
- **Subprocess Environment Isolation**: Subprocess spawning must always execute `sanitize_subprocess_env()` to strip API keys, cloud credentials, and SSH handles.
- **Token Caps**: Cloud LLM calls enforce explicit generation caps (`max_tokens: 1500`) to prevent runaway billing spikes.
- **Downstream Parity**: Merged commits on `main` mirrored to `dev` within $10\text{s}$ via `sync-main-to-dev.yml`.
- **Deterministic Token Gating**: `.t3-architecture-cache.md` must maintain $\ge 90\%$ token reduction relative to raw codebase line count (currently 94.4%, condensing ~32,000 lines into ~1,800 interface lines).
- **Release Check Preflight**: All 6 stages in `scripts/release-check.sh:L1` (Lint, Pytest, Schema Sync, Performance Guard, Build, Asset Check) must pass with zero warnings prior to release.

## 4. Testing & Architectural Invariants
- **Fast Pre-Flight Tier 0 (`pytest -m tier0 -q`)**: Must complete in $< 4.0\text{s}$ (observed $\sim 3.5\text{s}$) with zero network calls and zero flakiness.
- **AST Architecture Enforcement**: Zero `shell=True`, zero `os.system`, zero direct `subprocess` imports in `cyguide/ui/` or `tools/`, and zero unparameterized SQL queries (`tests/unit/test_architecture.py:L1`).
- **Adapter Crash-Resilience**: 100% crash immunity across all registered security tool adapters against hostile, malformed ANSI, truncated JSON, and 20k-token fuzz streams (`tests/unit/test_parsers/test_fuzz_all_adapters.py:L53`).
- **Concurrency & Ring Buffer Boundedness**: Zero deadlocks and strict $O(1)$ RAM bounding ($\le 5000$ lines) under 40,000 concurrent streaming log lines (`tests/unit/test_engine_stress.py:L1`).

