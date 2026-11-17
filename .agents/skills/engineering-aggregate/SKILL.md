---
name: engineering-aggregate
description: Evolve CyGuide's collective engineering intelligence through structured end-of-thread retrospectives, empirical validation, anti-pattern discovery, and iterative knowledge condensation. Use when completing an implementation thread, conducting an architectural post-mortem, logging engineering insights, evaluating prior techniques, or synthesizing multi-thread intelligence into domain knowledge bases.
---

# CyGuide Engineering Aggregate Skill

This skill governs CyGuide's self-evolving collective memory system. It transforms every development thread into an active learning node that evaluates existing engineering techniques, records novel insights, identifies broken or situational anti-patterns, and condenses findings into a token-efficient knowledge base.

---

## 1. The Closed-Loop Feedback Architecture

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      THE SELF-EVOLVING CYCLE                           │
 │                                                                        │
 │   1. INGEST               2. APPLY & TEST         3. DEPOSIT           │
 │  ┌──────────────┐        ┌──────────────┐        ┌──────────────────┐  │
 │  │ Read Domain  │───────►│ Implement    │───────►│ File End-of-     │  │
 │  │ Knowledge    │        │ & Stress-Test│        │ Thread Review    │  │
 │  └──────────────┘        └──────────────┘        └──────────────────┘  │
 │         ▲                                                  │           │
 │         │                                                  ▼           │
 │         │          4. CONDENSE & PRUNE                     │           │
 │         │         ┌───────────────────────┐                │           │
 │         └─────────│  Prune, Merge, Update │◄───────────────┘           │
 │                   │  Anti-Patterns & Rules│                            │
 │                   └───────────────────────┘                            │
 └────────────────────────────────────────────────────────────────────────┘
```

1. **Pre-flight Ingestion**: At the start of a task, the agent inspects relevant domain knowledge files (`.agents/knowledge/<domain>.md`) and `AGENTS.md` to avoid known traps.
2. **Empirical Verification**: The agent actively tests techniques during coding, test runs, and benchmarks.
3. **Structured Deposit**: At the end of the thread, the agent writes a retrospective using the standardized schema into `.agents/threads/thread_<topic>.md`.
4. **Condensation & Pruning**: Periodically (or during post-merge consolidation sweeps), deposits are distilled into domain knowledge bases, eliminating duplicates, adding edge-case conditions, and cataloging anti-patterns.

---

## 2. End-of-Thread Retrospective Schema

When completing a development thread, author `.agents/threads/thread_<topic>.md` following this four-pillar evaluation structure:

```markdown
# Thread Retrospective: <Feature / Bugfix / Refactor Name>

- **Branch / PR**: `<branch-name>` (Commit `<sha>`)
- **Primary Domain**: `[UI | Engine | Storage | Benchmarks | AI / LLM | Security | Tooling | CLI]`
- **Author / Contributor**: `@h45sh`

---

### Pillar 1: Aggregate Intelligence Feedback
*Evaluate principles or techniques previously documented in `.agents/knowledge/` or `AGENTS.md` that were applied during this thread:*

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

### Pillar 2: Novel Discoveries & Codebase Realities
*Document new non-obvious engineering principles, runtime quirks, or architectural seams uncovered in this thread.*

- **Principle**: *Clear, declarative name of the insight.*
- **Problem Solved**: *What bug, performance cliff, or architectural friction did it resolve?*
- **Mechanism**: *How does it work at the code/engine layer?*
- **Concrete Code Reference**: `path/to/file.py:L12-L34`

---

### Pillar 3: Anti-Patterns & Prohibited Techniques (What NOT to do)
*Document dead ends, failed attempts, and practices that future agents must strictly avoid.*

- **Anti-Pattern**: *Name of the prohibited approach.*
- **Why it Failed**: *What failure mode occurred (e.g. race condition, memory leak, UI lockup, security hole)?*
- **Correct Replacement**: *What technique must be used instead?*

---

### Pillar 4: Invariants & Performance Contracts to Preserve
*Document quantitative bounds, algorithmic complexities, and security boundaries proven in this thread.*

| Contract / Invariant | Threshold / Guarantee | Verification Command |
| :--- | :--- | :--- |
| *e.g., Terminal Stream Memory* | $\le 5\text{ MB}$ resident heap | `pytest tests/unit/test_benchmarks.py -k test_terminal_stream` |
| *e.g., SSRF IMDSv2 Blocking* | 100% rejection of link-local IP | `pytest tests/unit/test_gateway.py` |
```

---

## 3. Knowledge Condensation & Pruning Protocol

To prevent context bloat and keep token costs minimal for future agents, raw thread retrospectives are periodically synthesized into domain files under `.agents/knowledge/`.

### The 3-Tier Storage Hierarchy

| Tier | Directory / File | Target Size | Audience | Purpose |
| :--- | :--- | :---: | :--- | :--- |
| **Tier 1: Global Invariants** | `AGENTS.md` | $\le 250$ lines | All agents on startup | High-leverage repository laws and architectural invariants. |
| **Tier 2: Domain Knowledge** | `.agents/knowledge/<domain>.md` | 50–150 lines | Agents working in that specific domain | Compressed, actionable rules, edge-case conditions, and code patterns. |
| **Tier 3: Historical Thread Logs** | `.agents/threads/*.md` | Unlimited | Archival & audit reference | Full narrative context of past development threads. |

### Condensation Rules:

1. **Rule of 3 (Promotion)**:
   - When a pattern or invariant is validated across 3 distinct thread files $\rightarrow$ Promote it to a permanent rule in `AGENTS.md` or the primary domain knowledge file.
2. **Immediate Anti-Pattern Cataloging**:
   - When a technique fails and is confirmed hazardous $\rightarrow$ Add it directly to `.agents/knowledge/anti-patterns.md` with the failure mode and the mandated replacement.
3. **De-duplication & Pruning**:
   - Never append redundant summaries. If a new thread confirms an existing rule, update the existing entry with additional nuance, edge-case constraints, or platform notes.
4. **Situational Flagging**:
   - If a rule only applies under specific environments (e.g. macOS CI runners, low-memory local LLMs), explicitly add the qualifier: `"[CONDITION: macOS runners] ..."`.

---

## 4. Execution Workflow for Agents

### When concluding a development task:
1. Review git diff and PR changes.
2. Create `.agents/threads/thread_<topic>.md` using the retrospective schema.
3. Fill all 4 pillars with concrete, empirical observations from tests and runs.
4. Commit the thread retrospective alongside your work.

### When performing an aggregation sweep:
1. Scan all un-aggregated files in `.agents/threads/`.
2. Extract novel rules, confirmed validations, and anti-patterns.
3. Update `.agents/knowledge/<domain>.md` and `.agents/knowledge/anti-patterns.md`.
4. Update `AGENTS.md` if any global architectural invariants changed.
5. Verify changes with `git diff` to ensure zero redundant token bloat.
