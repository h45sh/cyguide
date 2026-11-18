# Domain Knowledge: Security Boundaries & Attack Surface Defense (Tier 2)

## 1. Gateway & SSRF Immunization
- **Deterministic Gateway Invariants**: All security commands dispatched by tools or operators must pass through `ActionGateway` (`cyguide/engine/gateway.py:L1`).
- **Blocked Targets**: `ActionGateway.BLOCKED_TARGETS` must never weaken SSRF filtering against:
  - IPv4 link-local ranges: `169.254.0.0/16`
  - AWS IMDSv2 metadata endpoints: `fd00:ec2::254`, `http://169.254.169.254`
  - Alibaba Cloud metadata endpoints: `100.100.100.200`
  - Decimal/Hex IP representations (`0x7f000001`, `2130706433`)
  - Cloud metadata DNS hostnames (`instance-data`, `metadata.google.internal`)
- **Safe Target Validation**: Targets must resolve to allowed public/lab IP scopes or pass operator domain validation rules.

## 2. Process & Environment Isolation
- **Subprocess Env Sanitization**: `sanitize_subprocess_env()` in `cyguide/engine/executor.py:L17` strips sensitive environment variables:
  - Repository / Provider keys: `CYGUIDE_*`, `OPENAI_*`, `ANTHROPIC_*`, `GEMINI_*`, `GROQ_*`
  - Cloud credentials: `AWS_*`, `GITHUB_*`, `GITLAB_*`
  - SSH authorization: `SSH_AUTH_SOCK`, `SSH_AGENT_PID`
- **Shell Injection Immunity**: Never construct shell commands via string interpolation (`f"{tool} {flags} {target}"`) or pass `shell=True`. Commands are strictly executed as argument lists (`List[str]`).
- **Untrusted Output Isolation**: Raw tool outputs can contain prompt injection payloads. Always wrap outputs in `<untrusted_scan_output>...</untrusted_scan_output>`.

## 3. Ephemeral Release Authentication & Packaging
- **Tokenless OIDC Publishing**: Automated releases to PyPI and GHCR utilize short-lived GitHub Actions OIDC tokens (`id-token: write`). Long-lived API tokens in repository secrets are prohibited.
- **Top-Level Workflow Rule**: PyPI OIDC verification strictly disallows nested or reusable workflows (`workflow_call`). Publish jobs must run directly inside top-level release workflows.
- **Distribution Package Verification**: Always build and verify real distribution wheels (`python -m build --wheel && pip install dist/*.whl`) in CI instead of editable installs (`pip install -e .`), preventing packaging omission bugs.
- **Atomic Private Permissions**: Sensitive files (`settings.json`, `scratchpad.md`) must be created atomically with mode `0o600` via `os.open` with `O_CREAT | O_WRONLY | O_TRUNC`.
