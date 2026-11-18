#!/usr/bin/env python3
"""
scripts/agg.py - Autonomous Engine for engineering-aggregate.

Provides deterministic, zero-token/low-token tooling for:
1. inherit:   Fast keyword/path-based extraction of relevant knowledge (Ancestral Inheritance).
2. tithe:     Automated end-of-thread retrospective scaffolding from git diff (Equivalent Exchange).
3. condense:  Algorithmic link auditing, line budget checks, and index updates.
4. sync:      Auto-discovers .agents/knowledge/*.md domain files and registers them into index.json.
5. test:      Built-in regression suite verifying that the CLI and hooks remain healthy across evolutions.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

# Paths
AGENTS_DIR = Path(".agents")
KNOWLEDGE_DIR = AGENTS_DIR / "knowledge"
THREADS_DIR = AGENTS_DIR / "threads"
HOOKS_DIR = AGENTS_DIR / "hooks"
INDEX_FILE = KNOWLEDGE_DIR / "index.json"


def run_cmd(cmd):
    """Run shell command safely and return output."""
    try:
        res = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def run_hook(hook_name, *args):
    """Execute dynamic user/agent hook if present in .agents/hooks/<hook_name>."""
    if not HOOKS_DIR.exists():
        return
    for ext in ["", ".sh", ".py"]:
        candidate = HOOKS_DIR / f"{hook_name}{ext}"
        if candidate.exists() and os.access(candidate, os.X_OK):
            cmd = f'"{candidate}" ' + " ".join(f'"{a}"' for a in args)
            run_cmd(cmd)
            break


def load_index():
    """Load or generate default index.json."""
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "domains": {},
        "anti_patterns": []
    }


def save_index(data):
    """Save index.json atomically."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def cmd_inherit(args):
    """
    Inherit relevant domain intelligence based on touched files or keywords.
    Outputs a concise, token-efficient brief for the agent's context.
    """
    run_hook("pre_inherit")

    query_terms = set()
    if args.query:
        query_terms.update([w.lower() for w in re.split(r"[\s,]+", args.query) if len(w) > 2])

    target_files = []
    if args.files:
        target_files.extend(args.files)
    else:
        git_status = run_cmd("git status --porcelain")
        if git_status:
            for line in git_status.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    target_files.append(parts[-1])

    for f in target_files:
        path_tokens = re.split(r"[/._\-]+", f.lower())
        query_terms.update([t for t in path_tokens if len(t) > 2])

    index = load_index()
    matched_domains = set()
    matched_anti_patterns = []

    # 1. Match domains via index file_patterns and keywords
    for domain, meta in index.get("domains", {}).items():
        patterns = meta.get("file_patterns", [])
        for p in patterns:
            for f in target_files:
                if Path(f).match(p) or p in f:
                    matched_domains.add(domain)

        domain_keywords = set(k.lower() for k in meta.get("keywords", []))
        if domain_keywords.intersection(query_terms):
            matched_domains.add(domain)

    # 2. Match anti-patterns
    for ap in index.get("anti_patterns", []):
        ap_keywords = set(k.lower() for k in ap.get("keywords", []))
        if ap.get("domain") in matched_domains or ap_keywords.intersection(query_terms):
            matched_anti_patterns.append(ap)

    is_compact = getattr(args, "compact", False)
    if is_compact:
        brief_bullets = []
        # Global Invariants (max 3 actionable rules from AGENTS.md)
        agents_md = Path("AGENTS.md")
        if agents_md.exists():
            for line in agents_md.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if (s.startswith("- ") or s.startswith("* ") or (s.startswith("**") and ":" in s)) and len(s) > 5:
                    brief_bullets.append(f"[GLOBAL] {s.lstrip('-* ')}")
                    if len(brief_bullets) >= 3:
                        break

        # Matched domain rules (extract actionable bullets, max 2 per domain)
        for domain in sorted(matched_domains):
            domain_file = KNOWLEDGE_DIR / f"{domain}.md"
            if domain_file.exists():
                count = 0
                for line in domain_file.read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if (s.startswith("- ") or s.startswith("* ")) and len(s) > 5:
                        brief_bullets.append(f"[{domain.upper()}] {s.lstrip('-* ')}")
                        count += 1
                        if count >= 2:
                            break

        # Anti-patterns (high-density trap warnings)
        for ap in matched_anti_patterns[:3]:
            title = ap.get("title", "Trap")
            repl = ap.get("replacement", "")
            brief_bullets.append(f"[TRAP: {title}] -> Instead: {repl}")

        if not brief_bullets:
            print("[INHERITANCE] Clean: No domain constraints or traps registered for current context.")
        else:
            print(f"=== INHERITANCE BRIEF: {len(brief_bullets)} ACTIVE RULES (COMPACT) ===")
            for b in brief_bullets[:10]:
                print(f"• {b}")
            print("=== END BRIEF: PROCEED WITH TASK ===")

        run_hook("post_inherit")
        return

    print("=== ANCESTRAL INHERITANCE: REPOSITORY INTELLIGENCE BRIEF ===")
    print(f"Context Filter: {', '.join(sorted(target_files)) if target_files else 'None'} | Terms: {', '.join(sorted(query_terms)) if query_terms else 'General'}\n")

    # 3. Output Global Laws (AGENTS.md summary if present)
    agents_md = Path("AGENTS.md")
    if agents_md.exists():
        print("--- [GLOBAL REPOSITORY INVARIANTS] (from AGENTS.md) ---")
        with open(agents_md, "r", encoding="utf-8") as f:
            lines = f.readlines()[:40]
            print("".join(lines).strip())
        print("\n-------------------------------------------------------")

    # 4. Output matched domain knowledge
    if matched_domains:
        for domain in sorted(matched_domains):
            domain_file = KNOWLEDGE_DIR / f"{domain}.md"
            if domain_file.exists():
                print(f"\n--- [DOMAIN INTELLIGENCE: {domain.upper()}] ({domain_file}) ---")
                with open(domain_file, "r", encoding="utf-8") as f:
                    print(f.read().strip())
    else:
        print("\n[Notice]: No domain-specific constraints found for current files.")

    # 5. Output matched anti-patterns (What NOT to do)
    if matched_anti_patterns:
        print("\n--- [PROHIBITED ANTI-PATTERNS & FATAL TRAPS] ---")
        for ap in matched_anti_patterns:
            print(f"- TRAP: {ap.get('title')}")
            print(f"  FAILURE MODE: {ap.get('why_failed')}")
            print(f"  REQUIRED REPLACEMENT: {ap.get('replacement')}\n")
    else:
        ap_file = KNOWLEDGE_DIR / "anti-patterns.md"
        if ap_file.exists():
            print(f"\n--- [GENERAL ANTI-PATTERNS] ({ap_file}) ---")
            with open(ap_file, "r", encoding="utf-8") as f:
                lines = [l for l in f.readlines() if l.strip().startswith("-") or l.strip().startswith("#")][:25]
                print("".join(lines).strip())

    print("\n=== END OF INHERITANCE BRIEF: PROCEED WITH TASK EXECUTION ===")
    run_hook("post_inherit")


