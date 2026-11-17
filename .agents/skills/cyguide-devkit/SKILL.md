---
name: cyguide-devkit
description: Author, scaffold, validate, and test production-grade CyGuide security tool adapters. Use when adding a new tool adapter (e.g. sqlmap, masscan, hydra, netexec, amass), authoring manifest.toml, implementing streaming finding parsers, writing hermetic parser tests, or validating plugin contracts against CyGuide standards.
---

# CyGuide Adapter Authoring & DevKit Skill

This skill guides the creation, maintenance, and verification of production-grade tool adapters for CyGuide. Every tool in CyGuide is isolated into its own self-contained directory under `tools/<tool_name>/` adhering strictly to the **Smart Adapter / Stupid Framework** architecture:

* **The Core Framework (`cyguide/engine`)**: Agnostic to individual security CLI tools. Manages the asynchronous subprocess lifecycle, deterministic SQLite entity graph, event logs, rate-limit backoff, and user interface without containing tool-specific execution or parsing logic.
* **The Tool Adapters (`tools/<tool_name>/`)**: Self-contained plugins that translate external CLI arguments, stream stdout, parse output into standardized `BaseFinding` schema models, auto-wire graph relationships, and sanitize terminal noise for the AI tutor.

---

## 1. Directory Structure Contract

Every tool plugin must adhere to this exact directory layout:

```text
tools/<tool_name>/
├── __init__.py           # Package marker
├── manifest.toml         # Declarative metadata, parameter contracts, curriculum recipes, and protocol theory
├── adapter.py            # ToolAdapter class (validate_install, build_command, parse_output, sanitize_output)
└── cli.py                # (Optional) Pure-Python CLI entry point for bundled tools (e.g. dnspython)

tests/fixtures/mock_tools/<tool_name>.(json|jsonl|txt)  # Raw sample output captured from tool
tests/unit/test_parsers/test_<tool_name>_parser.py     # Hermetic pytest unit test suite
```

---

## 2. Declarative Manifest Contract (`manifest.toml`)

The manifest defines the tool's integration points, input/output schemas, parameter configurations, and educational syllabus.

```toml
[meta]
name = "<tool_name>"
description = "Detailed multi-sentence explanation of tool purpose, mechanics, and capabilities."
one_line_summary = "Concise action-oriented summary for UI headers and tool selector badges."
category = "Web Application Analysis" # Primary UI grouping category
categories = ["web", "recon", "fuzzing", "vulnerability"] # Multi-tag categorization
binary = "<binary_name>" # Executable name verified via shutil.which()

[modes]
learning = true
power = true

[input]
accepts = ["network.host", "network.service", "web.endpoint"] # Must match schemas from SCHEMA_REGISTRY.md

[output]
produces = ["web.endpoint", "audit.misconfig", "vulnerability.found"] # Emitted finding schemas

[learning]
enabled = true

[[learning.recipes]]
name = "Standard Directory Discovery"
difficulty = "Beginner" # Beginner | Intermediate | Advanced
description = "Enumerate common directories and sensitive configuration files on target server."
flags = ["-u", "{url}", "-w", "{wordlist:common_dirs}"]

[learning.recipes.theory]
concept = "HTTP Response Code Analysis & Forced Browsing"
explanation = """
1. What the tool does: Emits rapid HTTP GET requests for dictionary entries appended to the base URL.
2. Flag selection: '-u' defines the endpoint target; '-w' mounts the wordlist.
3. Response interpretation: Status 200 indicates accessible resources; 301/302 indicates redirects; 403 reveals protected administrative surfaces.
"""
packet_wire_summary = "Client GET /admin -> Server HTTP/1.1 200 OK (Content-Length: 1024)"
remediation = "Disable directory listings, enforce strict role-based access control, and remove exposed backup/test files."
```

### Supported Macro Variables in Recipe Flags:
* `{target}`: Target IP, hostname, or endpoint URL.
* `{url}`: Full formatted HTTP/HTTPS URL (e.g. `http://10.0.0.1:80`).
* `{ip}`: Target host IP address.
* `{domain}`: Domain name identifier.
* `{port}`: Target service port number.
* `{wordlist}` / `{wordlist:<name>}`: Centralized wordlist macro expanded by `cyguide.engine.wordlists`. Built-in names:
  - `common_dirs`: Top web directories and files.
  - `subdomains_500`: High-frequency DNS subdomains.
  - `common_params`: Frequent HTTP GET/POST parameter names.
  - `common_usernames`: Standard administrative and service usernames.
  - `common_passwords`: Default credentials and common passwords.

