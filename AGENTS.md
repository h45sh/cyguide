# Agent Directives & Context Optimization

## Context Gate & Token Policy
1. **Never read raw full files for architectural discovery.** 
   - Consult `.t3-architecture-cache.md` first to locate classes, signatures, and contracts.
2. **Slice Reads:**
   - When inspecting implementations, use line-bounded ranges (`view_file` with `StartLine` and `EndLine`) targeting only the relevant function.
3. **Diff-Bounded Audits:**
   - Audit only `git diff` hunks or staged changes, not entire directory trees.
4. **Tier 0 Local Pre-flight:**
   - Run local tests/syntax checks (`pytest`, `ruff check`, `t3-gate --tier0`) in 50ms before invoking heavy subagents or reasoning chains.
5. **Concise Communication:**
   - Omit conversational filler, repeated boilerplate, and pleasantries. Focus on high-density technical findings.