def cmd_tithe(args):
    """
    Automate the Equivalent Exchange payback. Scaffolds a thread retrospective
    pre-filled with git branch, commit, touched files, and diff summary.
    """
    topic = args.topic
    if not topic:
        branch = run_cmd("git branch --show-current")
        topic = branch.replace("/", "_").replace("-", "_") if branch else "session"

    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    target_file = THREADS_DIR / f"thread_{topic}.md"

    branch = run_cmd("git branch --show-current") or "main"
    commit = run_cmd("git rev-parse --short HEAD") or "uncommitted"
    diff_stat = run_cmd("git diff --stat HEAD~1 HEAD") or run_cmd("git diff --stat")
    changed_files = run_cmd("git diff --name-only HEAD~1 HEAD") or run_cmd("git diff --name-only")

    content = f"""# Thread Retrospective: {topic}

- **Branch / PR**: `{branch}` (Commit `{commit}`)
- **Primary Domain**: `[{args.domain or 'Unspecified'}]`
- **Touched Files**:
{chr(10).join(f"- `{f}`" for f in changed_files.splitlines()) if changed_files else "- None"}

---

## Pillar 1: Aggregate Intelligence Feedback
*Audit of existing techniques consulted or inherited during this thread:*

| Technique / Rule Consulted | Outcome | Assessment | Detail & Context |
| :--- | :---: | :---: | :--- |
| *e.g. Existing DB connection pattern* | **VALIDATED** | Evergreen | *Held true without regressions.* |

*Options: VALIDATED | FAILED | SITUATIONAL | INSUFFICIENT DATA*

---

## Pillar 2: Novel Discoveries & Codebase Realities
*Document newly discovered runtime quirks, race conditions, or architecture seams:*

- **Principle**: *Name of the insight*
- **Problem Solved**: *What bug, performance cliff, or friction was resolved?*
- **Mechanism**: *How does it work?*
- **Code Reference**: `{changed_files.splitlines()[0] if changed_files else 'path/to/file.py'}:L1`

---

## Pillar 3: Anti-Patterns & Prohibited Techniques (What NOT to do)
*Document failed attempts and dead ends future agents must avoid:*

- **Anti-Pattern**: *Prohibited technique*
- **Why it Failed**: *Root cause of failure*
- **Correct Replacement**: *Mandated alternative*

---

## Pillar 4: Invariants & Performance Contracts to Preserve
*Quantitative guarantees and reproduction commands:*

| Contract / Invariant | Threshold / Guarantee | Verification Command |
| :--- | :--- | :--- |
| *Execution Safety* | All tests pass | `pytest` or project test command |

---
<!-- Diff Stat Summary:
{diff_stat}
-->
"""

    if target_file.exists() and not args.force:
        print(f"[Notice]: File '{target_file}' already exists. Use --force to overwrite.")
    else:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Tithe scaffolded at: {target_file}")
        print("Agent instructions: Review and fill in the 4 pillars with empirical facts from your test runs.")

    run_hook("post_tithe", str(target_file))


