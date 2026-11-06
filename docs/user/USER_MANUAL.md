# CyGuide User Manual

Welcome to CyGuide! This manual outlines the core workflows, complete keyboard shortcuts/hotkeys reference, and UI features for managing your cybersecurity investigations and learning journeys.

---

## ⚡ Master Keyboard Shortcuts & Hotkeys Quick Reference

| Context / Screen | Shortcut | Action |
| :--- | :--- | :--- |
| **Global / Help** | `F1` / `Ctrl+/` | Open Keyboard Shortcuts & Hotkeys Help dialog |
| **Global** | `Ctrl+P` | Open Textual Command Palette (`Configuration`, `Tool Health`, `Themes`, etc.) |
| **Global** | `Ctrl+Shift+C` | Open Full CyGuide Configuration Panel modal (`⚙`) |
| **Global** | `Q` / `Ctrl+Q` | Quit Application (Dashboard, Tool Browser, Lesson, Expanded Output) |
| **Dashboard** | `F1` / `Ctrl+/` | Show Keyboard Shortcuts & Hotkeys Help dialog |
| **Dashboard** | `Ctrl+N` | Create a New Workspace (Project) |
| **Dashboard** | `Ctrl+S` | Create a New Session in active Workspace |
| **Dashboard** | `Ctrl+A` | Archive / Reopen highlighted Workspace or Session |
| **Dashboard** | `F2` | Rename highlighted Workspace or Session inline |
| **Dashboard** | `Ctrl+B` | Toggle/collapse left Workspace sidebar |
| **Dashboard** | `Ctrl+L` | Switch to Learning Mode (Tool Browser) |
| **Dashboard** | `Ctrl+D` | Toggle Delete Mode / Confirm deletion |
| **Dashboard** | `Ctrl+M` | Toggle Organize (Move) Mode / Advance step & Confirm Move |
| **Dashboard** | `Space` | Toggle item selection (in Delete and Organize modes) |
| **Dashboard** | `Escape` | Cancel Delete or Organize Mode |
| **Dashboard** | `Enter` / Click | Open workspace details or launch Power Mode for highlighted session |
| **Dashboard** | `Up` / `Down` | Navigate list items (Workspaces, Sessions, Activity, Diagnostics) |
| **Power Mode** | `F1` / `Ctrl+/` | Show Keyboard Shortcuts & Hotkeys Help dialog |
| **Power Mode** | `Ctrl+T` | Open a new blank terminal tab |
| **Power Mode** | `Ctrl+W` | Close active terminal tab (kills running task & marks closed) |
| **Power Mode** | `Ctrl+K` | Kill / terminate running background job in active tab (`SIGTERM`) |
| **Power Mode** | `Ctrl+PageUp` | Switch to previous workbench tab |
| **Power Mode** | `Ctrl+PageDown` | Switch to next workbench tab |
| **Power Mode** | `Shift+Enter` / `Alt+Enter` / `Ctrl+J` | Execute command in a brand new terminal tab |
| **Power Mode** | `Ctrl+Tab` / `Ctrl+Right` | Switch to next Session in current workspace |
| **Power Mode** | `Ctrl+Shift+Tab` / `Ctrl+Left` | Switch to previous Session in current workspace |
| **Power Mode** | `Ctrl+B` | Toggle sidebar (collapse/expand Entity Browser, Job Queue, Suggestions) |
| **Power Mode** | `Ctrl+N` | Toggle Note-Taking Scratchpad (`~/.cyguide/scratchpad.md`) |
| **Power Mode** | `Ctrl+G` | Toggle Global Entity Graph (Session-scoped vs Workspace-wide view) |
| **Power Mode** | `Ctrl+E` | Export session findings (SQLite DB archive & Markdown report) |
| **Power Mode** | `Ctrl+L` | Toggle Raw Shell Lock (locks prompt in raw shell mode `!`) |
| **Power Mode** | `?` or `help` | Show in-app Keyboard Shortcuts & Hotkeys dialog modal |
| **Power Mode** | `Escape` | Exit Power Mode and return to Dashboard |
| **Power Mode Prompt** | `!` prefix | One-time raw shell command execution (bypasses tool parser) |
| **Power Mode Prompt** | `> !` or `! !` | Quick toggle between Tool Mode (`>`) and Shell Mode (`!`) |
| **Power Mode Prompt** | `Tab` | Filename auto-completion for CWD (when in Shell-Locked mode) |
| **Power Mode Prompt** | `Up` / `Down` | Navigate command execution history |
| **Power Mode Suggestions** | `Enter` / Click | Approve recommendation (pre-populates command prompt) |
| **Power Mode Suggestions** | `d` / `x` / `Delete` | Dismiss recommendation (removes from suggestions and database) |
| **Power Mode Tree** | Click / Highlight | Select entity node to inject variables (`$TARGET`, `$PORT`, `$SERVICE`) |
| **Power Mode Jobs** | Click / Select | Switch to job's terminal tab (seamlessly swaps active session if needed) |
| **Learning: Tool Browser** | `F1` / `Ctrl+/` | Show Keyboard Shortcuts & Hotkeys Help dialog |
| **Learning: Tool Browser** | Type in Search | Real-time search filter for tools, recipes, and flags |
| **Learning: Tool Browser** | `Up` / `Down` | Navigate categorized tool list |
| **Learning: Tool Browser** | `Enter` / Click | Select tool to open Lesson Screen |
| **Learning: Tool Browser** | `Escape` | Return to Dashboard |
| **Learning: Tool Browser** | `Q` / `Ctrl+Q` | Quit Application |
| **Learning: Lesson Screen** | `F1` / `Ctrl+/` | Show Keyboard Shortcuts & Hotkeys Help dialog |
| **Learning: Lesson Screen** | `Ctrl+B` | Toggle Lesson configuration sidebar |
| **Learning: Lesson Screen** | `Enter` on Recipe | Pre-populate flags and command preview from recipe |
| **Learning: Lesson Screen** | `Enter` in Chat | Submit question to AI cybersecurity tutor |
| **Learning: Lesson Screen** | `Escape` | Return to Tool Browser |
| **Learning: Lesson Screen** | `Q` / `Ctrl+Q` | Quit Application |
| **Expanded Output Modal** | `Escape` | Close expanded output screen and return to Lesson Screen |
| **Expanded Output Modal** | `Q` / `Ctrl+Q` | Quit Application |
| **Shortcuts Help Modal** | `Esc` / `F1` / `Ctrl+/` / `Q` | Close the Shortcuts Help dialog modal |

