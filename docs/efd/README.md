# 🎓 CyGuide: Explanation for Dummies (EFD)

Welcome to the **EFD**! If you know Python but feel overwhelmed by terms like "Entity Graph," "PIK Upserts," or "Declarative Manifests," you are in the right place. 

This directory is your map to understanding **how CyGuide works under the hood** and **why I built it this way**.

---

## 🗺️ The Big Picture

Imagine you are a detective. To solve a case, you use different tools (magnifying glass, fingerprint kit, database search). 

1.  **The Old Way (Messy)**: You write your notes on random scraps of paper. Every tool has its own notebook. If you find a name in one and an address in another, you have to manually remember they belong to the same person.
2.  **The CyGuide Way (Smart)**: Every tool you use gives you a "Finding" (a standard card). You give that card to the "Headquarters" (The Engine). The HQ is smart—if it sees two cards about the same IP address, it sticks them together on a big "Evidence Board" (The Entity Graph).

---

## 📂 What's in this Guide?

We have broken this down into three simple parts:

1.  **[01: Data & The Evidence Board (Schemas & Graphs)](01_data_and_schemas.md)**  
    *Learn how we turn messy tool output into clean, structured data that connects itself.*
2.  **[02: The Detective's Kit (Plugins & Tools)](02_plugins_and_tools.md)**  
    *Learn how we add new tools without breaking the system. (The "Smart Tool, Stupid Framework" rule).*
3.  **[03: The Case File (Session & History)](03_session_and_history.md)**  
    *Learn how we remember everything that happened so you can redo a scan perfectly.*

---

## 💡 Three Golden Rules of our Codebase

If you remember nothing else, remember these:

*   **Rule 1: Don't Guess.** If a tool isn't 100% sure two things are the same, don't merge them. Use an "Alias" instead.
*   **Rule 2: Keep the Core Simple.** The main engine should be like a post office—it just delivers data. It shouldn't need to know *what* nmap is or *how* gobuster works.
*   **Rule 3: Validation is King.** We use a library called `Pydantic`. It’s like a strict bouncer at a club—if the data doesn't look exactly like the "Schema" (the ID card), it doesn't get in.

---

### Ready to start?
Head over to **[01_data_and_schemas.md](01_data_and_schemas.md)** to learn about Findings!
