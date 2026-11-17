# Thread Insight: API Guardrails, Tool Sanitization, Virtualized CI Resilience & Dataflow

- **Branch / PR**: `feat/api-guardrails-and-tool-intelligence` (merged to `dev` at `f803e91`)
- **Primary Domain**: `[AI / LLM | Tooling | Benchmarks | UI | Engine | Storage]`
- **Author / Contributor**: `@h45sh`

---

## 1. Key Principles & Architectural Techniques Introduced

### 1.1. Dual-Tier Token Guardrails & Bounded Rate-Limit Backoff
- **Hard Generation Caps (`max_tokens: 1500`)**: Cloud LLMs (OpenAI, Anthropic, OpenRouter) must enforce bounded output token limits at the API client layer. Without explicit bounds, broad security questions on large scans trigger runaway token consumption and multi-dollar billing spikes.
- **Header-Driven Cooldown Engine**: On HTTP 429 rate limits, parse the standard `Retry-After` header. Enforce bounded cooldowns ($1\text{s} \le \text{cooldown} \le 300\text{s}$) with multi-key profile failover rather than infinite retry loops or immediate hard crashes.
- **Category-Aware Prompt Directives**: Dynamically adapt system prompts based on the tool's security domain (`network`, `recon`, `web`, `vulnerability`, `osint`, `dns`, `exploit`) and model capacity (`is_active_model_local()`). Smaller 4B/7B local models receive rigid single-task schemas; large cloud models receive holistic attack-chain analysis prompts.

### 1.2. Tool Output Sanitization Hooks (`ToolAdapter.sanitize_output`)
- **The Invariant**: Core framework never alters raw stdout stream written to disk/console (`data/logs/{action_id}.log`), but **MUST sanitize** stdout before feeding it to LLM tutor contexts.
- **Noise Elimination**: Dedicated hook in `ToolAdapter` (`tools/ffuf/`, `tools/nuclei/`) strips ASCII art banners, progress bars (`Progress: [21/100]`), and verbose diagnostic logs.
- **Token Efficiency**: Prevents 300–800 tokens of non-informational ASCII art from burning LLM context windows and confusing small open-weight models.

### 1.3. Lab Checkpointing vs Continuous Auto-Save (`.cyglab`)
- **The Mental Model**: Penetration test engagements require immutable audit journals (Power Mode). Educational exploration (Learning Mode) requires a **Quicksave / Load Checkpoint** model.
- **Why**: Students running experimental or aggressive commands generate garbage findings and rate limits. Forcing continuous auto-save pollutes the database with broken states.
- **Implementation**: Serializes discovered graph nodes, terminal log buffers, Socratic tutor history, active recipe index, and student reflection notes via zero-copy SQLite attachments (`ATTACH DATABASE`).

---

## 2. Non-Obvious Insights & Codebase Realities

### 2.1. Virtualized CI Runner Variance vs Bare-Metal Execution
- **The Pitfall**: On bare-metal developer machines, in-memory operations across 5,000 entities execute in 15–35ms.
- **The Reality**: GitHub Actions macOS (arm64/x86) and Ubuntu runners run under shared, hyperthreaded multi-tenant virtualization. CPU throttling and I/O noise can inflate execution times to 150–250ms for identical operations.
- **Rule of Thumb for Benchmarks**:
  - Never set microscopic `< 50ms` or `< 100ms` bounds for operations processing 5,000+ entities in test suites that run in CI.
  - Set thresholds to `< 500ms`. This provides a generous 2.5x–5x buffer against CI runner variance while strictly catching algorithmic $O(N^2)$ regressions (which take 5,000ms+).

### 2.2. Textual Markdown Table Event Forwarding Crash
- **The Pitfall**: Clicking inside a rapidly streaming Markdown pane containing rendered tables triggers `AttributeError: 'NoneType' object has no attribute 'region'` in Textual's `Screen._forward_event`.
- **The Fix**: Applied monkeypatch in `cyguide/ui/compat.py` setting `MarkdownTableContent.ALLOW_SELECT = False` and wrapping event coordinate resolution in safe fallback handlers.

### 2.3. Asynchronous Screen Mount & Debounce Timing
- **The Pitfall**: Asserting UI state immediately after triggering a screen transition or workspace switch fails with `WaitForScreenTimeout` or stale DOM values.
- **The Reality**: Textual employs reactive property watchers and internal debouncing. Tests verifying state transitions must await `pilot.pause(0.2)` or `settle_d()` to allow the event loop to drain pending reactive message pumps before running assertions.

---

## 3. Anti-Patterns & Outdated Techniques (What NOT to do)

1. **NEVER use `shell=True` or Concatenate Command Strings**:
   - Arbitrary string construction (`f"{binary} {flags} {target}"`) invites command injection and breaks on spaces/special characters.
   - Always pass argument vectors (`List[str]`) to `asyncio.create_subprocess_exec`.
2. **NEVER Pass Operator Secrets to Child Subprocesses**:
   - Subprocesses automatically inherit the parent process environment (`os.environ`) by default.
   - Always run `sanitize_subprocess_env()` to strip `CYGUIDE_*`, `OPENAI_*`, `ANTHROPIC_*`, `AWS_*`, `GITHUB_*`, and SSH keys before spawning child tools.
3. **NEVER Mutate SQLite Directly from UI Widgets**:
   - UI widgets (`cyguide/ui/widgets/`) must never import or call `db.execute()`.
   - All mutations must flow through high-level facades (`PowerWorkspaceFacade`, `LearningSession`) to ensure transactional consistency, SSRF validation, and pub/sub event emission.
4. **NEVER Accumulate Streaming Logs in Unbounded Lists or Strings**:
   - `+=` string concatenation on high-speed stdout streams (like `ffuf` 10,000 req/s) triggers severe memory fragmentation and UI freezes.
   - Always use bounded `collections.deque(maxlen=5000)` in terminal widgets and flush raw logs directly to disk.
5. **NEVER Trust Untrusted Scanner Output in LLM Prompts**:
   - Raw scanner outputs can contain malicious payloads designed for LLM prompt injection.
   - Always wrap scan output in `<untrusted_scan_output>...</untrusted_scan_output>` and escape closing tag breakouts (`<\\/untrusted_scan_output>`).

---

## 4. Invariants & Performance Contracts to Preserve

| Component | Target Contract | Hard Invariant |
| :--- | :--- | :--- |
| **Terminal Stream RAM** | Heap bounded strictly to $\le 5\text{ MB}$ | Bounded ring buffer (`deque(maxlen=5000)`), never unbounded memory growth. |
| **Terminal Stream Throughput** | $\ge 50,000\text{ lines/sec}$ | Atomic chunk batching; quadratic markup disabled (`markup=False`). |
| **GraphStore Ingestion** | 5,000 nodes ingested in $\le 4.0\text{s}$ | Atomic transaction batching (`upsert_findings_batch`). |
| **GraphStore Scale Queries** | 5,000 nodes queried in $\le 500\text{ms}$ | Fully indexed SQLite schema; parameter-bound queries. |
| **EntityBrowser Virtualization** | 5,000 nodes refresh & filter $\le 500\text{ms}$ | DOM virtualization; only visible viewport rendered. |
| **SSRF Link-Local Protection** | 100% rejection of `169.254.0.0/16` & IMDSv2 | `ActionGateway` strictly validates IP strings and alternate encodings. |
| **File Permissions** | Private credentials created with mode `0o600` | Created atomically via `os.open` with `0o600` flags (no TOCTOU chmod window). |
