# 03: The Case File (Session & History)

Security work is useless if you can't prove what you did or repeat it later. CyGuide uses two different ways to remember the "Truth."

## 1. The Dual-Storage System
When the engine receives a Finding, it saves it in two places at once:

### A. The Event Log (The Video Tape 📹)
*   **What it is**: A simple, append-only table in SQLite.
*   **The Rule**: You can never change it. Every finding gets added at the bottom with a timestamp.
*   **Why?**: This is our **Reproducibility Foundation**. If the database gets corrupted, we can "replay" the Event Log from the beginning to rebuild the exact same graph. It’s like a pilot’s black box.

### B. The Entity Graph (The Current Status 📊)
*   **What it is**: A stateful map of everything we know *right now*.
*   **The Rule**: It uses **Upserts** (Update or Insert) to keep information clean.
*   **Why?**: This is what the TUI uses to draw the screen. It doesn't need to know that we ran nmap five times; it just needs to know the final status of Port 80.

---

## 2. Session Portability
Because we use **SQLite**, your entire session is saved in a single file (usually `cyguide.db` or `test_session.db`). 

You can take this file, give it to a colleague, and they can open it in CyGuide to see exactly what you saw.

---

## 3. The "Entity Alias" (Identity Verification)
What happens if you find a host named `staging.local` and later find an IP `10.0.0.5`? Are they the same?

**The CyGuide Principle**: Never make a "smart guess" that could be wrong.
Instead of the engine guessing, we use an **Entity Alias** finding.
1.  An adapter (or a user) says: *"I have proof that `staging.local` is actually `10.0.0.5`."*
2.  They emit an `entity.alias` finding.
3.  The engine creates an explicit connection in the graph.

This keeps the data **auditable**. You can always look back and see *why* the system thinks two things are the same.

---

## 🏁 Conclusion: Your Coding Journey Starts Here

You now know more about CyGuide than 99% of people! 

### What should you do next?
1.  **Read the code**: Start with `cyguide/schemas/base.py`—it’s the "DNA" of our findings.
2.  **Look at an adapter**: See how `tools/nmap/adapter.py` turns text into data.
3.  **Try adding a tool**: Follow the steps in **[CONTRIBUTING.md](../CONTRIBUTING.md)**.

**Happy Hacking!** 🛡️