---

## 1. Dashboard: Engagement Management
The Dashboard is the central hub where you manage your engagements. Data is strictly isolated into **Workspaces** (Projects) and **Sessions** (Point-in-time investigations).

### Dashboard Shortcuts
- `F1` / `Ctrl+/`: Show the Keyboard Shortcuts & Hotkeys Help dialog
- `Ctrl+N`: Create a New Workspace (on Dashboard)
- `Ctrl+S`: Create a New Session in the currently selected workspace
- `F2`: Rename the currently highlighted Workspace or Session inline
- `Ctrl+B`: Toggle the left Workspace sidebar
- `Ctrl+L`: Switch to Learning Mode (on Dashboard)
- `Ctrl+D`: Toggle Delete Mode / Confirm Deletion
- `Ctrl+M`: Toggle Organize Mode / Advance Step & Confirm Move
- `Space`: Check/uncheck items during Delete or Organize modes
- `Escape`: Cancel Delete or Organize mode
- `Enter` / Click: Select a workspace or session, or click "ENTER POWER MODE"
- `Ctrl+P`: Open Command Palette (`Toggle Animations`, `Toggle Sidebar`, `Tool Health`, `Themes`)
- `Up` / `Down`: Navigate list items across Workspaces, Sessions, Recent Activity, and Tool Health
- `Q` / `Ctrl+Q`: Quit application

