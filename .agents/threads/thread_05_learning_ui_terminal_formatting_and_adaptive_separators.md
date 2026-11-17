# Thread Insight: Terminal Stream Styling, LLM Output Normalization & Adaptive Separator Architecture

- **Branch / PR**: `feat/api-guardrails-and-tool-intelligence` (PR #30)
- **Primary Domain**: `[UI | Engine | AI / LLM | Benchmarks]`
- **Author / Contributor**: `@h45sh`

---

## 1. Key Principles & Architectural Techniques Introduced

### 1.1. Native ANSI Prompt Architecture in Terminal Streams
- **Separated Multi-Line Prompt**: Replaced naive horizontal double-line separator boxes (`═` * 65) with an authentic Linux shell prompt architecture:
  ```
  ┌─[run #1]─[05:40:47]
  └─> nmap -sV 127.0.0.1
  ```
- **Direct ANSI Stream Rendering**: Emitted raw 8-bit ANSI SGR escape sequences directly in `cyguide/engine/learning.py` (`\x1b[90m` frame borders, `\x1b[1;36m` cyan run badge, `\x1b[33m` yellow timestamp, `\x1b[1;32m` green prompt `>` symbol, and `\x1b[1;37m` bold white command string).
- **Zero Rich Markup Overhead**: By emitting raw ANSI directly into `TerminalStreamPane` (which parses via `rich.text.Text.from_ansi`), we eliminated all square-bracket Rich markup escaping hazards (`[run #1]` would otherwise be misparsed as an unrecognized Rich style tag or BBCode token).

### 1.2. Adaptive Markdown Horizontal Rules (`CyGuideHorizontalRule` & `CyGuideMarkdown`)
- **Semantic Tiering of Horizontal Dividers**:
  - LLM debriefings naturally use `---` (CommonMark thematic break) to separate intra-explanation sections (`### Quick Summary`, `### Discovered Findings`, `### Flags Breakdown`).
  - Major session events (new scan executions and user follow-up questions) also need visual boundaries.
- **The Solution**: Subclassed `rich.markdown.HorizontalRule` and `rich.markdown.Markdown` to inspect token markup semantics:
  - **Major Boundaries (`***`)**: Rendered as a prominent **Electric Blue Double Line (`═`)** (`bold #38bdf8`) separating distinct runs and questions.
  - **Minor Boundaries (`---`)**: Rendered as a subtle, muted single hairline (`─`) (`dim #334155`) for internal section dividers.
- **Zero DOM Widget Hierarchy Churn**: Retained single-widget `Static` rendering with zero sub-widget lifecycle churn, preserving O(1) rendering time regardless of buffer length.

### 1.3. LLM Markdown Heading Normalization
- **Defensive Parsing in `render_markdown()`**: LLMs frequently wrap Markdown headings in bold asterisks when following structured prompt schemas (e.g. `**### Quick Summary**`).
- **The Issue**: CommonMark and `rich.markdown` require `#` to be the first non-whitespace character on the line to parse as a `heading_open` AST node. Asterisk wrapping causes the entire header to degrade into a plain paragraph with unparsed hash symbols.
- **The Seam**: Pre-processes raw LLM text buffers via regex `re.sub(r"^\s*\*\*(#{1,6}\s+.*?)\*\*\s*$", r"\1", text, flags=re.MULTILINE)` prior to AST construction, transparently normalizing malformed headings without corrupting legitimate inline bold text.

---

## 2. Non-Obvious Insights & Codebase Realities

### 2.1. Dynamic Console Width vs Hardcoded String Multiplications
- **The Trap**: Formatting separators by multiplying characters (`"=" * 80` or `"─" * console.width`) produces catastrophic line wrapping when users resize terminal panes, toggle the sidebar (<kbd>Ctrl+B</kbd>), or shrink the window below 80 columns.
- **The Reality**: Always yield `rich.rule.Rule(characters="═", style="bold #38bdf8")` inside a custom `MarkdownElement.__rich_console__`. Rich calculates the exact viewport column boundaries dynamically on every paint cycle without emitting superfluous newline wraps.

### 2.2. Multi-Tenant Virtualized Runner Jitter in Pytest Benchmarks
- **The Trap**: The `test_graphstore_scale_and_query_limits` test asserted `edges_elapsed < 250.0ms` for 2,500 edges across 5,000 nodes. On bare-metal local development, this consistently finishes in 15–30ms.
- **The Reality**: On shared GitHub Actions Ubuntu runners under high virtualization load, context switching and hypervisor scheduling jitter spiked query times to `255.5ms`, triggering transient CI test failures.
- **Contract Rule**: Align benchmark assertions with algorithmic regression boundaries ($O(N)$ vs $O(N^2)$) rather than sub-millisecond local machine tolerances. Setting the threshold to `< 500.0ms` maintains strict protection against regression while absorbing multi-tenant hypervisor variance.

### 2.3. Asynchronous Screen Mount and Tab Switch Settling
- **The Trap**: Calling `tabs.active = "tab_explanation"` or simulating button presses followed by an instantaneous single-frame `await pilot.pause()` intermittently failed assertions on macOS CI runners (`assert 'tab_recipes' == 'tab_explanation'`).
- **The Reality**: Textual tab switching schedules reactive event dispatches across widget hierarchies. Integration tests driving simulated UI interactions must provide bounded settlement periods (`await pilot.pause(0.2)`) to allow the internal Textual message pump to complete DOM state updates.

---

## 3. Anti-Patterns & Outdated Techniques (What NOT to do)

1. **NEVER Style Global Separators with Universal Hardcoded Markdown Rules**:
   - Styling all `---` occurrences as high-visibility colored double rules makes individual scan explanations look fragmented into multiple disjointed runs.
   - Always reserve high-contrast double lines (`═`) for true inter-session/inter-run boundaries (`***`) and keep intra-explanation section dividers subtle (`─`).
2. **NEVER Inject Raw Terminal Escape Codes into Rich-Marked Strings**:
   - Mixing Rich BBCode markup (`[bold cyan]...[/]`) with ANSI escapes (`\x1b[32m...`) inside the same stream leads to parser state corruption in Rich's text formatter.
   - Use either 100% ANSI escapes parsed via `Text.from_ansi()` or 100% Rich markup, never an ad-hoc hybrid.
3. **NEVER Emit Raw Unformatted Debug Fallbacks into User Explanations**:
   - Direct output of raw bracketed logs like `[Notice: Ollama connection failed (...). Falling back...]` creates an unpolished UI appearance.
   - Always wrap operational fallbacks and warnings in clean Markdown blockquotes: `> 💡 Notice: Local Ollama unavailable (connection failed). Falling back to Cloud AI...`.
4. **NEVER Rely on Immediate Synchronous Assertions After ListView or Tab Changes**:
   - Never assert `ws_list.index` or `tabs.active` immediately after mutating them. Always await debouncing routines (`await settle_d()` or `await pilot.pause(0.1-0.2)`) before asserting widget selection state.

---

## 4. Invariants & Performance Contracts to Preserve

| Component | Target Contract | Hard Invariant |
| :--- | :--- | :--- |
| **Explanation Stream Rendering** | Zero widget churn ($O(1)$ memory overhead) | Render entire explanation as a single `Static` widget via `render_markdown()`; never mount nested per-paragraph DOM widgets. |
| **Terminal Box Formatting** | Multi-line clean prompt on separate rows | `┌─[run #N]─[timestamp]` followed on next line by `└─> <command>` and stdout immediately on line 3. |
| **Dynamic Viewport Responsiveness** | No horizontal character wrap on resize | Rules must inherit from `rich.rule.Rule` or `RichHorizontalRule`; no hardcoded string repeating (`"═" * 80`). |
| **GraphStore Bulk Edge Query** | 2,500 edges queried in $\le 500\text{ms}$ | Fully indexed SQLite schema; parameter-bound queries; stable under CI virtualization. |
| **Workspace Switch Settling** | Instantaneous reactive debouncing | Debounce timers must be bounded ($\le 50\text{ms}$); tests must await debounce task completion (`settle_d()`). |
