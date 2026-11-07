## Summary

<!-- Briefly describe the purpose of this PR and what problem it solves. -->

Fixes # <!-- Issue number if applicable -->

---

## Type of Change

- [ ] Bug fix (non-breaking fix for an existing issue)
- [ ] New feature (non-breaking enhancement)
- [ ] New tool adapter (`tools/<tool_name>/`)
- [ ] Core engine modification (`cyguide/engine/` or `cyguide/schemas/`)
- [ ] UI / CSS improvement (`cyguide/ui/`)
- [ ] Documentation update
- [ ] CI / Workflow / Build system change

---

## Architectural Tier Check

- [ ] **Tier 1 (Core Engine & Schemas)**: Modifies `store.py`, `registry.py`, `canonicalize.py`, `base.py`, or `paths.py`. Requires CODEOWNERS review from `@h45sh`.
- [ ] **Tier 2 (Adapters & Pipelines)**: Modifies `executor.py`, `gateway.py`, or tool adapters in `tools/*/`.
- [ ] **Tier 3 (UI & Docs)**: Presentation, CSS, documentation, or learning mode recipes.

---

## Pre-Merge Verification Checklist

- [ ] My code adheres to the project code standards (formatted via `ruff format` and linted via `ruff check`).
- [ ] I have executed the automated verification script: `./scripts/verify.sh`.
- [ ] All 170+ logic tests pass without regressions.
- [ ] If finding schemas in `cyguide/schemas/` were added or modified, schema documentation has been regenerated and committed (`python3 scripts/generate_schema_registry.py`).
- [ ] No decorative emojis have been added in documentation, code, or commit messages.
- [ ] For tool adapters: External CLI commands are passed strictly as argument lists without `shell=True`.
- [ ] Diagnostic health check passes: `cyg check --json`.
