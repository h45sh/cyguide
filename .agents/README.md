# Agent Intelligence & Knowledge Architecture (`.agents/`)

This directory houses CyGuide's internal agent intelligence system. It acts as an evolving, token-efficient knowledge base designed specifically for AI agents and LLM orchestrators navigating this codebase.

---

## Directory Organization

```text
.agents/
├── README.md               # Directory overview & agent navigation guide
├── skills/
│   ├── adapter-authoring/      # Specialized skill for authoring CyGuide tool plugins
│   └── engineering-aggregate/  # Skill driving the self-evolving closed-loop intelligence system
├── threads/                # Staging area for per-thread raw retrospectives
│   └── TEMPLATE.md         # 4-pillar retrospective template used by threads
└── knowledge/              # (Created on aggregation sweep) Compact domain knowledge bases
```

---

## The Thread Insights & Aggregation Lifecycle

```text
[ Feature / Bugfix Thread ]
            │
            ▼ Writes specific engineering insights using TEMPLATE.md
[ .agents/threads/<topic>.md ]
            │
            ▼ Synthesized and consolidated periodically (after PR merges)
[ AGENTS.md & Domain Knowledge ]
            │
            ▼ De-duplicated, compressed & updated with Anti-Patterns
[ Evergreen Agent Intelligence ]
```

1. **Capture (Per-Thread)**:
   - When a development thread completes work on a feature, bugfix, or refactor, it records its key principles, non-obvious insights, anti-patterns, and invariants into `.agents/threads/<topic>.md`.
2. **Consolidate (Post-Merge Sweep)**:
   - Periodically after branches merge into `dev`, an aggregating agent reads the new thread files in `.agents/threads/`.
   - The insights are distilled, de-duplicated, and integrated into `AGENTS.md` and specialized domain files to avoid token bloat.
   - Outdated or broken patterns are logged to prevent future regressions.