### Organizing & Deleting Data
- **Rename Data**: Use the arrow keys to highlight any Workspace or Session and press `F2`. A prompt will appear allowing you to rename it instantly. Workspace names are validated for global uniqueness, and session names are validated within their workspace (both case-insensitively). Conflicting renames will trigger a notification badge.
- **Organize (Move) Sessions**: Press `Ctrl+M` to enter Organize Mode. Use `Space` to check off one or more sessions. Press `Ctrl+M` to proceed to Step 2, highlight the destination Workspace, and press `Ctrl+M` to confirm the move. Session names must remain unique in the destination workspace.
- **Delete Data**: Press `Ctrl+D` to enter Delete Mode. Check off items with `Space`, then press `Ctrl+D` to confirm deletion. Data is natively cascaded and wiped from the SQLite database. Any active background executor tasks associated with deleted sessions or workspaces are automatically terminated to prevent resource leaks.
- **Archive / Reopen Sessions (`Ctrl+A`)**: Press `Ctrl+A` on any active session to archive it. Archived sessions are protected against accidental scan mutations with strict read-only execution guards while preserving forensic logs and graph state. Press `Ctrl+A` again to reopen an archived session to active status.
- **Session Details**: Highlights metadata like `Active Jobs` (live background tasks) and `Closed Tabs` (persisted count of closed tabs/scans).

### The Command Palette (`Ctrl+P`) & In-App Configuration
Press `Ctrl+P` from anywhere in the application to summon the Textual Command Palette with unified navigation:
- **`⚙ Open Full Configuration Panel`** (`Ctrl+Shift+C`): Opens the comprehensive in-app settings dialog with 4 dedicated tabs:
  - **Local LLM (Ollama)**: Enable/disable local inference, configure model name (e.g., `gemma`, `llama3`), set custom base URL, and run an instant connectivity probe.
  - **Cloud AI & Multi-Key Profiles**: Manage multiple cloud API keys (OpenAI, Anthropic Claude, Groq, OpenRouter, DeepSeek, Gemini). Add custom profiles, set active keys, enable automatic fallback chains, and test endpoints directly.
  - **Database Settings**: Configure custom SQLite database locations (`--db`) or verify the unified database path.
  - **Custom Tools**: Set external plugin directories (`--tools`) to load custom security adapters without modifying the engine.
- **`Toggle Animations`**: Instantly toggle terminal UI animations on (`● ON`) or off (`○ OFF`). Your preference is automatically persisted to local settings.
- **`Toggle Sidebar`**: Expand or collapse the navigation sidebar (`● EXPANDED` / `○ COLLAPSED`) to maximize workbench real estate.
- **`Tool Health`**: Shows a live health badge (`● Healthy (5/5)` or `▲ Issues`). Selecting it opens the dedicated **Tool Health Modal**:
  - Displays real-time discovery, binary filesystem paths (e.g. `/usr/bin/nmap`), and installation status for all security plugins (`nmap`, `gobuster`, `nikto`, `subfinder`, `whois`).
  - Provides actionable OS-specific package manager installation hints (APT, Brew, Go) for any missing binaries.
  - Press `Left Arrow` (`← Left: Back`) or `Esc` to dismiss and return directly to the Command Palette.
- **`Search for themes…`**: Sub-palette to preview and switch between color themes (e.g. `cyguide-dark`, `monokai`, `nord`, `catppuccin`).
- **Sub-Menu Navigation**: Use `Right Arrow` to enter sub-menus (or trigger actions) and `Left Arrow` (`← Left: Back`) to return up a level. Highlighting memory ensures your position is preserved when returning.

---

## 2. Power Mode: Advanced Operator Workspace
Select a Session in the Dashboard and click "ENTER POWER MODE" (or press `Enter` on a session) to boot up the main terminal interface.

### Dynamic Split-Pane Edge Resizing
CyGuide features interactive split-pane resizing handles (`│`):
- Hover the mouse over the vertical border between the **Entity Browser** and the **Workbench Terminals**, or between the terminals and the **Suggestions sidebar**.
- Click and drag horizontally to smoothly expand or contract pane widths to your preference.
- Customized pane sizes are automatically saved to `~/.cyguide/settings.json` and persist across application restarts.

### The Entity Browser (Left Pane)
Displays a hierarchical physical tree of all entities (Targets -> Hosts -> Services -> Netblocks -> Domains & DNS -> Web -> Credentials -> Vulnerabilities) discovered during your investigation.
- **Global Graph Toggle** (`Ctrl+G`): By default, the tree strictly shows entities discovered in the *current session*. Press `Ctrl+G` to merge and deduplicate entities from *all sessions in the current workspace* into a unified workspace-wide view.
- **Variable Injection**: Click on or highlight any node in the Entity Browser to populate the context bar. You can now dynamically use variables like `$TARGET`, `$PORT`, and `$SERVICE` in your commands without retyping IPs.

