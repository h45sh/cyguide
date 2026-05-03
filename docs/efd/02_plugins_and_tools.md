# 02: The Detective's Kit (Plugins & Tools)

CyGuide is built to be **extensible**. We want anyone to be able to add a tool (like `sqlmap` or `ffuf`) without having to understand how the whole app works.

## 1. The "Smart Adapter / Stupid Framework" Rule
This is our design philosophy:
*   **The Framework is "Stupid"**: It doesn't know what `nmap` is. It just knows how to run a command and save the results.
*   **The Adapter is "Smart"**: The code inside `tools/nmap/adapter.py` knows exactly how to read nmap's weird text output and turn it into clean `Findings`.

---

## 2. What makes a Plugin?
Every tool is just a folder in the `tools/` directory with two files:

### A. `manifest.toml` (The ID Card)
This file tells CyGuide:
1.  **What is the tool named?**
2.  **What does it need to start?** (e.g., "I need an IP address")
3.  **What does it produce?** (e.g., "I find open ports")
4.  **Learning Milestones**: The `[learning.explainer]` section defines prompt templates for the Milestone System.
    *   *Example*: `first_service = "Explain why finding {service_name} on {host_ip}:{port} is significant for a beginner."`

### B. `adapter.py` (The Translator)
This is the Python code. It has three main jobs:
1.  `validate_install()`: Is `nmap` actually installed on this computer?
2.  `build_command()`: Turn the target IP into a string like `["nmap", "-sV", "127.0.0.1"]`.
3.  `parse_output()`: Read the text that nmap prints and `yield` Findings.

---

## 3. Recipes: The "Pre-built Kits"
Manifests now support **Recipes**. 
*   **The Intent**: Beginners often don't know which flags are best. A Recipe like "Standard Service Scan" automatically populates the recommended flags (e.g., `-sV -T4`), giving the student a safe and effective starting point.

---

## 4. The "Smart Adapter / Stupid Framework" Rule (Refined)
The Framework is responsible for **Concurrent Streaming**. 
*   **The Decision**: We stream `stdout` and `stderr` at the same time.
*   **The Intent**: Errors like "DNS resolution failed" often go to `stderr`. If we only streamed `stdout`, the student would see a blank screen and have no idea why the tool isn't working. 

---

## 5. Chaining & Suggestions (Power Mode)
How does CyGuide know to suggest `gobuster` after `nmap` finds port 80?

It uses **Derived Suggestions**.
1.  `nmap` finishes and puts a `network.service` (Port 80) into the graph.
2.  The `ToolRegistry` looks at `gobuster/manifest.toml`.
3.  It sees: `accepts_derived_from = ["network.service"]` with a filter `service_name == "http"`.
4.  The TUI sees the match and pops up a button: *"Hey, I found a web service. Want to run gobuster?"*

---

## 6. Why use `AsyncIterator`?
In `adapter.py`, you will see `async def parse_output(...) -> AsyncIterator`.

**Why?** Because security tools are slow! If `nmap` takes 5 minutes, we don't want the user to wait 5 minutes for a blank screen. By using an **AsyncIterator**, the adapter can `yield` a finding the *second* it finds it, and the UI will update instantly while the tool is still running.

---

### Final Step:
Learn how we save the case! **[03: The Case File (Session & History)](03_session_and_history.md)**
