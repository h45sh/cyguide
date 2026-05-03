# EFD 04: Real-time Streaming & UI Architecture

As a new programmer, you've just seen a "frozen" application transformed into a "live" one. This document explains the techniques we used, why we chose them, and the common pitfalls we avoided.

---

## 1. The "Freezing" Problem: Blocking vs. Non-blocking

### The Scenario
Initially, when you clicked "RUN," the UI would stop responding. You couldn't click buttons, and the screen wouldn't update until the tool (nmap) was completely finished.

### The Technical Cause: `process.communicate()`
We were using `await process.communicate()`. 
*   **How it works:** It waits for the tool to finish entirely and captures the whole "book" of output at once.
*   **The alternative:** Reading line-by-line.

### The Solution: Async Streaming (`readline`)
We refactored the `Executor` to use a `while True: line = await process.stdout.readline()` loop.
*   **Intent:** To treat the tool's output like a "live stream" rather than a "downloaded file."
*   **Result:** The UI remains interactive because the "event loop" (the brain of the app) can process one line of output, update the screen, and then quickly check if you clicked a button before going back to read the next line.

**Research Keywords:** *Asynchronous I/O, Event Loops, Non-blocking streams, Python Coroutines.*

---

## 2. Architecture: "Smart Adapter / Stupid Framework"

### The Decision
We decided that the **Adapters** (like `tools/nmap/adapter.py`) should contain all the parsing logic, while the **Engine** and **UI** should know nothing about how nmap works.

### Why this over alternatives?
*   **Alternative (Hardcoding):** We could have put nmap logic directly in the UI. 
    *   *Risk:* If you want to add `gobuster` later, you have to rewrite the UI. It becomes a "spaghetti" mess.
*   **Our Choice (Pluggable Adapters):** By making the adapter return a standard "Finding" object, the UI can display *any* tool's results without changing a single line of UI code.

**Research Keywords:** *Separation of Concerns, Plugin Architecture, Data Normalization.*

---

## 3. Data Modeling: The Netblock Refactoring

### The Decision
We moved the `organization` field from `NetworkHost` to a new `NetworkNetblock` schema.

### Why? (Data Integrity)
In cybersecurity, an IP address (Host) might belong to one company today and another tomorrow. However, the "Netblock" (the range of IPs) is what the organization actually owns.
*   **The Lesson:** Don't "muddle" your data. Put information where it semantically belongs. If you put company info on every IP, and the company name changes, you have to update 1,000 IPs. If you put it on the Netblock, you update it once.

**Research Keywords:** *Database Normalization, Entity-Relationship Modeling.*

---

## 4. UI/UX: The Two-Phase Learning Flow

### The Decision
We moved from a single dashboard to a **Phase 1 (Discovery) -> Phase 2 (Execution)** flow for Learning Mode.

### Design Intent
*   **Discovery (Tool Browser)**: Beginners don't know what tools exist. By providing a categorized "App Store" style browser with one-line summaries, we reduce the "blank page" anxiety.
*   **Execution (Lesson Screen)**: Once a tool is selected, the UI shifts to a specialized 2-column layout. 
    *   **The 50/50 Split**: We prioritize the **Explanation** and **Raw Output** equally. 
    *   **Layout over Visibility**: We use `display: none` (via the `.hidden` class) instead of just `visible = False` to ensure the layout "snaps" correctly when buttons like **STOP** appear.

---

## 5. CLI Literacy: The `raw_flags` Input

### The Decision
Instead of only providing "Easy Mode" checkboxes for flags, we implemented a manual `raw_flags` text input box.

### Why this over alternatives?
*   **Alternative (Checkboxes Only)**: It's safer but doesn't teach the student how to use the tool in the "real world" terminal.
*   **Our Choice (Validated Manual Input)**: We allow students to type flags like `-sV` manually. 
    *   **Guardrails**: The UI automatically checks for `sudo` or dangerous commands before execution.
    *   **The Lesson**: We want to transition students from "button-clickers" to CLI-literate engineers while maintaining a safety net.

**Research Keywords:** *Gradual Disclosure, UI Guardrails, CLI Simulation.*

---

## 6. The Milestone System: Triggering Explanations

### The Decision
Instead of explaining every single line of nmap output (which would be noisy), we implemented a **Milestone** system.

### How it Works
1.  **Detection:** The `Executor` watches for specific events, such as when the first `network.service` is found.
2.  **Trigger:** It fires a milestone named `first_service`.
3.  **Context:** It grabs the data from that finding (IP, Port, Service Name).
4.  **Template:** It looks up a prompt in the tool's `manifest.toml` and fills in the blanks.
    *   *Example:* "The scanner found the first open port: {service_name} on {host_ip}:{port}."
5.  **Streaming:** The filled prompt is sent to an **Explainer Backend** (like a local LLM or a simple template engine), which streams the human-readable explanation back to the UI.

### Why this over alternatives?
*   **Alternative (Timer-based):** We could explain every 5 seconds.
    *   *Risk:* It might explain nothing if the tool is slow, or miss critical events.
*   **Our Choice (Event-based):** We only explain when something *actually happens*. This ensures the "Signal-to-Noise" ratio remains high for the student.

**Research Keywords:** *Event-Driven Architecture, Pub/Sub Pattern, Real-time Analysis.*

---

## 7. Robustness: Graceful Degradation

### The Scenario
The app crashed because `pyperclip` (for copying text) wasn't installed.

### The Technique: Optional Imports
We wrapped the `import pyperclip` inside a `try/except ImportError` block.
*   **The Intent:** A missing "nice-to-have" feature should never crash a "must-have" application. 
*   **Design Choice:** If the library is missing, we `notify` the user with an instruction on how to fix it, rather than letting the Python interpreter "explode."

**Research Keywords:** *Defensive Programming, Error Handling, Dependency Management.*

---

## 8. CSS Dialects: Textual vs. Web

### The Lesson
You saw errors with `font-family` and `italic`. 
*   **Why?** Textual is a **TUI** (Terminal User Interface). Terminals don't have "fonts" in the way browsers do; the terminal app (like Alacritty or iTerm) decides the font. 
*   **Solution:** Use the framework-specific properties like `text-style: italic;`. Always check the documentation of your specific UI library, as "Standard CSS" often doesn't apply 1:1.
