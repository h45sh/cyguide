# Project Credits & Leadership

## Harshwardhan Patil — Project Lead, Architect & Founding Engineer

**Role:** System architect, primary implementer of Stage 1, and technical decision maker.

---

### 🏛️ Founding Contributions (Stages 1-3)

**Architectural Ownership**
- **Legacy Evolution**: Led the transition from initial proposal and legacy monolithic scripts(Phase 3) to the Stage 1 modular platform.
- **Smart Adapter Model**: Designed the "Smart Adapter / Stupid Framework" boundary to ensure the platform remains extensible and tool-agnostic.
- **Entity Graph & PIK**: Authored the Primary Identity Key (PIK) upsert logic and the dual-store SQLite model (Stateful Graph + Event Log).
- **Reactive Engine**: Designed the store-watching reactivity model that decouples the engine from the TUI.

**Core Implementation**
- **Engine**: Built the `GraphStore`, `Executor` async pipeline, and `ToolRegistry` discovery logic.
- **Schema Library**: Designed and implemented the full 15-schema Pydantic vocabulary for cybersecurity findings.
- **TUI Framework**: Developed the core Textual application shell, including the Learning Mode and Power Mode orchestrators.
- **Verification**: Established the project's testing standards and authored the 27-test automated verification suite.

---

### 🤝 Future Contributors

CyGuide is built to be an extensible ecosystem. We welcome contributions in the following areas:

**Tool Adapters (Tier 3)**
- Implementation of new tool adapters in `tools/` (e.g., Nikto, Gobuster, Ffuf).
- Enhancing existing adapters with more granular milestone triggers.

**User Interface & UX (Tier 3)**
- Development of new Textual widgets for the Dashboard.
- Styling and accessibility improvements in `ui/style.css`.

**Community Schemas (Tier 2)**
- Proposals for new finding schemas to expand the platform's vocabulary.