### The Job Queue (Bottom Left)
Tracks the status of background tools (`RUNNING`, `DONE`, `FAILED`).
- **Global Visibility**: The queue intelligently monitors jobs running across *all sessions in your current workspace*.
- **Cross-Session Jump**: Clicking a job in the queue that belongs to a different session will seamlessly swap your active environment to that session so you can view its terminal output.

### The Suggestions Pane (Bottom Left)
Displays context-aware tool recommendations (`💡 [tool] ❯ [target]`) generated by the Recommendation Engine based on existing findings.
- **Approve Recommendation** (`Enter` or Click): Pre-populate the command prompt with the suggested command, allowing you to review/edit before running.
- **Dismiss Recommendation** (`d`, `x`, or `Delete`): Remove the recommendation from the suggestion list and database.

### The Scratchpad
- **Toggle Scratchpad** (`Ctrl+N` in Power Mode): Opens a docked markdown editor next to the job queue.
- Notes are continuously auto-saved to `~/.cyguide/scratchpad.md` in your unified CyGuide application folder (or custom data directory). Use this to quickly jot down target notes, syntax reminders, or investigation thoughts without leaving the terminal regardless of which folder CyGuide was run from.
- *Security Note*: Scratchpad contents are stored in plaintext on disk (`~/.cyguide/scratchpad.md` with mode `0600`). Do not store sensitive credentials or private keys in the scratchpad; utilize your system's protected secret storage instead.

### The Command Palette & Terminal Prompt
Located at the bottom of the screen, the prompt executes your commands.
- **Smart Tools (`[tool]`)**: Typing a registered tool (e.g., `nmap -sV $TARGET`) runs through CyGuide's adapter layer. The raw output streams to the terminal above, while the background parser automatically extracts findings into the Entity Graph.
- **Raw Shell (`[shell]`)**: Prefix any command with `!` (e.g., `!ping 127.0.0.1`), or press `Ctrl+L` in Power Mode to lock the prompt into Raw Shell mode. These commands bypass the parser entirely and execute directly on your OS.
- **Quick Mode Switching**: Typing `> !` switches from Tool Mode to Shell Mode (`! `). Typing `! !` switches back to Tool Mode (`> `).
- **Tab Completion**: When in Shell-Locked mode (`Ctrl+L`), pressing `Tab` triggers auto-completion for filenames and paths within your Current Working Directory (`pwd`).
- **Command History**: Press `Up` and `Down` arrow keys to cycle through previous command history.
- **New Tab Execution**: Press `Shift+Enter`, `Alt+Enter`, or `Ctrl+J` when submitting a command to force it to open and execute in a brand new terminal tab.
- **Built-in Terminal Commands**:
  - `F1` or `Ctrl+/` (or `?` / `help` in prompt): Open the in-app Keyboard Shortcuts & Hotkeys Help dialog modal.
  - `clear`: Clear the output buffer of the active terminal tab.
  - `cd <path>`: Change directory within the session context.
  - `sudo <command>`: Suspends the TUI for interactive sudo password entry in your login shell environment before resuming.

### Workbench Navigation Shortcuts
- `F1` / `Ctrl+/`: Open the Keyboard Shortcuts & Hotkeys Help dialog
- `Ctrl+T`: Open a new blank terminal tab
- `Ctrl+W`: Close the currently focused terminal tab. Closed tabs are marked closed in the database and do not reappear upon re-entering the session.
- `Ctrl+K`: Kill / terminate the currently focused background job (`SIGTERM`)
- `Ctrl+PageUp` / `Ctrl+PageDown`: Cycle horizontally through active workbench tabs
- `Ctrl+Tab` / `Ctrl+Shift+Tab` (or `Ctrl+Right` / `Ctrl+Left`): Cycle through your active Sessions in the workspace without returning to the Dashboard
- `Ctrl+E`: Export current session findings (SQLite DB to `exports/` and Markdown report to `reports/`)
- `Ctrl+B`: Toggle the sidebar to maximize terminal space
- `Esc`: Exit Power Mode and return to the Dashboard

---