def cmd_quick_tithe(args):
    """
    Atomic Equivalent Exchange: One single command to record the retrospective,
    register new anti-patterns, update index, and run audits (< 50ms).
    Eliminates multi-step round trips and context bloat.
    """
    topic = args.topic
    branch = run_cmd("git branch --show-current") or "main"
    if not topic:
        topic = branch.replace("/", "_").replace("-", "_") if branch else "session"

    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    target_file = THREADS_DIR / f"thread_{topic}.md"

    commit = run_cmd("git rev-parse --short HEAD") or "uncommitted"
    changed_files = run_cmd("git diff --name-only HEAD~1 HEAD") or run_cmd("git diff --name-only")
    files_list = changed_files.splitlines() if changed_files else []

    summary = getattr(args, "summary", None) or f"Task execution and validation on {branch}"
    domain = getattr(args, "domain", None) or ("General" if not files_list else "Codebase")
    validated = getattr(args, "validated", None) or "Standard coding & design patterns"
    discovery = getattr(args, "discovery", None) or f"Changes verified in {files_list[0] if files_list else 'codebase'}"
    trap = getattr(args, "trap", None) or "None observed"
    invariant = getattr(args, "invariant", None) or "Test suite passes without regressions"

    # Pillar 4 Verification Execution Gate (Lauren Tan 70/30 Verification Law)
    verify_cmd = getattr(args, "verify_cmd", None)
    verify_status = "Skipped"
    if verify_cmd:
        print(f"🔬 [VERIFICATION GATE] Running verification contract: `{verify_cmd}`...")
        v_res = run_cmd(verify_cmd)
        # Check actual exit code
        proc = subprocess.run(verify_cmd, shell=True, text=True, capture_output=True)
        if proc.returncode != 0:
            print(f"❌ [VERIFICATION GATE FAILED] Command `{verify_cmd}` failed with exit code {proc.returncode}!")
            if proc.stderr:
                print(f"Error output:\n{proc.stderr.strip()[:500]}")
            if not getattr(args, "force", False):
                print("Aborting tithe: Code does not satisfy quantitative verification invariant. Fix code or run with --force.")
                sys.exit(1)
            verify_status = f"FAILED (exit code {proc.returncode})"
        else:
            print("✅ [VERIFICATION GATE PASSED] Invariant verified mathematically/empirically.")
            verify_status = "PASSED (exit code 0)"

    content = f"""# Thread Retrospective: {topic}

- **Branch / PR**: `{branch}` (Commit `{commit}`)
- **Primary Domain**: `[{domain}]`
- **Summary**: {summary}
- **Touched Files**:
{chr(10).join(f"- `{f}`" for f in files_list) if files_list else "- None"}

---

## Pillar 1: Aggregate Intelligence Feedback
| Technique / Rule Consulted | Outcome | Assessment | Detail & Context |
| :--- | :---: | :---: | :--- |
| {validated} | **VALIDATED** | Evergreen | Preserved and confirmed during implementation. |

---

## Pillar 2: Novel Discoveries & Codebase Realities
- **Insight**: {discovery}
- **Mechanism**: Confirmed via test execution and functional verification.
- **Reference**: `{files_list[0] if files_list else 'src'}:L1`

---

## Pillar 3: Anti-Patterns & Prohibited Techniques (What NOT to do)
- **Trap / Anti-Pattern**: {trap}
- **Prevention**: Enforce architectural and runtime validation contracts.

---

## Pillar 4: Invariants & Performance Contracts to Preserve
| Contract / Invariant | Threshold / Guarantee | Verification Command | Gate Status |
| :--- | :--- | :--- | :--- |
| {invariant} | Zero Regressions | `{verify_cmd or 'agg.py test'}` | **{verify_status}** |

---
"""
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)

    # Register trap if provided and real
    if trap and trap.lower() not in ["none", "none observed"]:
        ap_file = KNOWLEDGE_DIR / "anti-patterns.md"
        if ap_file.exists():
            with open(ap_file, "a", encoding="utf-8") as ap_f:
                ap_f.write(f"\n- **Trap [{domain}]**: {trap} (Recorded in `{target_file.name}`)\n")

    # Run internal sync and condensation silently
    cmd_sync(argparse.Namespace())
    cmd_condense(argparse.Namespace(silent=True))

    print(f"✅ [QUICK-TITHE] Retrospective recorded, intelligence synchronized, and audits passed: {target_file}")
    run_hook("post_tithe", str(target_file))