---

## 3. Tool Adapter Implementation (`adapter.py`)

Adapters inherit from `cyguide.engine.registry.ToolAdapter`:

```python
"""Adapter for <Tool Name>."""

import json
import shlex
import shutil
from typing import Any, AsyncIterator, Dict, List

from cyguide.engine.registry import ToolAdapter
from cyguide.engine.wordlists import substitute_wordlist_macros
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.web import WebEndpoint


class ToolNameAdapter(ToolAdapter):
    """Adapter for <Tool Name> integrating with CyGuide entity graph."""

    def validate_install(self) -> bool:
        """Verify the required binary exists on the system PATH."""
        return shutil.which("<binary_name>") is not None

    def sanitize_output(self, raw_stdout: str) -> str:
        """Strip tool-specific ASCII banners, progress bars, and noisy diagnostic headers.

        Invoked by CyGuide before sending scan logs to the AI explainer tutor.
        Reduces prompt token consumption and prevents confusion on smaller local LLMs.
        """
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            # Strip ASCII art banners or progress indicators
            if s.startswith("::") or "Progress: [" in s or s.startswith("____"):
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """Construct CLI arguments safely as an argument list (preventing shell injection)."""
        # 1. Extract target identifiers
        url = target.pik.get("url") or target.data.get("url")
        if not url:
            raise ValueError(f"Target finding {target.schema_type} missing valid URL.")

        # 2. Process user flags and expand wordlist macros
        raw_flags = params.get("raw_flags", "").strip()
        raw_flags, _ = substitute_wordlist_macros(raw_flags)
        flag_args = shlex.split(raw_flags) if raw_flags else []

        args = ["<binary_name>"]

        # 3. Enforce programmatic non-interactive & structured output flags
        if "-u" not in flag_args:
            args.extend(["-u", url])
        if "-oJ" not in flag_args and "--json" not in flag_args:
            args.append("--json")

        args.extend(flag_args)
        return args

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse streaming raw stdout into typed finding models with graph parent wiring."""
        cleaned = raw_stdout.strip()
        if not cleaned:
            return

        host_ip = target.pik.get("host_ip") or target.pik.get("ip") or target.data.get("host_ip")

        # 1. Parse JSON / JSONL output
        for line in cleaned.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue

            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            endpoint_url = item.get("url", "").strip()
            if endpoint_url:
                # Yield finding with parent host_ip preserved
                yield WebEndpoint.create(
                    url=endpoint_url,
                    host_ip=host_ip,
                    status_code=int(item.get("status", 200)),
                )
```

### Core Implementation Invariants:
1. **Never block interactively**: Enforce non-interactive flags (`--batch`, `-oJ`, `-q`, `-silent`, `--noninteractive`).
2. **Never invoke subshells**: Arguments must be constructed as a `List[str]`, never formatted as a single concatenated shell string.
3. **Prefer structured JSON/JSONL output**: Modern security tools (`nuclei`, `ffuf`, `searchsploit`, `dnspython`) output structured data. If a tool prints console banners before JSON, implement slice extraction:
   ```python
   start = cleaned.find("{")
   end = cleaned.rfind("}")
   if start != -1 and end != -1 and end > start:
       data = json.loads(cleaned[start : end + 1])
   ```
4. **Wordlist macro substitution**: If the tool takes wordlists, process flags through `substitute_wordlist_macros(raw_flags)` so users can write `{wordlist:common_dirs}` or `{wordlist}`.
5. **Auto-wire graph relationships**: Extract the target's primary keys (`host_ip`, `port`, `url`, `domain`, `cve_id`) and pass them to the `.create(...)` factory of emitted child findings. This ensures the SQLite entity graph auto-wires parent and child nodes seamlessly.
6. **Pure-Python adapters**: For tools implemented directly in Python (e.g. `dnspython`), `validate_install()` verifies the package can be imported, and `build_command()` invokes `sys.executable -m tools.<tool_name>.cli`.
7. **Strip tool noise with `sanitize_output()`**: Override `sanitize_output(self, raw_stdout: str) -> str` to strip tool-specific noise. CyGuide's core engine automatically cleans ANSI color escape sequences and invokes `adapter.sanitize_output(raw_output)` before feeding scan logs to the AI tutor.
8. **Handle non-zero exit codes**: Many security scanners (e.g. `nikto`, `nuclei`) return exit code 1 or 2 when vulnerabilities are discovered or minor network errors occur. `parse_output()` must parse valid partial or finding data even if the process exited with a non-zero status.

