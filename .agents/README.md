# Agent Intelligence & Knowledge Architecture (`.agents/`)

This directory houses CyGuide's internal agent intelligence system powered by `engineering-aggregate`. It acts as an evolving, token-efficient collective memory designed specifically for AI agents and LLM orchestrators navigating this codebase.

---

## Directory Organization

```text
.agents/
├── README.md               # Directory overview & agent navigation guide
├── hooks/                  # Dynamic lifecycle hooks (pre_inherit, etc.)
├── skills/
│   └── adapter-authoring/  # Specialized skill for authoring CyGuide tool plugins
├── threads/                # Staging area for per-thread raw retrospectives (git-ignored)
│   ├── TEMPLATE.md         # 4-pillar retrospective template used by threads
│   └── thread_*.md         # Historical thread archives (Tier 3)
└── knowledge/              # Compact domain knowledge bases & routing index (Tier 2)
    ├── index.json          # Knowledge routing table & fast anti-pattern registry
    ├── ui.md               # UI & Textual presentation invariants & lifecycles
    ├── engine.md           # Core engine, subprocess execution & sanitization
    ├── storage.md          # Graph persistence, SQLite transactions & checkpoints
    ├── security.md         # SSRF defense, gateway boundaries & credential hygiene
    ├── tooling.md          # Pluggable adapter architecture & recipe guidelines
    ├── testing.md          # Multi-tier testing pyramid, AST gates & fuzzing proofs
    ├── anti-patterns.md    # Catalog of prohibited patterns and required replacements
    └── invariants.md       # Quantitative runtime & benchmark contracts
```

---

## The Autonomous Protocol for Agents

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                   THE ZERO-BLOAT AGENT LIFECYCLE                       │
 │                                                                        │
 │   1. PRE-FLIGHT (Compact)        2. EXECUTE TASK      3. ONE-SHOT TITHE│
 │  ┌─────────────────────────┐    ┌──────────────┐    ┌────────────────┐ │
 │  │ python3 scripts/agg.py  │───►│ Write Code   │───►│ python3 scripts│ │
 │  │ inherit --compact ...   │    │ & Run Tests  │    │ /agg.py        │ │
 │  │ (<150 tokens, 1 round)  │    │              │    │ quick-tithe ...│ │
 │  └─────────────────────────┘    └──────────────┘    └────────────────┘ │
 │                                                     (Atomic <50ms,     │
 │                                                      Zero round-trips) │
 └────────────────────────────────────────────────────────────────────────┘
```

1. **Task Startup (Ancestral Inheritance)**:
   ```bash
   python3 scripts/agg.py inherit --compact --files <touched_files> --query "<task_description>"
   ```
2. **Implementation (Pure Focus)**: Deliver code, benchmarks, and passing tests.
3. **Paying the Tithe (One-Shot Atomic Quick-Tithe)**:
   ```bash
   python3 scripts/agg.py quick-tithe --topic <topic> --domain <UI|Engine|Storage|Security|Testing> --summary "<summary>" --verify-cmd "<test_command>"
   ```
   *Or for background / subagent tasks*:
   ```bash
   python3 scripts/agg.py auto-tithe
   ```
4. **Knowledge Audit & Anti-Entropy Sweep**:
   ```bash
   python3 scripts/agg.py condense
   python3 scripts/agg.py deslop
   python3 scripts/agg.py test
   ```