## 3. Learning Mode: Guided Educational Sandbox
Learning Mode provides structured cybersecurity education through curated tool lessons, interactive recipes, and real-time AI tutor explanations.

### Phase 1: Tool Browser Screen
The entry hub for Learning Mode (accessed via `Ctrl+L` from the Dashboard):
- **Search Filtering**: Type directly into the search bar to filter tools, categories, recipes, and flags in real time.
- **Navigation**: Use `Up` / `Down` arrow keys to browse through categorized tools (e.g., Port Scanners, Web Fuzzers, OSINT, DNS).
- **Select Tool**: Press `Enter` or click on any tool item to launch its interactive Lesson Screen.
- **`Esc`**: Return to the Dashboard.
- **`Q` / `Ctrl+Q`**: Quit the application.

### Phase 2: Lesson Screen
An interactive learning interface for executing commands and receiving guided breakdowns:
- **Lesson Sidebar Toggle** (`Ctrl+B`): Collapse/expand the left lesson configuration pane.
- **Recipe Selection**: Use `Up` / `Down` and press `Enter` (or click) on a recipe to automatically populate the Flag Editor with optimized parameters and preview the generated command.
- **Flag & Target Editor**: Manually customize additional flags and target host/domain/URL with instant command preview updates.
- **Run & Stop Execution**: Click `▶ RUN` to execute the scan or `⏹ STOP` to terminate an active scan early.
- **Automated AI Explanations**: After scan completion, the AI tutor generates a structured Markdown breakdown featuring:
  - 🎯 Quick Summary of the target
  - 📊 Discovered Services & Findings table
  - ⚙️ Flags Breakdown table
  - 💡 Key Takeaways
  - 🚀 Next Recommended Commands
- **Interactive AI Tutor Chat**: Type questions into the chat prompt at the bottom right and press `Enter` to ask specific questions about the scan output and findings.
- **Output & Explanation Controls**:
  - `↕ EXPAND` / `↕ SHRINK`: Toggle between normal view and maximized view for either the Explanation pane or Raw Output pane.
  - `🗑️ CLEAR`: Clear the Explanation or Raw Output log buffer.
  - `📋 COPY`: Copy the entire Explanation markdown or Raw Output text to the system clipboard.
  - `⛶` (Expand Screen): Open the content in a full-screen scrollable modal (`ExpandedOutputScreen`).
- **Expanded Output Modal Shortcuts**:
  - `Esc`: Close the full-screen modal and return to the Lesson Screen.
  - `Q` / `Ctrl+Q`: Quit application.
- **`Esc`**: Return to the Tool Browser.
- **`Q` / `Ctrl+Q`**: Quit application.

---

## 4. CLI Subcommands & Diagnostics

CyGuide includes a powerful command-line interface for automation, verification, and session portability:

### Diagnostic Health Check (`cyg check`)
Verifies your local environment, database storage permissions, security tool installations, and AI backends:
```bash
cyg check
```
*   **JSON Output**: Use `cyg check --json` for scriptable health output and CI pipelines.
*   **Custom Database Check**: Use `cyg check --db <path>` to test a specific database location.

### Exporting Investigations (`cyg export`)
Exports a session's findings, relationships, and execution logs into a standalone `.db` file in `exports/` and an executive Markdown report in `reports/`:
```bash
cyg export <session_id> exports/my_session.db --report reports/my_session_report.md
```

#### Who are Exports & Reports For?
* **🎓 Instructors & Evaluators**: Students can export their lab/CTF session into an archive and submit it. Instructors can run `cyg import` to step through the student's exact methodology, commands, and discoveries in their own CyGuide TUI.
* **🤝 Security Teams & Collaborators**: Analysts and penetration testers can share specific engagement findings for peer review or shift handoffs without exposing their entire global database.
* **💾 Archiving & Engagement Backups**: Portable, lightweight snapshots of completed assessments that can be restored into CyGuide anytime on any machine.
* **📄 Executive & Client Reporting**: Automatically generated Markdown summaries (`reports/`) ready for presentation, documentation, and review.

### Importing Investigations (`cyg import`)
Imports a previously exported session `.db` into your local workspace:
```bash
cyg import exports/my_session.db [--workspace-id <target_workspace_id>]
```