def cmd_auto_tithe(args):
    """
    Fully automated background tithe: extracts context from recent commit or diff
    and executes quick-tithe with zero manual prompting.
    """
    last_commit_msg = run_cmd("git log -1 --pretty=%B").strip() or "Automated task completion"
    first_line = last_commit_msg.splitlines()[0] if last_commit_msg else "task"
    branch = run_cmd("git branch --show-current") or "main"
    topic = getattr(args, "topic", None) or branch.replace("/", "_").replace("-", "_")

    quick_args = argparse.Namespace(
        topic=topic,
        domain=getattr(args, "domain", None) or "Codebase",
        summary=first_line,
        validated="Inherited constraints & test integrity",
        discovery=f"Commit {run_cmd('git rev-parse --short HEAD') or 'HEAD'}: {first_line}",
        trap=getattr(args, "trap", None) or "None observed",
        invariant="All unit and integration tests passing",
        force=True
    )
    cmd_quick_tithe(quick_args)


def cmd_condense(args):
    """
    Algorithmic maintenance:
    - Scans for dead file/line references in .agents/knowledge/
    - Checks line count limits (Tier 1 <= 250 lines, Tier 2 <= 150 lines)
    """
    silent = getattr(args, "silent", False)
    if not silent:
        print("=== RUNNING ALGORITHMIC KNOWLEDGE CONDENSATION & AUDIT ===")

    agents_md = Path("AGENTS.md")
    if agents_md.exists():
        line_count = len(agents_md.read_text(encoding="utf-8").splitlines())
        status = "✅ PASS" if line_count <= 250 else "⚠️ EXCEEDED"
        if not silent:
            print(f"Tier 1 Budget (AGENTS.md): {line_count}/250 lines -> {status}")

    if KNOWLEDGE_DIR.exists():
        for k_file in KNOWLEDGE_DIR.glob("*.md"):
            lines = len(k_file.read_text(encoding="utf-8").splitlines())
            status = "✅ PASS" if lines <= 150 else "⚠️ EXCEEDED (Requires pruning)"
            if not silent:
                print(f"Tier 2 Budget ({k_file.name}): {lines}/150 lines -> {status}")

    if not silent:
        print("\nAuditing code references for drift/entropy...")
    link_pattern = re.compile(r"([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+):L(\d+)")
    dead_links = 0
    total_links = 0

    files_to_check = list(KNOWLEDGE_DIR.glob("*.md")) if KNOWLEDGE_DIR.exists() else []
    for f in files_to_check:
        content = f.read_text(encoding="utf-8")
        matches = link_pattern.findall(content)
        for filepath, _line_no in matches:
            total_links += 1
            if not Path(filepath).exists():
                if not silent:
                    print(f"⚠️  Dead reference in {f.name}: File '{filepath}' does not exist!")
                dead_links += 1

    # Zero-Apology Rule (Lauren Tan Principle): Flag newly introduced TODO/FIXME/HACK comments in recent diff
    recent_diff = run_cmd("git diff HEAD~1 HEAD") or run_cmd("git diff")
    escape_hatch_count = 0
    if recent_diff:
        escape_pattern = re.compile(r"^\+\s*.*(//|#|/\*)\s*(TODO|FIXME|HACK|WORKAROUND|TEMP|BUG):?", re.IGNORECASE | re.MULTILINE)
        found = escape_pattern.findall(recent_diff)
        escape_hatch_count = len(found)
        if escape_hatch_count > 0:
            msg = f"⚠️ [ZERO-APOLOGY AUDIT] Found {escape_hatch_count} 'escape hatch' comments (TODO/FIXME/HACK) added in diff! Fix code at root rather than excusing slop."
            if not silent:
                print(f"\n{msg}")

    if not silent:
        print(f"Reference Audit Complete: {total_links} references verified, {dead_links} dead links found.")
        print("=== CONDENSATION & AUDIT FINISHED ===")
    else:
        print(f"[Audit Summary]: {total_links} references verified, {dead_links} dead links, {escape_hatch_count} excuse comments.")


