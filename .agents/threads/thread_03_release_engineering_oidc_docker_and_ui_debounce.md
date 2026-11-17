# Thread Insight: Release Engineering, OIDC Trusted Publishing, Docker Hardening & Textual Debounce Resilience

- **Branch / PR**: `chore(main): release 1.10.0` (#24), `chore(release): bump version to 1.10.1` (commit `96471b9`), `fix(test): stabilize workspace and session list highlight debounce` (commit `766fca2`), and `ci: switch release-please to on-demand workflow_dispatch` (commit `a238680`)
- **Primary Domain**: `[Tooling | UI | Security | CLI]`
- **Author / Contributor**: `@h45sh`

---

## 1. Key Principles & Architectural Techniques Introduced

### 1.1. Decoupled, Tokenless PyPI Publishing via OIDC Trusted Publishers
- **The Architecture**: PyPI Trusted Publisher uses OpenID Connect (OIDC) tokens issued by GitHub Actions to authenticate release uploads without long-lived API keys or passwords.
- **The Reusable Workflow Trap**: PyPI's Trusted Publisher specification strictly checks the OIDC claim `job_workflow_ref`. When `release-please.yml` invoked `release.yml` via `workflow_call`, the claim reflected the caller workflow (`release-please.yml`), triggering an immediate `HTTP 400 Bad Request: Invalid token: workflow_call is not supported`.
- **Top-Level Event Decoupling**: Release orchestration is decoupled from packaging and publication:
  1. `release-please` handles Conventional Commit parsing, version increments, changelog generation, and creates the GitHub Release object.
  2. The GitHub Release event (`release: [published]`) natively triggers `.github/workflows/release.yml` as a top-level, standalone workflow.
  3. PyPI validates the exact registered workflow path (`.github/workflows/release.yml`) with zero token mismatch.

### 1.2. Hermetic Distribution Package Testing (`build --wheel` vs `pip install -e .`)
- **The Principle**: "Works on my machine" and "works in CI but breaks in production" are frequently caused by testing against editable installs (`pip install -e .`). Editable installs symlink to the repository source tree, which masks packaging omission bugs.
- **The Technique**: CI was re-architected to always build and install the real distribution wheel before running test suites or diagnostics:
  ```bash
  python -m build --wheel
  pip install dist/*.whl
  ./scripts/verify.sh
  cyg check --json
  ```
- **The Invariant**: If static assets (such as `.txt.gz` wordlists, schema templates, or data files) are missing from `pyproject.toml`'s package data or `MANIFEST.in`, CI fails immediately on PR, preventing broken packages from reaching PyPI or Docker Hub.

### 1.3. Multi-Stage Docker Context Whitelisting
- Root-level `.dockerignore` patterns must use explicit negative whitelisting (`assets/*` combined with `!assets/wordlists`) when selective directories are required in container layers.
- Docker multi-arch builds (`linux/amd64`, `linux/arm64`) with Buildx require explicit QEMU setup (`docker/setup-qemu-action@v4`) and deterministic asset staging to prevent build context inflation and layer cache misses.

### 1.4. Automated Downstream Branch Synchronization (`sync-main-to-dev.yml`)
- Solved the multi-branch synchronization burden by introducing an automated workflow that mirrors merged release commits from `main` to `dev` using fast-forward merges:
  - Listens on `push: branches: [main]`.
  - Runs in $\le 10\text{s}$, completely eliminating manual checkout/merge/push ceremonies for developers.

### 1.5. On-Demand Release Cadence (`workflow_dispatch`)
- Release Please was transitioned from eager `push: branches: [main]` triggers to on-demand execution (`workflow_dispatch`).
- Prevents persistent release PR clutter on GitHub while maintaining automated changelog extraction and semantic version tagging on demand.

---

## 2. Non-Obvious Insights & Codebase Realities

### 2.1. Textual Async Debounce Lifecycles & DOM Mount Race Conditions
- **The Mechanism**: In Textual applications, rapid keyboard navigation (`down`, `up`, `enter`) triggers `ListView.Highlighted` events that schedule debounced async tasks (`_ws_debounce_task`, `_sess_debounce_task` with $0.05\text{s}$ delays).
- **The Bug**: On loaded virtualized CI runners (e.g. `ubuntu-latest, Python 3.12`), a static `await pilot.pause(0.1)` or single task await in unit tests was non-deterministic.
  - When `show_workspace_details(ws_id)` runs, it clears and remounts session list children (`await sess_list.remove_children()`, `await sess_list.mount(*sess_items)`).
  - During the remount interval, `sess_list.index` is temporarily `None`. Asserting `assert sess_list.index == 0` during this slice failed with `AssertionError: assert None == 0`.
- **The Settle Protocol**: Never rely on static sleeps for asynchronous UI tests. Use an active settle loop that awaits in-flight debounce tasks, catches `asyncio.CancelledError`, and checks that the DOM has settled:
  ```python
  async def settle():
      for _ in range(20):
          if dashboard._ws_debounce_task and not dashboard._ws_debounce_task.done():
              try:
                  await dashboard._ws_debounce_task
              except asyncio.CancelledError:
                  pass
          if dashboard._sess_debounce_task and not dashboard._sess_debounce_task.done():
              try:
                  await dashboard._sess_debounce_task
              except asyncio.CancelledError:
                  pass
          await pilot.pause(0.05)
          if sess_list.index is not None and len(sess_list.children) > 0:
              break
  ```

### 2.2. Virtualized CI Runner Timing Variance
- Bare-metal dev machines run debounce and message pumps in single-digit milliseconds. Shared CI virtual machines experience CPU scheduling delays, stretching a $50\text{ms}$ debounce into $150\text{ms}+$. Test timeouts and settle loops must accommodate these 3x–5x latency spikes without failing.

### 2.3. Transitive Security Audit Flakiness
- Upstream vulnerability advisories (`pip-audit`) frequently report medium/low severity CVEs on transitive dev dependencies that have no upstream fix yet available.
- Setting `continue-on-error: true` for audit checks in routine PR validation keeps development unblocked while preserving audit output in CI logs.

---

## 3. Anti-Patterns & Outdated Techniques (What NOT to do)

1. **NEVER Use `pip install -e .` in CI Verification**:
   - Editable installs hide missing package data, uncommitted assets, and broken build manifests. Always build a distribution wheel and install the `.whl` file before testing.
2. **NEVER Invoke PyPI Publishing from a `workflow_call`**:
   - PyPI OIDC verification strictly disallows nested/reusable workflows. PyPI publish jobs must live in top-level workflows triggered directly by `release` or `workflow_dispatch`.
3. **NEVER Use Static Sleeps (`sleep(0.1)`) for Textual State Assertions**:
   - DOM updates, worker task execution, and debounce timers are asynchronous. Always await the specific `asyncio.Task` handles or employ bounded settle loops.
4. **NEVER Manually Rebase or Merge Bot Commits Across Branches**:
   - Bot commits (from Release Please) on `main` must be automatically propagated to `dev` via CI automation to prevent divergent branch histories.
5. **NEVER Keep Uncontrolled Open Release PRs Open Indefinitely**:
   - If an open release PR is continually modified by every small commit, it creates clutter and false CI triggers. Use on-demand release triggering.
6. **NEVER Package Uncompressed Wordlists or Raw Dumps in Wheels**:
   - Always store distributed wordlists in gzip format (`.txt.gz`) and ensure `MANIFEST.in` explicitly declares them.

---

## 4. Invariants & Performance Contracts to Preserve

| Component | Target Contract | Hard Invariant |
| :--- | :--- | :--- |
| **Release Authentication** | Zero long-lived secrets | PyPI and GHCR use strictly ephemeral OIDC tokens (`id-token: write`). |
| **Packaging Validation** | 100% packaged asset verification | CI installs and tests the built wheel artifact (`dist/*.whl`), never an editable install. |
| **CI Execution Time** | $\le 3\text{ minutes}$ per job | Fail-fast disabled for visibility; optimized dependency caching via `actions/setup-python@v7` (`cache: "pip"`). |
| **UI Debounce Settle Time** | $\le 1000\text{ms}$ total | Maximum 20 iterations at $0.05\text{s}$ pause; exits immediately upon DOM index resolution. |
| **Branch Alignment** | Fast-forward parity between `main` and `dev` | Auto-sync workflow runs within $10\text{s}$ of any push to `main`. |
| **Docker Build Reproducibility** | Multi-arch OCI compliant (`amd64` / `arm64`) | Exact tag pinning; build context whitelisted via `.dockerignore`. |
