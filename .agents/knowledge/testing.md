# Domain Knowledge: Testing Architecture & Quality Assurance (Tier 2)

## 1. Multi-Tier Testing Pyramid
- **Tier 0 Pre-Flight Invariants (`pytest -m tier0 -q`)**: Executes in $< 4.0\text{s}$ (target $< 3.5\text{s}$) with zero network, zero heavy DOM mounts, and zero disk I/O flakiness. Runs AST mechanical checks, SSRF boundary proofs, and core canonicalization invariants.
- **Tier 1 Algorithmic & Unit Contracts**: Parameterized contract tables (`SCHEMA_CONTRACT_CASES` in `tests/unit/test_schemas.py:L20`) and pure domain state controllers (`KeyProfileManager` in `tests/unit/test_config_state.py:L10`).
- **Tier 2 Universal Tool Adapter Fuzzing**: Syzkaller-inspired adversarial stream fuzzer (`tests/unit/test_parsers/test_fuzz_all_adapters.py:L53`) dynamically discovers all 9 tool adapters, verifying crash-resilience against malformed ANSI, truncated JSON, 20k-token payloads, and null bytes.
- **Tier 3 Integration & Headless Operator Proofs**: Complete headless Textual operator journeys (`tests/integration/test_tui_workflow_proof.py:L1`) verifying Power Mode, Tool Browser, and Guided Learning without requiring display servers.

## 2. AST Mechanical Architectural Gates (`tests/unit/test_architecture.py`)
- **Prohibited AST Nodes**: Mechanical enforcement prevents developer drift by failing CI if:
  - `shell=True` or `os.system` is introduced anywhere in the repository.
  - Direct `subprocess` calls are imported or executed inside `cyguide/ui/` or `tools/*/adapter.py`.
  - Unparameterized SQL format strings (`execute(f"...")` or `execute("..." % ...)`) are introduced.
  - Application private state (`_last_shortcuts_toggle_time`) is penetrated across module seams.

## 3. Mathematical Properties & State Machine Testing (`tests/unit/test_properties.py`)
- **State Machine Verification**: Hypothesis `GraphStoreStateMachine(RuleBasedStateMachine)` executes randomized interleaved sequences of workspace, session, finding, and archive operations, asserting `PRAGMA integrity_check == "ok"` and zero orphaned foreign edges after every transition.
- **SSRF Mathematical Proof**: Property tests prove 100% block rate across hex (`0xa9fea9fe`), decimal (`2852039166`), octal, IPv6 link-local, and cloud metadata DNS rebinding while guaranteeing zero false positives on benign public/internal IP ranges.

## 4. Anti-Flakiness Rules & DOM Decoupling
- **Decoupled Domain Controllers**: Never mount an entire Textual application and burn seconds in `pilot.pause()` sleeps just to verify domain logic (such as API key uniqueness or deletion fallback). Extract domain logic into pure controllers (`KeyProfileManager`) and test with sub-second property proofs.
- **Textual Yield Discipline**: When testing UI widgets, use `await pilot.pause()` exclusively to yield to Textual's event loop for layout calculation and event dispatching.
