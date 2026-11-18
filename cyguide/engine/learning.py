"""LearningSession: Deep module encapsulating interactive single-tool learning workflows.

Coordinates tool selection, recipe binding, execution lifecycles, structured finding
extraction, and AI educational tutoring behind a unified seam.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable, List, Optional, Set, Tuple
from uuid import UUID, uuid4

from cyguide.engine.execution_session import ExecutionSession
from cyguide.engine.explainer import ExplanationTutor
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.reporter import SessionReportService
from cyguide.engine.session import InvestigationSession
from cyguide.engine.store import GraphStore
from cyguide.engine.wordlists import substitute_wordlist_macros
from cyguide.schemas.power import ActionRequest, ActionSource

__all__ = [
    "BriefingChunkEvent",
    "BriefingCompletedEvent",
    "BriefingStartedEvent",
    "InvestigationSession",
    "LearningEvent",
    "LearningSession",
    "RecipeBinding",
    "ResolvedInvocation",
    "ScanCompletedEvent",
    "ScanOutputChunkEvent",
    "ScanStartedEvent",
    "ToolLearningContext",
    "TutorCommandResult",
    "TutorStreamChunk",
]


@dataclass(frozen=True)
class ResolvedInvocation:
    """Resolved command parameters and execution metadata."""

    tool_name: str
    target: str
    flags: str
    cmd_str: str
    recipe_idx: Optional[int] = None


class RecipeBinding:
    """Deep module resolving tool recipes, selected flags, and target macros."""

    @staticmethod
    def resolve(
        manifest: Any,
        target: str,
        flags_used: str = "",
        selected_flags: Optional[Set[str]] = None,
        recipe_idx: Optional[int] = None,
    ) -> ResolvedInvocation:
        """Resolve command flags, macro replacements ({url}, {target}, wordlists), and recipe binding."""
        target_val = target.strip()
        if not target_val:
            raise ValueError("Target address or host cannot be empty")

        tool_name = manifest.meta.name if manifest else "tool"
        flags_str = flags_used.strip()

        # If flags_str not provided but recipe_idx is specified, populate from recipe
        if (
            not flags_str
            and recipe_idx is not None
            and manifest
            and hasattr(manifest, "learning")
            and manifest.learning
            and manifest.learning.recipes
        ):
            if 0 <= recipe_idx < len(manifest.learning.recipes):
                r_flags = manifest.learning.recipes[recipe_idx].flags
                flags_str = " ".join(r_flags) if isinstance(r_flags, list) else str(r_flags)

        # Perform macro substitution
        preview_flags = (
            flags_str.replace("{url}", target_val)
            .replace("{target}", target_val)
            .replace("{domain}", target_val)
            .replace("{port}", "80")
        )
        preview_flags, _ = substitute_wordlist_macros(preview_flags)

        if (
            "{url}" in flags_str
            or "{target}" in flags_str
            or "{domain}" in flags_str
        ):
            full_flags = preview_flags.strip()
            cmd_str = f"{tool_name} {preview_flags}".strip().replace("  ", " ")
        else:
            full_flags = f"{preview_flags} {target_val}".strip()
            cmd_str = f"{tool_name} {preview_flags} {target_val}".strip().replace("  ", " ")

        # Auto-detect matching recipe index if not explicitly provided
        matched_recipe_idx = recipe_idx
        if (
            matched_recipe_idx is None
            and manifest
            and hasattr(manifest, "learning")
            and manifest.learning
            and manifest.learning.recipes
        ):
            active_flags = selected_flags if selected_flags is not None else set(flags_str.split())
            for idx, r in enumerate(manifest.learning.recipes):
                if set(getattr(r, "flags", [])) == active_flags:
                    matched_recipe_idx = idx
                    break

        return ResolvedInvocation(
            tool_name=tool_name,
            target=target_val,
            flags=full_flags,
            cmd_str=cmd_str,
            recipe_idx=matched_recipe_idx,
        )


@dataclass
class ToolLearningContext:
    """Metadata and quickstart documentation for a selected tool in Learning Mode."""

    tool_name: str
    manifest: Any
    is_installed: bool
    binary: str
    category: str
    summary: str
    description: str
    produces: List[str]
    recipes: List[Any]
    welcome_markdown: str

    @property
    def name(self) -> str:
        return self.tool_name

    @property
    def welcome_md(self) -> str:
        return self.welcome_markdown


# --- Typed Stream Events ---


@dataclass
class LearningEvent:
    """Base event emitted during a learning scan or briefing."""

    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass
class ScanStartedEvent(LearningEvent):
    run_count: int = 0
    cmd_str: str = ""
    header_text: str = ""
    timestamp: str = ""


@dataclass
class ScanOutputChunkEvent(LearningEvent):
    chunk: str = ""


@dataclass
class ScanCompletedEvent(LearningEvent):
    duration_seconds: float = 0.0
    footer_text: str = ""


@dataclass
class BriefingStartedEvent(LearningEvent):
    placeholder: str = "*[Analyzing scan results & generating educational breakdown...]*"


@dataclass
class BriefingChunkEvent(LearningEvent):
    chunk: str = ""


@dataclass
class BriefingCompletedEvent(LearningEvent):
    full_text: str = ""


@dataclass
class TutorCommandResult:
    """Result of evaluating a tutor slash command."""

    handled: bool
    command: str = ""
    action: Optional[str] = None  # "clear", "copy", "exit", "toggle_ai", "switch_recipes"
    message: str = ""
    arg: str = ""


@dataclass
class TutorStreamChunk:
    """A streamed, paced AI tutor response chunk with accumulated state."""

    chunk: str = ""
    accumulated: str = ""
    is_fallback: bool = False
    is_error: bool = False


class LearningSession:
    """The deep module managing single-tool interactive learning investigations.

    Encapsulates tool selection, recipe binding, process execution, structured
    finding extraction, and AI educational tutoring behind a unified seam.
    """

    def __init__(
        self,
        store: GraphStore,
        registry: ToolRegistry,
        execution: ExecutionSession,
        explainer: Optional[ExplanationTutor] = None,
        session_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
    ):
        self.store = store
        self.registry = registry
        self.execution = execution
        self.explainer = explainer
        self.session_id = session_id or uuid4()
        self.workspace_id = workspace_id

        # Learning state
        self.active_tool: Optional[str] = None
        self.active_recipe_idx: Optional[int] = None
        self.run_count: int = 0
        self.log_buffer: List[str] = []
        self.explanation_buffer: str = ""
        self.ai_enabled: bool = True
        self.scan_in_progress: bool = False
        self.current_job_id: Optional[UUID] = None

    def _resolve_tool_context(
        self, tool_name: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Any]]:
        """Resolve tool category and adapter from registry."""
        target_name = tool_name or self.active_tool
        if not target_name or not self.registry:
            return None, None
        tool_data = self.registry.get_tool(target_name)
        if not tool_data:
            return None, None
        manifest = tool_data.get("manifest")
        adapter = tool_data.get("adapter")
        category = None
        if manifest and hasattr(manifest, "meta"):
            category = getattr(manifest.meta, "category", None) or (
                manifest.meta.categories[0]
                if getattr(manifest.meta, "categories", None)
                else None
            )
        return category, adapter

    def select_tool(self, tool_name: str) -> Optional[ToolLearningContext]:
        """Select a tool and return its resolved learning context."""
        self.active_tool = tool_name
        self.active_recipe_idx = None
        if not self.registry:
            return None
        tool_data = self.registry.get_tool(tool_name)
        if not tool_data:
            return None
        manifest = tool_data.get("manifest")

        binary = manifest.meta.binary if manifest else tool_name
        bin_path = shutil.which(binary)
        is_installed = bool(bin_path)

        summary = (
            manifest.meta.one_line_summary or "Security inspection and analysis tool."
            if manifest
            else "Security inspection and analysis tool."
        )
        description = (
            manifest.meta.description or summary
            if manifest
            else summary
        )
        category = "tool"
        if manifest and hasattr(manifest, "meta"):
            category = (
                getattr(manifest.meta, "category", None)
                or (
                    manifest.meta.categories[0]
                    if getattr(manifest.meta, "categories", None)
                    else None
                )
                or "tool"
            )
        produces = (
            manifest.output.get("produces", [])
            if manifest and hasattr(manifest, "output") and manifest.output
            else []
        )
        recipes = (
            manifest.learning.recipes
            if manifest and hasattr(manifest, "learning") and manifest.learning
            else []
        )

        name_display = manifest.meta.name.upper() if manifest else tool_name.upper()
        welcome_md = (
            f"# ◆ {name_display}\n\n"
            f"{summary}\n\n"
            "### Quick Start Guide\n"
            "1. **Choose a Workflow Recipe** from the sidebar on the left, or configure Target and Flags.\n"
            "2. Click **▶ RUN SCAN** (or press Enter) to execute the security tool.\n"
            "3. Raw output streams in **Raw Output**, while live AI explanations stream here in real time.\n\n"
            "### Keyboard Shortcuts & Hidden Features\n"
            "* **`Alt+[` / `Alt+]` (or `Alt+{` / `Alt+}`)**: Shrink and expand sidebar width smoothly.\n"
            "* **`Ctrl+B`**: Toggle sidebar visibility (show or collapse).\n"
            "* **`Ctrl+Left` / `Ctrl+Right`**: Cycle between tabs (*Explanation* ↔ *Raw Output* ↔ *Recipes*).\n"
            "* **`● AI: ON / OFF`**: Toggle live automated AI explanations in the toolbar.\n"
            "* **`COPY` / `Ctrl+Y`**: Copy all explanations to clipboard (`Ctrl+C` copies active mouse selection).\n"
            "* **AI Tutor & Slash Commands**: Ask any question in the bottom dock, or run commands:\n"
            "  - `/summary` — Summarize scan findings and risk profile\n"
            "  - `/flags` — Explain command-line flags and syntax\n"
            "  - `/recipes` — List workflow recipes with security best practices\n"
            "  - `/info` — Tool background, capabilities, and defense insights\n"
            "  - `/help` — View available tutor commands\n"
            "* **`F1`**: Open full Keyboard Shortcuts & Hotkeys help dialog.\n"
            "* **`Esc`**: Return to Tool Browser.\n"
        )

        return ToolLearningContext(
            tool_name=tool_name,
            manifest=manifest,
            is_installed=is_installed,
            binary=binary,
            category=category,
            summary=summary,
            description=description,
            produces=produces,
            recipes=recipes,
            welcome_markdown=welcome_md,
        )

    def resolve_invocation(
        self,
        target: str,
        flags_used: str = "",
        selected_flags: Optional[Set[str]] = None,
        recipe_idx: Optional[int] = None,
    ) -> ResolvedInvocation:
        """Delegate parameter resolution and macro expansion to RecipeBinding."""
        tool_data = self.registry.get_tool(self.active_tool) if self.active_tool else None
        manifest = tool_data.get("manifest") if tool_data else None
        return RecipeBinding.resolve(
            manifest=manifest,
            target=target,
            flags_used=flags_used,
            selected_flags=selected_flags,
            recipe_idx=recipe_idx if recipe_idx is not None else self.active_recipe_idx,
        )

    async def run_scan(
        self,
        target: str,
        flags_used: str = "",
        selected_flags: Optional[Set[str]] = None,
        recipe_idx: Optional[int] = None,
        on_raw_chunk: Optional[Callable[[str], Any]] = None,
    ) -> AsyncIterator[LearningEvent]:
        invocation = self.resolve_invocation(
            target=target,
            flags_used=flags_used,
            selected_flags=selected_flags,
            recipe_idx=recipe_idx,
        )
        self.active_recipe_idx = invocation.recipe_idx

        self.scan_in_progress = True
        self.run_count += 1
        t_start = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Format terminal prompt header: clean prompt box with colorful command on next line
        prompt_top = f"\x1b[90m┌─[\x1b[0m\x1b[1;36mrun #{self.run_count}\x1b[0m\x1b[90m]─[\x1b[0m\x1b[33m{timestamp}\x1b[0m\x1b[90m]\x1b[0m"
        prompt_cmd = f"\x1b[90m└─\x1b[0m\x1b[1;32m>\x1b[0m \x1b[1;37m{invocation.cmd_str}\x1b[0m"
        log_header = (
            f"\n\n{prompt_top}\n{prompt_cmd}\n\n"
            if self.log_buffer
            else f"{prompt_top}\n{prompt_cmd}\n\n"
        )
        self.log_buffer.append(log_header)

        yield ScanStartedEvent(
            run_count=self.run_count,
            cmd_str=invocation.cmd_str,
            header_text=log_header,
            timestamp=timestamp,
        )

        async def _handle_chunk(text: str) -> None:
            self.log_buffer.append(text)
            if on_raw_chunk:
                try:
                    res = on_raw_chunk(text)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass

        action = ActionRequest(
            session_id=self.session_id,
            tool_name=self.active_tool or invocation.tool_name,
            params={"raw_flags": invocation.flags},
            triggered_by=ActionSource.USER,
        )

        try:
            if self.execution:
                self.current_job_id = await self.execution.dispatch(
                    action=action,
                    on_chunk=_handle_chunk,
                )
                job_task = self.execution.get_running_task(self.current_job_id)
                if job_task:
                    await asyncio.shield(job_task)
            else:
                await _handle_chunk(f"Simulated execution for {action.tool_name}\n")

            elapsed = time.time() - t_start
            footer = f"\n\x1b[90m✔ Process finished in {elapsed:.1f}s\x1b[0m\n"
            self.log_buffer.append(footer)

            yield ScanCompletedEvent(
                duration_seconds=elapsed,
                footer_text=footer,
            )

            # AI Briefing Phase
            if self.ai_enabled and self.explainer:
                yield BriefingStartedEvent()

                try:
                    _ui_findings, structured_llm = await self.extract_structured_findings()
                except Exception:
                    structured_llm = None

                raw_output = "".join(self.log_buffer[-80:])
                briefing_buffer = ""
                active_tool_name = self.active_tool or invocation.tool_name
                tool_category, tool_adapter = self._resolve_tool_context(active_tool_name)

                async for chunk in self.explainer.generate_scan_briefing(
                    tool_name=active_tool_name,
                    cmd_str=invocation.cmd_str,
                    scan_output=raw_output,
                    structured_findings=structured_llm,
                    tool_category=tool_category,
                    tool_adapter=tool_adapter,
                ):
                    briefing_buffer += chunk
                    yield BriefingChunkEvent(chunk=chunk)

                yield BriefingCompletedEvent(full_text=briefing_buffer)

        finally:
            self.scan_in_progress = False

    async def stop_scan(self) -> bool:
        """Terminate active tool scan."""
        killed = False
        if self.current_job_id:
            killed = await self.execution.kill_job(self.current_job_id)
        self.scan_in_progress = False
        stop_msg = "\n[!] Scan stopped by user.\n"
        self.log_buffer.append(stop_msg)
        return killed

    async def extract_structured_findings(
        self,
        store: Optional[GraphStore] = None,
        session_id: Optional[Any] = None,
    ) -> Tuple[str, str]:
        """Query GraphStore for session nodes and format both a UI card summary and an LLM prompt block."""
        target_store = store or self.store
        target_session_id = session_id or self.session_id
        if not target_store or not target_session_id:
            return "*No structured findings in current session yet.*", "None"
        return await SessionReportService(target_store).extract_structured_findings(
            str(target_session_id)
        )

    async def get_database_targets(self, workspace_id: Optional[str] = None) -> List[str]:
        """Fetch all unique network targets (IPs, hostnames, domains, URLs) from the database."""
        if not self.store:
            return []

        target_ws = workspace_id or (str(self.workspace_id) if self.workspace_id else None)
        nodes = []
        if target_ws:
            nodes = await self.store.get_workspace_nodes(target_ws)
        elif self.session_id:
            nodes = await self.store.get_all_nodes(str(self.session_id))

        targets: Set[str] = set()
        for node in nodes:
            schema_type = node.get("schema_type", "")
            pik_val = node.get("pik_json", "{}")
            try:
                pik = json.loads(pik_val) if isinstance(pik_val, str) else (pik_val or {})
            except Exception:
                pik = {}
            if schema_type == "network.host" and "ip" in pik:
                targets.add(str(pik["ip"]))
            elif schema_type in ("dns.record", "domain.info"):
                for key in ("domain", "host", "name"):
                    if key in pik:
                        targets.add(str(pik[key]))
            elif schema_type == "web.endpoint" and "url" in pik:
                targets.add(str(pik["url"]))
        return sorted(list(targets))

    async def sweep_targets(
        self,
        targets: Optional[List[str]] = None,
        flags_used: str = "",
        selected_flags: Optional[Set[str]] = None,
        recipe_idx: Optional[int] = None,
        on_raw_chunk: Optional[Callable[[str], Any]] = None,
    ) -> AsyncIterator[LearningEvent]:
        """Sweep through multiple targets sequentially using the active tool and recipe.

        If targets is None or empty, targets will be queried from the database.
        """
        resolved_targets = targets if targets is not None else await self.get_database_targets()
        for target in resolved_targets:
            async for event in self.run_scan(
                target=target,
                flags_used=flags_used,
                selected_flags=selected_flags,
                recipe_idx=recipe_idx,
                on_raw_chunk=on_raw_chunk,
            ):
                yield event

    def evaluate_slash_command(
        self, raw_input: str, active_flags_str: str = ""
    ) -> Optional[TutorCommandResult]:
        """Evaluate slash commands (/help, /model, /recipes, /summary, /flags, /ai, /clear, /bye)."""
        stripped = raw_input.strip()
        if not stripped.startswith("/"):
            return None

        parts = stripped.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/clear":
            self.explanation_buffer = ""
            return TutorCommandResult(handled=True, command=cmd, action="clear")

        if cmd == "/copy":
            return TutorCommandResult(handled=True, command=cmd, action="copy")

        if cmd in ("/bye", "/exit", "/quit"):
            return TutorCommandResult(handled=True, command=cmd, action="exit")

        if cmd in ("/?", "/help"):
            menu = (
                self.explainer.format_help_menu()
                if self.explainer
                else ExplanationTutor.format_help_menu()
            )
            return TutorCommandResult(handled=True, command=cmd, message=menu)

        if cmd in ("/model", "/show"):
            info = (
                self.explainer.format_model_info(self.active_tool, len(self.log_buffer))
                if self.explainer
                else f"Active Tool: {self.active_tool}"
            )
            return TutorCommandResult(handled=True, command=cmd, message=info)

        if cmd in ("/recipes", "/recipies", "/recipe"):
            tool_data = self.registry.get_tool(self.active_tool) if self.active_tool else None
            manifest = tool_data.get("manifest") if tool_data else None
            recipes_text = (
                f"### ◆ Available Recipes for `{self.active_tool or 'Current Tool'}`\n\n"
            )
            if manifest and hasattr(manifest, "learning") and manifest.learning and manifest.learning.recipes:
                for r in manifest.learning.recipes:
                    flags_disp = " ".join(r.flags) if isinstance(r.flags, list) else str(r.flags)
                    recipes_text += f"- **{r.name}** (`{flags_disp}`): {r.description}\n"
            else:
                recipes_text += "*No pre-configured workflow recipes found for this tool.*"

            return TutorCommandResult(
                handled=True,
                command=cmd,
                action="switch_recipes",
                message=recipes_text,
            )

        if cmd == "/ai":
            if arg in ("on", "enable", "1", "true"):
                self.ai_enabled = True
            elif arg in ("off", "disable", "0", "false"):
                self.ai_enabled = False
            else:
                self.ai_enabled = not self.ai_enabled

            state_desc = "enabled" if self.ai_enabled else "turned off"
            msg = f"> **[AI Tutor]** AI Explanations are now **{state_desc}**."
            return TutorCommandResult(
                handled=True,
                command=cmd,
                action="toggle_ai",
                message=msg,
                arg=state_desc,
            )

        if cmd in ("/summary", "/findings"):
            return TutorCommandResult(
                handled=False,
                command=cmd,
                message="Please provide a concise educational summary of the scan results, discovered open ports, and potential attack surface.",
            )

        if cmd == "/flags":
            flags_display = f"'{active_flags_str}'" if active_flags_str else "standard default flags"
            question = f"Please explain what the flags {flags_display} do for the tool '{self.active_tool}' and when a security analyst would use them."
            return TutorCommandResult(
                handled=False,
                command=cmd,
                message=question,
            )

        # Unknown command
        unknown_msg = f"> [!] Unknown command: `{cmd}`. Type `/help` to see available slash commands."
        return TutorCommandResult(handled=True, command=cmd, message=unknown_msg)

    def _resolve_tool_context(
        self, tool_name: Optional[str]
    ) -> Tuple[Optional[str], Optional[Any]]:
        """Resolve category and ToolAdapter instance for a tool name from the registry."""
        if not tool_name or not self.registry:
            return None, None
        try:
            tool_data = self.registry.get_tool(tool_name)
            if not tool_data:
                return None, None
            manifest = tool_data.get("manifest")
            adapter = tool_data.get("adapter")
            category = getattr(manifest.meta, "category", None) if manifest and hasattr(manifest, "meta") else None
            return (category.lower() if category else None, adapter)
        except Exception:
            return None, None

    async def query_tutor(
        self,
        question: str,
    ) -> AsyncIterator[str]:
        """Query the AI tutor with contextually enriched scanner output."""
        if not self.ai_enabled:
            return

        scan_output = "".join(self.log_buffer[-60:]) if self.log_buffer else None
        tool_tag = self.active_tool or "General Security"
        tool_category, tool_adapter = self._resolve_tool_context(self.active_tool)

        if not self.explainer:
            yield (
                f"Hello! I'm your CyGuide cybersecurity tutor. "
                f"I'm here to help you with `{tool_tag}`. "
                "You can run a scan using the controls on the left, or ask me questions about network flags, discovered services, or vulnerabilities!"
            )
            return

        async for chunk in self.explainer.explain_scan(
            question=question,
            scan_output=scan_output,
            tool_name=tool_tag,
            tool_category=tool_category,
            tool_adapter=tool_adapter,
        ):
            yield chunk

    async def stream_tutor_response(
        self,
        question: str,
        update_interval: float = 0.04,
    ) -> AsyncIterator[TutorStreamChunk]:
        """Paced stream emitting throttled educational explanations with automatic fallback synthesis."""
        if not self.ai_enabled:
            return

        accumulated = ""
        last_emit = time.time()
        tool_tag = self.active_tool or "General Security"
        tool_category, tool_adapter = self._resolve_tool_context(self.active_tool)

        if not self.explainer:
            fallback = (
                f"Hello! I'm your CyGuide cybersecurity tutor. "
                f"I'm here to help you with `{tool_tag}`. "
                "You can run a scan using the controls on the left, or ask me questions about network flags, discovered services, or vulnerabilities!"
            )
            yield TutorStreamChunk(chunk=fallback, accumulated=fallback, is_fallback=True)
            return

        scan_output = "".join(self.log_buffer[-60:]) if self.log_buffer else None
        try:
            async for chunk in self.explainer.explain_scan(
                question=question,
                scan_output=scan_output,
                tool_name=tool_tag,
                tool_category=tool_category,
                tool_adapter=tool_adapter,
            ):
                accumulated += chunk
                now = time.time()
                if now - last_emit >= update_interval:
                    yield TutorStreamChunk(chunk=chunk, accumulated=accumulated)
                    last_emit = now
                await asyncio.sleep(0)

            if not accumulated.strip():
                fallback = (
                    f"Hello! I'm your CyGuide cybersecurity tutor. "
                    f"I'm here to help you with `{tool_tag}`. "
                    "You can run a scan using the controls on the left, or ask me questions about network flags, discovered services, or vulnerabilities!"
                )
                yield TutorStreamChunk(chunk=fallback, accumulated=fallback, is_fallback=True)
            else:
                yield TutorStreamChunk(chunk="", accumulated=accumulated)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            err_text = f"> [!] **Error getting explanation:** {str(e)}\n"
            yield TutorStreamChunk(chunk=err_text, accumulated=accumulated + err_text, is_error=True)

    def reload_explainer(self, explainer: Optional[ExplanationTutor] = None) -> None:
        """Update explainer subsystem reference."""
        self.explainer = explainer

    def reload_store(
        self, store: Optional[GraphStore] = None, session_id: Optional[UUID] = None
    ) -> None:
        """Update database store and session ID references."""
        self.store = store
        if session_id:
            self.session_id = session_id

    def clear_explanation(self) -> None:
        """Clear explanation buffer history."""
        self.explanation_buffer = ""

    def clear_output(self) -> None:
        """Clear log buffer history."""
        self.log_buffer.clear()
