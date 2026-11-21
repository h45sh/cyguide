# CyGuide Architecture & Domain Glossary

This glossary defines the authoritative terminology, domain concepts, and architectural patterns used across the CyGuide codebase and documentation.

---

## Core System Concepts

### Smart Adapter / Dumb Framework
An architectural design pattern where all tool-specific logic (command flag assembly, binary path discovery, and stdout/stderr parsing) is strictly encapsulated inside pluggable adapters (`tools/<name>/adapter.py`). The core platform (the "dumb framework") remains completely agnostic of individual security tools; it only processes standardized `BaseFinding` schemas, manages asynchronous process lifecycles, and maintains the relational entity graph.

### Primary Identity Key (PIK)
A deterministic SHA-256 hash uniquely identifying a security finding based on its normalized semantic attributes (e.g., `ip_address`, `port_number`, `normalized_url`). PIKs ensure idempotent upserts into `GraphStore`: repeated scans update existing nodes rather than cluttering the database with duplicate entities.

### Entity Graph
A persistent SQLite-backed directed graph that models an engagement's attack surface. Nodes represent normalized cybersecurity entities (`network.host`, `network.service`, `web.endpoint`, `vulnerability.found`, `credential.found`), while directional edges model relationships (e.g., `host -> service`, `service -> vulnerability`).

### Contextual Variable Injection
The dynamic resolution and substitution of runtime environment tokens (`$TARGET`, `$PORT`, `$SERVICE`, `$URL`) into command inputs. When an operator selects any node in the workbench entity tree, these variables automatically bind to the active node's attributes, eliminating repetitive manual argument entry.

---

## Execution & Security Engine

### Action Gateway (`ActionGateway`)
The central policy enforcer and security gate for all system invocations. The gateway validates target scope (CIDR boundaries), enforces non-shell binary whitelisting, prevents Link-Local and cloud metadata SSRF attacks (`169.254.0.0/16`, IMDSv2), and prevents unprivileged automated agents from executing raw shell commands.

### Execution Session (`ExecutionSession`)
An asynchronous process orchestrator managing subprocess lifecycles. It connects subprocess `stdout` and `stderr` streams, spools output to disk in 64KB chunks (`LogSpooler`), micro-batches terminal UI renders at 20–30 FPS, and handles two-phase privileged execution (targeted `sudo -v` terminal suspension for credentials, followed by foreground live output streaming into tabs).

### Pre-flight Verification (`PreflightVerifier`)
A zero-side-effect validation subsystem that inspects execution prerequisites prior to process launch: discovers binaries on system `$PATH`, verifies wordlist files and macro expansions, resolves context variables, and enforces sandbox security boundaries (prohibiting unauthorized `sudo` and cloud metadata SSRF targets). Paired with `PreflightModal` to surface instant, one-click remediation guidance.

### Subprocess Environment Scrubbing (`sanitize_subprocess_env`)
A security control that strips all sensitive host environment variables (including `CYGUIDE_*`, `OPENAI_*`, `ANTHROPIC_*`, `AWS_*`, `GITHUB_*`, and `SSH_PRIVATE_KEY`) before spawning child security tools, ensuring external binaries cannot inspect `/proc/<PID>/environ` to harvest operator credentials.

### Untrusted Output Sandboxing
A prompt-injection defense mechanism in `ExplanationTutor` where raw, unverified target scanner outputs are encapsulated inside `<untrusted_scan_output tool="...">` XML boundaries, with closing-tag sanitization and automated redaction of sensitive credentials (PEM keys, bearer tokens, passwords) before dispatch to language models.

---

## Storage & Lab Workflows

### Forensic Session Archiving
A state-governed lifecycle model (`ACTIVE` vs `CLOSED`). When an operator closes a session, the workspace facade activates read-only guards (`PermissionError`), freezing findings and command history to preserve evidentiary integrity while remaining fully navigable and exportable.

### Standalone Session Archive (`cyg session export` / `cyg session import`)
An atomic SQLite database export mechanism (`ATTACH DATABASE`) that bundles the entire entity graph, edge relationships, and execution logs into a self-contained `.db` file. Instructors and evaluators can import this archive into any local CyGuide instance to inspect a student's exact chronological methodology and scan findings.

### Universal Lab Checkpoint (`.cyglab`)
A self-contained SQLite archive created in Learning Mode (`Ctrl+S` / `⤓ SAVE`) that serializes full multi-tool laboratory progression. It records all discovered entity graph nodes/edges across all tools, per-tool configuration caches (`tool_configs`), cumulative terminal stdout lines, AI tutor dialogues, and student notes, secured with atomic `0o600` private file permissions.

### Wordlist Subsystem
A centralized asset repository located at `~/.cyguide/wordlists/` (or `$CYGUIDE_DATA_DIR/wordlists`). It bundles high-signal starter wordlists and dynamically expands named macros (`{wordlist:common_dirs}`) inside tool recipes.
