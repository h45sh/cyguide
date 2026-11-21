# Domain Knowledge: Tool Adapters & Manifest Architecture (Tier 2)

## 1. Pluggable Tool Ecosystem
- **Smart Adapter / Stupid Framework**: The core engine knows nothing about specific CLI flags or binary output quirks. Each tool plugin encapsulates its behavior within `tools/<name>/manifest.toml` and `tools/<name>/adapter.py` (`cyguide/engine/adapter.py:L1`).
- **Strict Additive Evolution**: Supporting a new security tool is 100% additive—never modify engine, database, or UI source files to support a plugin.
- **Recipe & Manifest Standards**: Tool manifests are validated via `ToolManifest` schema (`cyguide/engine/manifest.py:L1`). Every recipe must define educational hints, safety classifications, target flag macros, and output format specs.
- **Standalone DevKit**: Consult `h45sh/cyguide-devkit` and `.agents/skills/adapter-authoring/` for automated scaffolding, schema validation, and curriculum authoring.

## 2. Output Parsing & Graph Wiring
- **Dual Streaming & Batch Parsing**: Adapters implement both line-by-line streaming parsers (for real-time UI terminal updates) and structured completion parsers (for JSON/XML artifact extraction).
- **Normalized Finding Schemas**: Parsed entities must inherit from Pydantic `BaseFinding` (`cyguide/schemas/base.py:L1`) ensuring uniform graph node attributes across heterogeneous scanners.
- **Output Sanitization Hook**: Adapters must implement `sanitize_output()` to strip banners, progress meters, and colored escape codes before LLM consumption.
