# Security Policy

## Supported Versions

CyGuide receives active security updates and vulnerability patches on the current default release branch and latest PyPI release. 

| Release Channel | Supported | Notes |
| :--- | :---: | :--- |
| **Latest Release / Default Branch (`main`)** | **Yes** | Active security support and patches. |
| **Prior Releases** | **Best Effort** | Security fixes are backported or rolled into the next minor/patch release. |

We recommend always running the latest packaged release (`pip install -U cyguide`) or pulling the latest tagged release.

---

## Reporting a Vulnerability

The CyGuide team takes security seriously. If you discover a vulnerability, potential security bug, or weakness in CyGuide (including command injection vectors in tool adapters, path traversal in export/import routines, or credential exposure), please do not report it through a public GitHub issue.

### Preferred Reporting Channel

* **GitHub Private Vulnerability Reporting**: Navigate to the [CyGuide Security Advisory tab](https://github.com/h45sh/cyguide/security/advisories/new) and submit a private report.
* **Direct Maintainer Contact**: If the advisory portal is unavailable, contact the project maintainer directly at `harshwardhan@h45sh.com` with the subject line `[SECURITY] CyGuide Vulnerability Report`.

### What to Include

To help us assess and resolve the issue quickly, please provide:
1. A clear description of the vulnerability and its potential impact.
2. Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
3. The affected CyGuide version and operating system environment.
4. Any potential mitigations or remediation patches you have identified.

### Response Timeline

* **Acknowledgment**: Within 48 hours of initial receipt.
* **Triage & Assessment**: Within 5 business days, confirming whether the report is accepted or requires further detail.
* **Remediation & Advisory Release**: A coordinated release date will be scheduled once a patch is tested. We aim to release critical fixes within 14 days of confirmation.

Credit will be given in the release notes and security advisories for responsibly disclosed vulnerabilities, unless the reporter requests anonymity.

---

## Security Architecture & Scope

CyGuide operates as an orchestration, analysis, and educational harness executing external cybersecurity binaries on the local host. When assessing potential vulnerabilities, consider the following threat model boundaries:

1. **Subprocess Execution**: CyGuide tool adapters must always pass arguments as structured argument lists (`List[str]`) directly to `asyncio.create_subprocess_exec` rather than invoking a shell with `shell=True`. Vulnerabilities where arbitrary target parameters or unescaped macro tokens lead to unintended shell execution on the host are in-scope.
2. **Environment Sanitization & Credential Protection**: Subprocess environments must be scrubbed (`sanitize_subprocess_env`) of operator secrets (`CYGUIDE_*`, `OPENAI_*`, `ANTHROPIC_*`, `AWS_*`, `GITHUB_*`, `SSH_PRIVATE_KEY`). Flaws where external CLI tools can read operator API tokens from child `/proc/<PID>/environ` are in-scope.
3. **Session Database Isolation & Hardening**: Exported `.db` files contain findings and command metadata. SQLite database connections enforce `PRAGMA trusted_schema = OFF` and parameterized queries. Deserialization flaws leading to path traversal, arbitrary file writes, or trigger execution are in-scope.
4. **Network Gateways & Cloud Metadata SSRF Protection**: CyGuide provides target validation and Link-Local/cloud metadata blocking (`169.254.0.0/16`, IMDSv2, cloud metadata hostnames). Bypasses that trick the gateway into dispatching requests to cloud metadata services or bypassing target CIDR boundary checks are considered security issues.
5. **AI Prompt Injection & Boundary Delimiters**: Parsing untrusted stdout/stderr from external security tools encapsulates content within `<untrusted_scan_output>` XML boundary tags with closing-tag sanitization and credential redaction (PEM keys, tokens, passwords). Exploits that achieve prompt injection override or credential exfiltration are in-scope.
6. **Local Filesystem Permissions**: Sensitive settings (`settings.json`) and scratchpads (`scratchpad.md`) enforce atomic `0o600` permissions to prevent TOCTOU race conditions.

