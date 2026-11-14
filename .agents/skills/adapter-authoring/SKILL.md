---
name: adapter-authoring
description: Expert skill for authoring comprehensive CyGuide tool adapters. Inspects CLI tools, authors typed manifest.toml with curriculum-grade recipes and protocol theory, implements adapter.py with JSON/regex streaming parsers and graph relation auto-wiring, and creates hermetic pytest fixtures.
---

# CyGuide Adapter Authoring Skill

This skill guides the creation of production-grade, deep tool adapters for CyGuide. Every tool in CyGuide is isolated into its own self-contained directory under `tools/<tool_name>/`.

---

## 1. Directory Structure Contract

Every tool plugin must adhere to this file layout:

```text
tools/<tool_name>/
├── __init__.py
├── manifest.toml         # Metadata, contracts, modes, and curriculum recipes
└── adapter.py            # ToolAdapter implementation (build_command + parse_output)

tests/fixtures/mock_tools/<tool_name>.(txt|json)  # Pre-recorded raw CLI output
tests/unit/test_parsers/test_<tool_name>_parser.py # Hermetic pytest unit test
```

---

## 2. Manifest Contract (`manifest.toml`)

The manifest defines the tool's integration points, input/output contracts, and educational syllabus.

```toml
[meta]
name = "<tool_name>"
description = "Detailed multi-sentence explanation of tool purpose and capabilities."
one_line_summary = "Concise action-oriented summary for UI headers"
category = "Web Enumeration" # Category for UI grouping (e.g., Network Reconnaissance, Vulnerability Assessment)
categories = ["web", "recon", "fuzzing"]
binary = "<binary_name>" # Checked via shutil.which()

[modes]
learning = true
power = true

[input]
accepts = ["network.host", "web.endpoint"] # Must match schemas from SCHEMA_REGISTRY.md

[output]
produces = ["web.technology", "audit.misconfig"] # Emitted finding schemas

[learning]
enabled = true

[[learning.recipes]]
name = "Standard Discovery"
difficulty = "Beginner" # Beginner | Intermediate | Advanced
description = "High-level goal of this specific scan recipe"
flags = ["-u", "{url}", "-w", "{wordlist:common_dirs}"]

[learning.recipes.theory]
concept = "Underlying networking or application protocol mechanism"
explanation = """
Deep educational breakdown explaining:
1. What the tool is doing under the hood at the packet or HTTP layer.
2. Why these specific flags were chosen.
3. What responses indicate success vs failure.
"""
packet_wire_summary = "Client GET /admin -> Server 200 OK / 403 Forbidden"
remediation = "Defensive hardening advice: how a sysadmin or SOC analyst remediates or detects this scan."
```

---

## 3. Adapter Implementation Contract (`adapter.py`)

All adapters inherit from `ToolAdapter` in [`cyguide/engine/adapter.py`](../../cyguide/engine/adapter.py).

### Core Rules:
1. **Never block interactively**: Always include non-interactive flags (`--batch`, `-oJ`, `-q`, etc.).
2. **Support JSON whenever available**: Modern tools (`nuclei`, `ffuf`, `searchsploit`) support JSON output (`-j`, `-oJ`, `--json`). Prefer JSON over regex for bulletproof parsing.
3. **Handle manual flags gracefully**: If user provided custom flags in `params.get("raw_flags")`, prioritize them while ensuring the binary and target are correctly placed.
4. **Auto-wire parent relations**: Always pass the `target` entity's IP/URL into the finding factory so parent and child nodes connect seamlessly in the SQLite graph.

### Skeleton Implementation:

```python
"""<Tool Name> adapter."""

import json
import shutil
from typing import Any, AsyncIterator, Dict, List

from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.vulnerability import AuditMisconfig


class ExampleAdapter(ToolAdapter):
    """Adapter for <tool_name>."""

    def validate_install(self) -> bool:
        return shutil.which("<binary_name>") is not None

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        raw_flags = params.get("raw_flags", "")
        # Construct arguments list...
        return ["<binary_name>", *raw_flags.split()]

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        context = context or {}
        for line in raw_stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Parse line (e.g. json.loads(line) or regex match)
            # Yield standardized typed finding:
            yield AuditMisconfig.create(
                target=target.pik.get("url", ""),
                check_id="example-check",
                title="Example Issue",
                severity="medium",
            )
```

---

## 4. Hermetic Test Fixture & Parser Test

Every adapter must have a hermetic test that runs in CI without requiring the real security binary to be installed:

1. Save a sample output file to `tests/fixtures/mock_tools/<tool_name>.txt` (or `.json`).
2. Implement `tests/unit/test_parsers/test_<tool_name>_parser.py`:
   - Load the fixture text.
   - Instantiate `<ToolName>Adapter`.
   - Run `findings = [f async for f in adapter.parse_output(sample_text, target=dummy_target)]`.
   - Assert `len(findings) > 0`.
   - Assert specific field values, PIKs, and parent relationships on the returned findings.
