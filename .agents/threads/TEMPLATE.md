# Thread Retrospective: <Feature / Bugfix / Refactor Name>

- **Branch / PR**: `<branch-name>` (Commit `<sha>`)
- **Primary Domain**: `[UI | Engine | Storage | Benchmarks | AI / LLM | Security | Tooling | CLI]`
- **Author / Contributor**: `@h45sh`

---

## Pillar 1: Aggregate Intelligence Feedback
*Evaluate techniques previously documented in `.agents/knowledge/` or `AGENTS.md` that were applied during this thread:*

| Technique / Rule Consulted | Outcome | Assessment | Detail & Context |
| :--- | :---: | :---: | :--- |
| *e.g., Virtualized CI runner benchmark buffer* | **VALIDATED** | Evergreen | Threshold of <500ms prevented flaky failures on macOS arm64 runner. |
| *e.g., Unbounded Textual Markdown streaming* | **FAILED** | Anti-Pattern | Caused NoneType region crash; required monkeypatch in compat.py. |
| *e.g., Settle delay pause duration* | **SITUATIONAL** | Conditional | `pilot.pause(0.1)` was sufficient on Linux, but macOS required 0.2s. |
| *e.g., SQLite WAL multi-reader concurrency* | **INSUFFICIENT DATA** | Needs Test | Only tested with 10 readers; needs 100+ concurrent reader stress test. |

*Assessment Options*:
- `VALIDATED` (Evergreen pattern, fully held true in practice)
- `FAILED` (Anti-pattern, broke under execution or triggered bugs)
- `SITUATIONAL` (Holds true only under specific runtime/platform constraints)
- `INSUFFICIENT DATA` (Promising hypothesis, but needs broader edge-case testing)

---

## Pillar 2: Novel Discoveries & Codebase Realities
*Document new non-obvious engineering principles, runtime quirks, or architectural seams uncovered in this thread:*

- **Principle**: *Clear, declarative name of the insight.*
- **Problem Solved**: *What bug, performance cliff, or architectural friction did it resolve?*
- **Mechanism**: *How does it work at the code/engine layer?*
- **Concrete Code Reference**: `path/to/file.py:L12-L34`

---

## Pillar 3: Anti-Patterns & Prohibited Techniques (What NOT to do)
*Document dead ends, failed attempts, and practices that future agents must strictly avoid:*

- **Anti-Pattern**: *Name of the prohibited approach.*
- **Why it Failed**: *What failure mode occurred (e.g. race condition, memory leak, UI lockup, security hole)?*
- **Correct Replacement**: *What technique must be used instead?*

---

## Pillar 4: Invariants & Performance Contracts to Preserve
*Document quantitative bounds, algorithmic complexities, and security boundaries proven in this thread:*

| Contract / Invariant | Threshold / Guarantee | Verification Command |
| :--- | :--- | :--- |
| *e.g., Terminal Stream Memory* | $\le 5\text{ MB}$ resident heap | `pytest tests/unit/test_benchmarks.py -k test_terminal_stream` |
| *e.g., SSRF IMDSv2 Blocking* | 100% rejection of link-local IP | `pytest tests/unit/test_gateway.py` |
