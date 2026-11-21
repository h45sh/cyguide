# Changelog

All notable changes to the CyGuide project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Unified Algorithmic Deep Module**: Bitwise Patricia Radix Trie (`IPRadixTrie`) for $\mathcal{O}(W)$ longest-prefix matching, Disjoint-Set Union (`DisjointSet`), MinHash locality-sensitive hashing, dynamic programming 0/1 Knapsack token optimizer (`knapsack_01`), and probabilistic query filter (`BloomFilter`) consolidated in `cyguide.common.algorithms`.
- **Graph Intelligence Engine**: In-memory graph analytics engine (`GraphAnalyticsEngine`) computing Brandes betweenness centrality for choke-point detection, Tarjan's strongly connected components (SCC) for cyclic attack loops, shortest attack path traversals, and blast-radius compromise calculations.
- **Headless CLI 2.0 (`cyg`)**: Fully decoupled POSIX command architecture with domain subcommands (`workspace`, `session`, `tool`, `lab`, `doctor`) supporting rich terminal formatting and universal `--json` serialization for automated pipelines.
- **Embedded Mock Practice Server**: Local loopback web server (`cyg lab start`) and `.cyglab` universal checkpoint archives for hermetic, verifiable offline training exercises.
- **Streamlined Test Architecture**: Universal adapter fuzzing, AST architectural layer DAG guards, and property-based mathematical verification suites.

---

## [1.0.0] - Initial Platform Release

### Added
- **Dual-Mode Terminal User Interface**: Interactive operator workbench (Power Mode) and pedagogical curriculum explorer (Learning Mode) built on Textual and Rich.
- **Pluggable Security Tool Ecosystem**: Dynamic plugin discovery and line-by-line streaming parsers for 11 security tools: `nmap`, `gobuster`, `nikto`, `whois`, `subfinder`, `nuclei`, `ffuf`, `searchsploit`, `sqlmap`, `netexec`, and `dnspython`.
- **Stateful SQLite Findings Graph**: Persistent relational entity graph (`GraphStore`) tracking hosts, services, endpoints, vulnerabilities, and credentials with deterministic Primary Identity Keys (PIK).
- **Subprocess Security & SSRF Defense**: Subprocess environment scrubbing stripping cloud and API credentials, strict link-local and cloud metadata IP/DNS blocking, and declarative CIDR scope enforcement.
- **Session Portability & Forensic Reporting**: Atomic zero-copy session export and import via SQLite `ATTACH DATABASE`, standalone `.cyglab` checkpoints, and automated Markdown report generation.
- **Multi-Provider AI Mentoring**: Local offline Ollama integration alongside cloud AI providers (OpenAI, Anthropic, Gemini, DeepSeek, Groq) with prompt boundary sanitization and token budget caps.
