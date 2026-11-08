# Security Policy

## Supported Versions

CyGuide receives active security updates and vulnerability patches on the following release branches:

| Version | Supported     |
| :------ | :------------ |
| 1.7.x   | Yes (Current) |
| < 1.7.0 | No            |

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

CyGuide operates as an orchestration and analysis harness executing external cybersecurity binaries on the local host. When assessing potential vulnerabilities, consider the following threat model boundaries:

1. **Subprocess Execution**: CyGuide tool adapters must always pass arguments as structured argument lists (`List[str]`) rather than invoking a shell with `shell=True`. Vulnerabilities where arbitrary target parameters lead to unintended command execution on the host are in-scope.
2. **Session Database Isolation**: Exported `.db` files contain findings and command metadata. SQLite database deserialization must prevent path traversal, arbitrary file writes, or SQL injection.
3. **Local Scope & Network Gateways**: CyGuide provides target CIDR boundary checks. Bypasses that lead to scanning unintended IP ranges are considered security issues.
4. **Third-Party Tool Output**: Parsing untrusted stdout/stderr from external security tools must not lead to terminal escape sequence injections or crash the host process.
