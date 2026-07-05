# CyGuide Project Roadmap

## ✅ Phase 1: Core Foundation (Completed)
- **Engine Architecture**: Implemented Smart-Adapter model, Reactive Graph Store (PIK-Upsert), and Async Executor.
- **TUI Framework**: Built the Textual shell with Dashboard, Learning Mode, and the **Power Mode Advanced Operator Workspace Foundations**.
- **Schema Vocabulary**: Developed a 15-schema Pydantic library with auto-generated registry and linter.
- **Project Governance**: Established tiered protection policy, MIT License, and 27-test verification suite.
- **Production Hardening**: Implemented configurable storage (`data/` isolation), plugin diagnostics (UI-surfaced), absolute tool discovery (fixing `cyg` execution from any directory), and modernized packaging (`pyproject.toml`).

## 🚀 Phase 2: Intelligence & Expansion (Current)

### **Priority 1: The "Intelligence" (Explainer Backends)**
- [x] **Ollama Integration**: Implemented `OllamaBackend` and wired it to the CLI/TUI via `--ollama` (default: gemma).
- [ ] **Anthropic Integration**: Implement cloud-based explanations for high-fidelity guidance (Opt-in).

### **Priority 2: The "Curriculum" (Tool Expansion)**
- [ ] **Web Discovery**: Implement `gobuster` or `ffuf` adapter for directory brute-forcing.
- [ ] **Vuln Scanning**: Implement `nikto` adapter for standard web vulnerability detection.
- [ ] **DNS Analysis**: Implement `subfinder` or `dig` adapter for attack surface mapping.

### **Priority 3: Strategic Logic (Guided Mentorship)**
- [ ] **Recommendation Engine**: Implement declarative filters to suggest tools based on findings (e.g., if port 80/443 found -> suggest gobuster).
- [ ] **Milestone Expansion**: Add rich educational content for new tools in `manifest.toml`.

## 🛠️ Phase 3: Polish & Delivery (Planned)

### **Automation & CI**
- [ ] **GitHub Actions**: Automated schema linting and multi-platform testing on push.
- [ ] **Diagnostic CLI**: Add a `cyg check` command to verify local environment dependencies (nmap, etc.).

### **Session Portability**
- [ ] **Export/Import**: Create a mechanism to export a session (`.db` + logs) for collaborative review or grading.
- [ ] **Markdown Reporting**: Automatically generate a professional summary of findings in Markdown format.

### **Final Polish**
- [ ] **User Manual**: Author a comprehensive guide for adding new adapters and using the TUI.
- [ ] **UI Responsiveness**: Final audit for terminal resizing edge cases and high-latency LLM streaming.
