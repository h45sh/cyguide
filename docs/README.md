# CyGuide Documentation Hub

Welcome to the CyGuide documentation portal. CyGuide is an open-source Terminal User Interface (TUI) platform for cybersecurity education, tool orchestration, and stateful reconnaissance analysis.

Our documentation is structured according to the **[Diátaxis Framework](https://diataxis.fr/)**, dividing technical information into four distinct modes: **Tutorials**, **How-To Guides**, **Reference**, and **Explanation**.

---

## Documentation Navigation

```text
                                  PRACTICAL
                                     ▲
                                     │
           Tutorials                 │             How-To Guides
     (Learning-Oriented)             │          (Problem-Oriented)
  "Show me how to get started"       │      "Show me how to solve a task"
                                     │
 ────────────────────────────────────┼────────────────────────────────────
                                     │
             Explanation             │               Reference
     (Understanding-Oriented)        │         (Information-Oriented)
   "Help me understand how it works" │     "Give me the technical specs"
                                     │
                                     ▼
                                THEORETICAL
```

---

### 1. Tutorials (Learning-Oriented)
Step-by-step lessons designed to take you through your first successful investigation:

* **[Quickstart & First Reconnaissance](user/USER_MANUAL.md#1-getting-started--the-dashboard)**: Launch CyGuide, initialize a workspace, and discover your first target host and open services.
* **[Guided Learning Mode](user/USER_MANUAL.md#3-learning-mode-guided-cybersecurity-curriculum)**: Work through curated security tool recipes, inspect flag breakdowns, receive real-time AI tutor explanations, save multi-tool lab checkpoints (`.cyglab`), and export lab notes to Markdown.

---

### 2. How-To Guides (Task-Oriented)
Practical recipes for accomplishing specific operational goals:

* **[Multi-Distribution Installation](README.md#installing-security-tools--dependencies)**: Automated and native package manager installation across Debian/Ubuntu, Kali, Arch, Fedora/RHEL, openSUSE, Alpine, Void, and macOS.
* **[Configuring Local AI with Ollama](user/USER_MANUAL.md#the-command-palette-ctrlp--in-app-configuration)**: Connect CyGuide to local, privacy-preserving LLMs (e.g., Llama 3, Gemma, Mistral).
* **[Multi-Provider Cloud AI Setup](user/USER_MANUAL.md#the-command-palette-ctrlp--in-app-configuration)**: Configure OpenAI, Anthropic, Gemini, DeepSeek, or Groq with automatic failover.
* **[Exporting & Importing Investigations](user/USER_MANUAL.md#session-portability--reporting)**: Archive standalone `.db` graphs for CTF assignment submissions or peer reviews.
* **[Academic & Classroom Lab Guide](user/ACADEMIC_LAB_GUIDE.md)**: Verifiable methodology grading, student assignment workflows, and privacy-preserving local AI tutoring for university professors.
* **[Writing a Custom Security Tool Adapter](user/CONTRIBUTING.md#2-anatomy-of-a-tool-plugin)**: Create a new pluggable adapter using the Smart Adapter / Stupid Framework pattern.
* **[Developer Standards & Pre-Commit Setup](user/CONTRIBUTING.md#7-code-standards--developer-ergonomics)**: Ruff linting, pre-commit git hooks, and Conventional Commits workflow.

---

### 3. Reference (Information-Oriented)
Authoritative technical specifications and catalogues:

* **[Architecture & Domain Glossary](GLOSSARY.md)**: Comprehensive definitions of core platform terms (PIK, Smart Adapter, Entity Graph, Action Gateway, Forensic Archiving).
* **[Master Keyboard Shortcuts & Hotkeys](user/USER_MANUAL.md#master-keyboard-shortcuts--hotkeys-quick-reference)**: Comprehensive lookup table for all global, dashboard, learning mode, and operator hotkeys.
* **[CLI Commands & Diagnostics](user/USER_MANUAL.md#6-cli-commands--diagnostics)**: Complete reference for `cyg doctor`, `cyg session`, `cyg workspace`, `cyg tool`, and `cyg lab`.
* **[Standard Schema Registry](developer/SCHEMA_REGISTRY.md)**: Specifications for the standardized finding schemas (hosts, services, endpoints, credentials, vulnerabilities) and Primary Identity Keys (PIKs).
* **[Database Architecture & Relational DDL](developer/DATABASE.md)**: Full SQLite schema, index specifications, ER diagrams, and portability mechanisms.
* **[Security Vulnerability Policy](../.github/SECURITY.md)**: Supported versions, private reporting channels, response SLAs, and threat model boundaries.



---

### 4. Explanation (Understanding-Oriented)
In-depth discussions of system architecture, design decisions, and threat models:

* **[System Architecture Blueprint](developer/ARCHITECTURE.md)**: Architectural Decision Records (ADRs), decoupled subsystem design, and dataflow pipelines.
* **[Database Architecture & Relational DDL](developer/DATABASE.md)**: Full SQLite schema, index specifications, ER diagrams, and portability mechanisms.
* **[Master Project Roadmap & Milestones](developer/ROADMAP.md)**: Architectural progression, deliverable capabilities, and future autonomous agent roadmap.

---

## Reading Paths by Role

### For Students & CTF Competitors
1. Read the **[User Manual](user/USER_MANUAL.md)** to learn how to navigate the TUI.
2. Launch `cyg` and practice in **Learning Mode** to understand command flags and scan outputs.
3. Switch to **Power Mode** during live CTFs to track network discovery live in the entity graph without messy terminal tabs.
4. Export your session using `cyg session export <session_id> session.db -r report.md` (or save multi-tool lab checkpoint `cyg lab save <name>`) to submit your challenge writeup.

### For Instructors & Evaluators
1. Install CyGuide via Docker or package manager ([Installation Guide](README.md#installing-security-tools--dependencies)).
2. Have students submit standalone `.db` archives generated via `cyg session export` or `.cyglab` checkpoints.
3. Use `cyg session import <archive.db>` or `cyg lab load <file.cyglab>` to import student submissions into your local CyGuide instance.
4. Review the student's exact chronological execution timeline, discovered findings, and command history in the TUI.

### For Security Analysts & Penetration Testers
1. Deploy CyGuide via Docker (`docker run -it --rm --net=host -v ~/.cyguide:/root/.cyguide ghcr.io/h45sh/cyguide`).
2. Utilize **Power Mode** (`Enter`) for parallel scanning with universal variable substitution (`$TARGET`, `$PORT`).
3. Use `Ctrl+G` to merge findings across multiple subnets and targets into a unified workspace-wide attack graph.
4. Press `Ctrl+E` to generate instant technical and executive Markdown reports.

### For Tool Developers & Plugin Authors
1. Read **[Contributing Guide](user/CONTRIBUTING.md)** and understand the Smart Adapter contract.
2. Inspect the **[Schema Registry](developer/SCHEMA_REGISTRY.md)** to select the right finding models for your tool.
3. Review **[System Architecture](developer/ARCHITECTURE.md)** and **[Database Specification](developer/DATABASE.md)**.
4. Verify changes locally by running `./scripts/verify.sh`.

---

## Author & Project Ownership

**CyGuide** is an open-source cybersecurity platform created, architected, and maintained by **Harshwardhan Patil ([@h45sh](https://github.com/h45sh))**.

* **Website**: [h45sh.com/portfolio/cyguide](https://h45sh.com/portfolio/cyguide/)
* **Maintainer Inquiries**: [harshwardhan@h45sh.com](mailto:harshwardhan@h45sh.com)

