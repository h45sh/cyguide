# Academic & Classroom Lab Guide: Verifiable Cybersecurity Pedagogy

CyGuide is engineered to solve a fundamental problem in cybersecurity education: **unverifiable lab submissions**. 

In conventional computer security and ethical hacking courses, instructors evaluate student performance using static PDF writeups or screenshots of flags—which are easily shared or plagiarized. CyGuide replaces this with **forensically verifiable, replayable lab sessions** backed by atomic SQLite audit archives and local privacy-preserving AI mentoring.

---

## Why Use CyGuide in Academic Labs?

1. **True Methodology Auditing**: Instructors can review the exact sequence of commands, flags, timestamps, and terminal output a student executed, rather than relying on after-the-fact reports.
2. **Zero-Cost, Privacy-First AI Mentoring**: By pairing with local Ollama instances (e.g. `gemma`, `llama3`), departments incur **$0 in API fees** while ensuring zero student telemetry or lab data leaves university workstations (FERPA compliant).
3. **Deterministic Entity Corroboration**: Discovered ports, endpoints, and vulnerabilities automatically organize into a structured graph, teaching students how real-world security teams correlate attack surfaces.
4. **Offline & Isolated Lab Support**: CyGuide requires zero internet connection to run local reconnaissance labs and parse structured findings.

---

## Instructor Workflow: Setting Up & Grading Labs

### 1. Distributing Lab Environments
Students can install CyGuide directly on their Linux workstations, virtual machines (Kali/Parrot), or via Docker:

```bash
# Recommended lightweight container deployment for student machines
docker run -it --rm --net=host -v ~/.cyguide:/root/.cyguide ghcr.io/h45sh/cyguide
```

### 2. Instructing Students to Export Sessions
At the end of an assigned CTF or network audit lab, instruct students to export their investigation:

```bash
# Student command line export
cyg export <session_id> student_submission.db --report student_report.md
```

This exports:
* The full relational entity graph (all discovered hosts, open ports, software banners, and vulnerabilities).
* The complete chronological audit log of all executed commands and raw tool outputs.
* An automatically synthesized technical summary in Markdown.

### 3. Importing & Grading Submissions
The instructor or teaching assistant downloads `student_submission.db` and imports it into their own local CyGuide dashboard:

```bash
cyg import student_submission.db
```

#### What the Instructor Can Verify:
* **The Entity Graph**: Check whether the student successfully enumerated target subnets and identified vulnerable services without missing assets.
* **Chronological Command Timeline**: Inspect the command sequence to verify that the student used systematic discovery techniques rather than running arbitrary automated scripts.
* **Terminal Logs**: Review verbatim stdout/stderr streams to confirm that flags and findings were legitimately obtained on the target machine.

---

## Student Workflow: Learning & Submitting

### 1. Interactive Learning Mode
For beginner and intermediate students, CyGuide's **Learning Mode** acts as an interactive lab workbench:
* **Curated Tool Recipes**: Step through safe, standardized command recipes for `nmap`, `gobuster`, `nikto`, `ffuf`, `nuclei`, and DNS tools.
* **Flag Inspections**: Explains what each flag (e.g., `-sS`, `-sV`, `-Pn`) does under the hood before execution.
* **Socratic AI Tutor**: Ask clarifying questions about network behaviors, protocol mechanics, and remediation steps without leaving the terminal.

### 2. Power Mode (Open Labs & CTFs)
During open-ended capture-the-flag competitions or capstone penetration testing exercises, students use **Power Mode**:
* Launch concurrent tools in separate tabs (`Ctrl+T`).
* Click target graph nodes to automatically bind `$TARGET` and `$PORT` into subsequent commands without copy-pasting.
* Review real-time finding discovery as entities are linked deterministically.

---

## Recommended Departmental Course Integrations

| Course Title | Recommended Modules | Lab Objective |
| :--- | :--- | :--- |
| **Intro to Cybersecurity** | Learning Mode (`nmap`, `whois`, `dnspython`) | Understanding port scanning, TCP handshakes, and DNS enumeration. |
| **Web Application Security** | Learning Mode (`gobuster`, `ffuf`, `nikto`) | Discovering hidden endpoints, directory brute-forcing, and HTTP status codes. |
| **Ethical Hacking & Pentesting** | Power Mode (Multi-tool correlation) | Conducting full-scope penetration tests with stateful graph tracking. |
| **Vulnerability Assessment** | Power Mode (`nuclei`, `searchsploit`) | Mapping discovered services to Exploit-DB references and CVE advisories. |