---

## 4. Hermetic Test Fixture & Parser Test Suite

Every adapter must have a hermetic unit test that runs in CI without requiring the real security binary to be installed on the host:

1. Save a sample output file to `tests/fixtures/mock_tools/<tool_name>.(json|jsonl|txt)`.
2. Implement `tests/unit/test_parsers/test_<tool_name>_parser.py`:
   - Test `validate_install()` returns a boolean.
   - Test `build_command()` properly formats target variables, user flags, and macro expansions.
   - Load the mock fixture text and test `parse_output()`.
   - Assert `len(findings) > 0`.
   - Assert specific field values, PIK dictionaries, data attributes, and parent relationship keys on the emitted findings.
   - Test handling of empty strings and malformed noisy output.
   - Test `sanitize_output()`: Verify that ASCII art banners, progress lines, or noisy headers are stripped while leaving scan findings intact.

---

## 5. Ecosystem Registration Checklist

When creating or significantly updating an adapter, update all corresponding touchpoints across the repository:

| Component | Target File | Required Update |
| :--- | :--- | :--- |
| **Diagnostics** | [`cyguide/engine/diagnostics.py`](../../cyguide/engine/diagnostics.py) | Add package manager installation hint to `INSTALLATION_HINTS`. |
| **System Installer** | [`scripts/install_deps.sh`](../../scripts/install_deps.sh) | Add tool to apt, pacman, dnf, zypper, apk, and brew; add binary release installer function (`install_<tool>_release`); update `verify_tools`. |
| **Docker Image** | [`Dockerfile`](../../Dockerfile) | Add package installation or binary release download to container build; copy `assets/ assets/`. |
| **Mock Fixture** | [`tests/fixtures/mock_tools/<tool>.(json\|jsonl\|txt)`](../../tests/fixtures/mock_tools) | Raw sample output fixture for hermetic tests. |
| **Parser Tests** | [`tests/unit/test_parsers/test_<tool>_parser.py`](../../tests/unit/test_parsers) | Unit tests verifying `validate_install`, `build_command`, `parse_output`, and `sanitize_output`. |
| **Schema Registry** | [`scripts/generate_schema_registry.py`](../../scripts/generate_schema_registry.py) | If emitting any new finding schemas, update parent/association heuristics and run `--check`. |
| **Documentation** | [`README.md`](../../README.md), [`docs/user/USER_MANUAL.md`](../../docs/user/USER_MANUAL.md) | Add the tool to the supported security tools list and package installation guides. |

---

## 6. Reference Tool Matrix

The 9 production adapters in CyGuide serve as standard reference implementations:

| Tool Name | Binary / Module | Primary Finding Schemas Emitted | Category | Reference Source |
| :--- | :--- | :--- | :--- | :--- |
| **nmap** | `nmap` | `network.host`, `network.service` | Network Discovery & Port Scanning | [`tools/nmap/`](../../tools/nmap) |
| **whois** | `whois` | `domain.info`, `network.netblock`, `network.host` | OSINT & Domain Intelligence | [`tools/whois/`](../../tools/whois) |
| **gobuster** | `gobuster` | `web.endpoint` | Web Directory & DNS Brute-Forcing | [`tools/gobuster/`](../../tools/gobuster) |
| **nikto** | `nikto` | `web.vulnerability`, `vulnerability.found` | Web Server Vulnerability Scanning | [`tools/nikto/`](../../tools/nikto) |
| **subfinder** | `subfinder` | `dns.record` | Passive Subdomain Enumeration | [`tools/subfinder/`](../../tools/subfinder) |
| **dnspython** | Pure-Python (`dns.resolver`) | `dns.record` | DNS Resolution & Zone Transfers | [`tools/dnspython/`](../../tools/dnspython) |
| **searchsploit** | `searchsploit` | `exploit.reference` | Exploit-DB Offline Querying | [`tools/searchsploit/`](../../tools/searchsploit) |
| **ffuf** | `ffuf` | `web.endpoint`, `audit.misconfig` | High-Performance Web Fuzzing | [`tools/ffuf/`](../../tools/ffuf) |
| **nuclei** | `nuclei` | `web.technology`, `audit.misconfig`, `vulnerability.found` | Template-Based Vulnerability Scanning | [`tools/nuclei/`](../../tools/nuclei) |