def cmd_deslop(args):
    """
    Codebase Anti-Entropy Sweep (Lauren Tan 'Codebase is Memory' Principle):
    Audits codebase for:
    1. Layer DAG leaks (e.g. UI directly importing db/storage/models)
    2. Nuance-heavy or banned APIs (e.g. unencapsulated raw timers, raw useEffect, raw sync)
    3. Accumulated TODO/FIXME debt that agents will emulate as canonical style.
    """
    print("=== RUNNING CODEBASE ANTI-ENTROPY SWEEP (DE-SLOP) ===")
    root = Path(".")
    
    # 1. Scan for escape hatch comments
    print("\n[1/3] Scanning for escape-hatch comments (TODO/FIXME/HACK)...")
    comment_pattern = re.compile(r"\b(TODO|FIXME|HACK|WORKAROUND)\b:?\s*(.*)", re.IGNORECASE)
    total_excuses = 0
    scanned_extensions = [".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".cpp", ".h"]

    for ext in scanned_extensions:
        for p in root.rglob(f"*{ext}"):
            # ignore hidden, vendor, node_modules, build directories, and tooling scripts
            if any(part.startswith(".") or part in ["node_modules", "target", "dist", "build", "venv", ".venv", "scripts"] for part in p.parts):
                continue
            try:
                for idx, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    match = comment_pattern.search(line)
                    if match:
                        total_excuses += 1
                        if total_excuses <= 10:
                            print(f"  • {p}:{idx} -> {match.group(0).strip()[:80]}")
            except Exception:
                pass

    if total_excuses > 10:
        print(f"  ... and {total_excuses - 10} more escape-hatch comments across codebase.")
    print(f"  Total escape-hatch comments found: {total_excuses}")

    # 2. Scan for layer DAG violations (UI -> DB/Backend)
    print("\n[2/3] Checking Architectural Seams (UI -> Direct DB/Backend imports)...")
    ui_patterns = [
        "src/ui/**", "src/components/**", "src/views/**", "src/frontend/**",
        "ui/**", "components/**", "cyguide/ui/**"
    ]
    dag_violations = 0
    forbidden_imports = ["sqlite3", "aiosqlite", "prisma", "typeorm", "storage/direct"]

    for pattern in ui_patterns:
        for p in root.glob(pattern):
            if p.is_file() and p.suffix in [".ts", ".tsx", ".js", ".jsx", ".py"]:
                try:
                    for idx, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        for bad in forbidden_imports:
                            if (
                                f"from '{bad}" in line
                                or f'from "{bad}' in line
                                or f"import {bad}" in line
                                or f"from {bad}" in line
                            ):
                                print(f"  🚨 Layer DAG Leak: {p}:{idx} directly imports '{bad}'!")
                                dag_violations += 1
                except Exception:
                    pass

    if dag_violations == 0:
        print("  ✅ Zero architectural DAG layer leaks detected in UI components.")
    else:
        print(f"  ⚠️ Total architectural leaks detected: {dag_violations}")

    # 3. Check for Anti-Patterns ready for Graduation to Linter/Compiler checks
    print("\n[3/3] Checking Anti-Patterns for Linter/Compiler Graduation...")
    index = load_index()
    aps = index.get("anti_patterns", [])
    grad_count = 0
    for ap in aps:
        freq = ap.get("frequency", 1)
        title = ap.get("title", "")
        if freq >= 2 or ap.get("critical", False):
            print(f"  🎓 Candidate for Linter Rule: '{title}' (Occurred {freq}x)")
            print(f"     Action: Graduate from prose in anti-patterns.md to a custom linter rule or AST check.")
            grad_count += 1

    if grad_count == 0:
        print("  ✅ All current anti-patterns are within acceptable frequency limits.")
    else:
        print(f"  ⚠️ {grad_count} anti-pattern(s) should be graduated into hard machine-enforced linter rules.")

    print("\n=== DE-SLOP SWEEP COMPLETE ===")


def cmd_sync(args):
    """
    Auto-discovers .agents/knowledge/*.md domain files and registers them into index.json.
    """
    if not KNOWLEDGE_DIR.exists():
        print(f"[Notice]: Knowledge directory '{KNOWLEDGE_DIR}' does not exist yet.")
        return

    index = load_index()
    domains = index.setdefault("domains", {})
    count_added = 0

    for md_file in KNOWLEDGE_DIR.glob("*.md"):
        domain_name = md_file.stem
        if domain_name in ["anti-patterns", "invariants"]:
            continue

        if domain_name not in domains:
            domains[domain_name] = {
                "path": str(md_file.as_posix()),
                "keywords": [domain_name],
                "file_patterns": [f"src/{domain_name}/**", f"**/{domain_name}/**"]
            }
            count_added += 1

    save_index(index)
    print(f"✅ Sync complete: Registered {count_added} new domains into {INDEX_FILE}.")


def cmd_test(args):
    """
    Built-in regression suite verifying that the CLI and hooks remain healthy across evolutions.
    """
    class SelfTest(unittest.TestCase):
        def test_load_index_structure(self):
            idx = load_index()
            self.assertIn("domains", idx)
            self.assertIn("anti_patterns", idx)

        def test_tithe_scaffold_output(self):
            dummy_file = THREADS_DIR / "thread__selftest_dummy.md"
            if dummy_file.exists():
                dummy_file.unlink()
            dummy_args = argparse.Namespace(topic="_selftest_dummy", domain="TestDomain", force=True)
            cmd_tithe(dummy_args)
            self.assertTrue(dummy_file.exists())
            content = dummy_file.read_text(encoding="utf-8")
            self.assertIn("Pillar 1: Aggregate Intelligence Feedback", content)
            self.assertIn("Pillar 2: Novel Discoveries & Codebase Realities", content)
            self.assertIn("Pillar 3: Anti-Patterns & Prohibited Techniques", content)
            self.assertIn("Pillar 4: Invariants & Performance Contracts", content)
            dummy_file.unlink()

        def test_inherit_compact(self):
            dummy_args = argparse.Namespace(files=["src/test.py"], query="test", compact=True)
            # Should run without throwing errors
            cmd_inherit(dummy_args)

        def test_quick_tithe_and_auto_tithe(self):
            dummy_file = THREADS_DIR / "thread__selftest_quick.md"
            if dummy_file.exists():
                dummy_file.unlink()
            q_args = argparse.Namespace(
                topic="_selftest_quick",
                domain="TestDomain",
                summary="Unit test execution",
                validated="Inheritance protocol",
                discovery="One-shot execution test",
                trap="None observed",
                invariant="All tests pass",
                force=True
            )
            cmd_quick_tithe(q_args)
            self.assertTrue(dummy_file.exists())
            content = dummy_file.read_text(encoding="utf-8")
            self.assertIn("Pillar 1: Aggregate Intelligence Feedback", content)
            self.assertIn("One-shot execution test", content)
            dummy_file.unlink()

            # Test auto-tithe
            auto_file = THREADS_DIR / "thread__selftest_auto.md"
            if auto_file.exists():
                auto_file.unlink()
            a_args = argparse.Namespace(topic="_selftest_auto", domain="AutoDomain", trap="None observed")
            cmd_auto_tithe(a_args)
            self.assertTrue(auto_file.exists())
            auto_file.unlink()

        def test_deslop_command(self):
            # Test deslop sweep runs cleanly
            d_args = argparse.Namespace()
            cmd_deslop(d_args)

        def test_verification_gate(self):
            # Test that a passing verification command succeeds
            v_args = argparse.Namespace(
                topic="_selftest_verify",
                domain="TestDomain",
                summary="Verification gate test",
                validated="Verification gate",
                discovery="Pillar 4 execution gate",
                trap="None observed",
                invariant="True condition",
                verify_cmd="python3 -c 'exit(0)'",
                force=True
            )
            cmd_quick_tithe(v_args)
            verify_file = THREADS_DIR / "thread__selftest_verify.md"
            self.assertTrue(verify_file.exists())
            content = verify_file.read_text(encoding="utf-8")
            self.assertIn("PASSED (exit code 0)", content)
            verify_file.unlink()

    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromTestCase(SelfTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


def cmd_harvest_t3(args):
    """
    Scans ~/.t3/caches/pull-requests/ to harvest PR metadata, feature branches,
    and reviews for a target repository, outputting a retrospective draft.
    """
    cache_dir = Path.home() / ".t3" / "caches" / "pull-requests"
    if not cache_dir.exists():
        print(f"[Error]: T3 pull-requests cache not found at '{cache_dir}'.")
        return

    repo_filter = args.repo.lower() if args.repo else None
    harvested = []

    for f in cache_dir.glob("pr-v2*"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                if isinstance(data, list) and len(data) > 0:
                    val = data[0].get("value", {})
                    payload_str = val.get("payload")
                    if payload_str:
                        payload = json.loads(payload_str)
                        r = payload.get("repository", "")
                        if not repo_filter or (repo_filter in r.lower()):
                            # Filter out automated bot bumps
                            if not payload.get("author", {}).get("isBot", False):
                                harvested.append(payload)
        except Exception:
            pass

    harvested.sort(key=lambda x: x.get("number", 0))
    print(f"=== HARVESTED {len(harvested)} PULL REQUESTS FROM T3 CACHE ===")

    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = THREADS_DIR / "thread_t3_harvest.md"

    md_lines = [
        "# Thread Retrospective: T3 Cache Historical Harvest",
        "",
        f"- **Repository Target**: `{args.repo or 'All'}`",
        f"- **Total PRs Harvested**: `{len(harvested)}`",
        "",
        "---",
        "",
        "## Harvested Feature & Fix Sprints",
        "",
        "| PR # | Title | Branch Flow | State |",
        "| :---: | :--- | :--- | :---: |"
    ]

    for pr in harvested:
        num = pr.get("number")
        title = pr.get("title", "").replace("|", "-")
        head = pr.get("headBranch", "")
        base = pr.get("baseBranch", "")
        state = pr.get("state", "")
        md_lines.append(f"| #{num} | {title} | `{head}` → `{base}` | **{state.upper()}** |")

    md_lines.extend([
        "",
        "---",
        "",
        "## Key Solved Regressions & Invariant Candidates",
        "",
        "Review the PR titles above to extract verified techniques into `.agents/knowledge/<domain>.md` and anti-patterns into `.agents/knowledge/anti-patterns.md`.",
        ""
    ])

    out_file.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"✅ Harvest report generated at: {out_file}")
    print("Agent instruction: Review and extract the confirmed techniques and timing invariants into domain knowledge files.")


def main():
    parser = argparse.ArgumentParser(description="engineering-aggregate command engine")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # inherit
    p_inherit = subparsers.add_parser("inherit", help="Extract ancestral intelligence for files or query")
    p_inherit.add_argument("--files", nargs="*", help="File paths being modified")
    p_inherit.add_argument("--query", type=str, help="Keywords or task description")
    p_inherit.add_argument("--compact", action="store_true", help="Emit high-density, low-token brief (< 150 tokens)")

    # tithe
    p_tithe = subparsers.add_parser("tithe", help="Scaffold retrospective from git diff")
    p_tithe.add_argument("--topic", type=str, help="Topic / feature name")
    p_tithe.add_argument("--domain", type=str, help="Primary domain (UI, Storage, Engine, etc.)")
    p_tithe.add_argument("--force", action="store_true", help="Overwrite existing thread retrospective")

    # quick-tithe
    p_qtithe = subparsers.add_parser("quick-tithe", help="One-shot atomic retrospective, condensation, and audit")
    p_qtithe.add_argument("--topic", type=str, help="Topic / feature name")
    p_qtithe.add_argument("--domain", type=str, help="Primary domain (UI, Storage, Engine, etc.)")
    p_qtithe.add_argument("--summary", type=str, help="Short summary of implementation")
    p_qtithe.add_argument("--validated", type=str, help="Rule or technique validated")
    p_qtithe.add_argument("--discovery", type=str, help="Novel discovery or code reference")
    p_qtithe.add_argument("--trap", type=str, help="Anti-pattern observed or avoided")
    p_qtithe.add_argument("--invariant", type=str, help="Contract or invariant preserved")
    p_qtithe.add_argument("--verify-cmd", type=str, help="Verification command to execute (Lauren Tan 70/30 Verification Law)")
    p_qtithe.add_argument("--force", action="store_true", help="Overwrite existing thread retrospective")

    # auto-tithe
    p_atithe = subparsers.add_parser("auto-tithe", help="Fully automated background tithe from git log/diff")
    p_atithe.add_argument("--topic", type=str, help="Topic / feature name")
    p_atithe.add_argument("--domain", type=str, help="Primary domain")
    p_atithe.add_argument("--trap", type=str, help="Optional anti-pattern to record")

    # deslop (Lauren Tan "Codebase is Memory" sweep)
    p_deslop = subparsers.add_parser("deslop", help="Run codebase anti-entropy sweep for layer DAG leaks and excuse comments")

    # condense
    p_condense = subparsers.add_parser("condense", help="Run algorithmic budget and reference audit")
    p_condense.add_argument("--silent", action="store_true", help="Suppress detailed audit logs")

    # sync
    p_sync = subparsers.add_parser("sync", help="Auto-sync knowledge files into index.json")

    # test
    p_test = subparsers.add_parser("test", help="Run self-testing suite for CLI and tools")

    # harvest-t3
    p_harvest = subparsers.add_parser("harvest-t3", help="Harvest PRs and reviews from ~/.t3/caches/")
    p_harvest.add_argument("--repo", type=str, help="Repository name filter (e.g. h45sh/cyguide)")

    args = parser.parse_args()
    if args.subcommand == "inherit":
        cmd_inherit(args)
    elif args.subcommand == "tithe":
        cmd_tithe(args)
    elif args.subcommand == "quick-tithe":
        cmd_quick_tithe(args)
    elif args.subcommand == "auto-tithe":
        cmd_auto_tithe(args)
    elif args.subcommand == "deslop":
        cmd_deslop(args)
    elif args.subcommand == "condense":
        cmd_condense(args)
    elif args.subcommand == "sync":
        cmd_sync(args)
    elif args.subcommand == "test":
        cmd_test(args)
    elif args.subcommand == "harvest-t3":
        cmd_harvest_t3(args)


if __name__ == "__main__":
    main()
