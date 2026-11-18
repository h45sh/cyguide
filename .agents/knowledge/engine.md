# Domain Knowledge: Engine & Execution Lifecycle (Tier 2)

## 1. Core Architecture & Lifecycles
- **Deep Modules**: The engine hides orchestration complexity behind deep facades: `ExecutionSession` (`cyguide/engine/execution_session.py:L25`), `ActionGateway` (`cyguide/engine/gateway.py:L1`), and `PowerWorkspaceFacade` (`cyguide/engine/power_facade.py:L16`).
- **Cold App Launch Contract**: Cold startup benchmark must remain $< 600\text{ms}$ (hard ceiling $950\text{ms}$). Verified via `python -c "import cyguide.app"` (`cyguide/app.py:L1`).
- **Decoupled Startup Network Stacks**: Never import heavy HTTP clients (`httpx`, `openai`, `anthropic`, `dotenv`) at root package level or during app startup. Primitives like `is_placeholder_key` live in `cyguide/common/keys.py:L1`.
- **On-Demand Screen Loading & Dynamic PEP 562 Symbol Re-Exporting**:
  - Secondary screens are registered via `cyguide/ui/screens/lazy.py:L1` callables in `SCREENS`.
  - `cyguide/ui/screens/__init__.py:L1` uses PEP 562 `__getattr__` module-level dynamic resolution, cutting cold start latency ~43% (~950ms down to ~540ms) without breaking imports.

## 2. Process Execution & Subprocess Invariants
- **Argument Vector Mandate**: `shell=True` and string concatenation are strictly prohibited. Construct commands as explicit argument vectors (`List[str]`) executed via `asyncio.create_subprocess_exec` in `cyguide/engine/executor.py:L17`.
- **Secret Isolation**: Child processes automatically inherit the parent process environment by default. Subprocess spawning MUST pass through `sanitize_subprocess_env()` to strip `CYGUIDE_*`, `OPENAI_*`, `ANTHROPIC_*`, `AWS_*`, `GITHUB_*`, and SSH keys.
- **Dual-Tier Token Guardrails**: Bounded generation limits (`max_tokens: 1500`) prevent runaway scanning costs. On HTTP 429 rate limits, parse standard `Retry-After` headers and enforce bounded backoff ($1\text{s} \le \text{cooldown} \le 300\text{s}$) with multi-key profile failover.
- **Category-Aware Prompt Directives**: Dynamically adapt system prompts based on tool domain and model capacity (`is_active_model_local()`). Local 4B/7B models receive rigid schemas; large cloud models receive holistic attack-chain analysis prompts.

## 3. Tool Sanitization & Ingestion Dataflow
- **The Sanitization Invariant**: Raw stdout stream written to disk/console (`data/logs/{action_id}.log`) remains immutable. However, stdout fed into LLM tutor contexts MUST pass through `ToolAdapter.sanitize_output` (`cyguide/engine/adapter.py:L1`).
- **Noise Stripping**: Strips ASCII banners, diagnostic logs, and animated progress bars to preserve 300–800 tokens per prompt and prevent small open-weight model hallucination.
- **Untrusted Scanner Sanitization**: Wrap scan outputs in `<untrusted_scan_output>...</untrusted_scan_output>` and escape closing tag breakouts (`<\\/untrusted_scan_output>`).
- **Terminal Stream Ring Buffer**: In-memory logs use an $O(1)$ ring buffer (`deque(maxlen=5000)`) strictly bounded to $\le 5\text{MB}$ RAM, maintaining throughput $\ge 50,000\text{ lines/sec}$ with quadratic markup disabled (`markup=False`).
