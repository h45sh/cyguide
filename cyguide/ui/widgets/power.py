"""Specialized widgets for Power Mode."""

import json
import os
import subprocess
from typing import Dict, Any, List, Optional
from textual import events
from textual.widgets import Tree, Static, Label, ListView, ListItem, Input, Rule
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from cyguide.schemas.power import JobStatus, JobStatusEnum


class EntityBrowser(Tree):
    """Hierarchical browser for findings in the current session."""

    def __init__(self, **kwargs):
        super().__init__("ENTITY BROWSER", **kwargs)
        self.root.expand()

    async def refresh_entities(self, nodes: List[Dict[str, Any]]):
        """Update the tree based on fresh nodes from the store."""
        self.clear()
        
        # 1. Group nodes
        groups = {
            "Hosts": {}, # host_id -> {node: node, services: []}
            "Web": [],
            "Credentials": [],
            "Vulnerabilities": []
        }
        
        for node in nodes:
            st = node["schema_type"]
            if st == "network.host":
                groups["Hosts"][node["id"]] = {"node": node, "services": []}
            elif st == "network.service":
                groups["Web"].append(node) # Temporary fallback
            elif st.startswith("web."):
                groups["Web"].append(node)
            elif st.startswith("credential."):
                groups["Credentials"].append(node)
            elif st.startswith("vulnerability."):
                groups["Vulnerabilities"].append(node)
        
        # 2. Populate Tree
        hosts_root = self.root.add("Targets", expand=True)
        for h_id, data in groups["Hosts"].items():
            pik = json.loads(data["node"]["pik_json"])
            ip = pik.get("ip") or pik.get("host_ip") or h_id[:8]
            hosts_root.add_leaf(f"{ip}", data={"id": h_id, "type": "network.host"})

        if groups["Web"]:
            web_root = self.root.add("Web", expand=True)
            for node in groups["Web"]:
                pik = json.loads(node["pik_json"])
                label = pik.get("url") or pik.get("path") or f"{node['id'][:8]}"
                web_root.add_leaf(label, data={"id": node["id"], "type": node["schema_type"]})

        if groups["Credentials"]:
            cred_root = self.root.add("Credentials", expand=True)
            for node in groups["Credentials"]:
                pik = json.loads(node["pik_json"])
                label = f"{pik.get('username')}:{pik.get('password')}"
                cred_root.add_leaf(label, data={"id": node["id"], "type": node["schema_type"]})

        if groups["Vulnerabilities"]:
            vuln_root = self.root.add("Vulnerabilities", expand=True)
            for node in groups["Vulnerabilities"]:
                pik = json.loads(node["pik_json"])
                label = pik.get("cve_id") or pik.get("title") or node["id"][:8]
                vuln_root.add_leaf(label, data={"id": node["id"], "type": node["schema_type"]})


class JobQueue(Vertical):
    """Displays running and queued jobs."""

    class JobSelected(events.Event):
        """Emitted when a job is clicked in the list."""
        def __init__(self, job_id: str):
            super().__init__()
            self.job_id = job_id

    def compose(self) -> ComposeResult:
        yield Label("JOB QUEUE", classes="section_header")
        yield ListView(id="power_job_list")

    async def update_jobs(self, jobs: List[JobStatus]):
        """Refresh the list of active jobs."""
        job_list = self.query_one("#power_job_list", ListView)
        # Keep track of selected index to restore it if possible
        old_idx = job_list.index
        
        await job_list.clear()
        
        # Sort jobs so running ones are at the top
        sorted_jobs = sorted(jobs, key=lambda j: (j.status != JobStatusEnum.RUNNING, j.started_at), reverse=True)

        for job in sorted_jobs:
            # Differentiate status visually
            if job.status == JobStatusEnum.RUNNING:
                status_icon = "◯"
                style = "bold #58a6ff"
            elif job.status == JobStatusEnum.DONE:
                status_icon = "●"
                style = "#3fb950"
            elif job.status == JobStatusEnum.FAILED:
                status_icon = "×"
                style = "#f85149"
            else: # QUEUED
                status_icon = "⚪"
                style = "#8b949e"
            
            label = f"{status_icon} {job.tool_name} [#8b949e]{job.job_id.hex[:4]}[/]"
            item = ListItem(Static(label), id=f"job_item_{job.job_id.hex}")
            item.job_id = str(job.job_id)
            job_list.append(item)
            
        if old_idx is not None and old_idx < len(job_list.children):
            job_list.index = old_idx

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle job selection in the queue."""
        if hasattr(event.item, "job_id"):
            self.post_message(self.JobSelected(event.item.job_id))


class CommandPalette(Vertical):
    """The interactive command prompt with Gemini-CLI style metrics."""

    class Submitted(Input.Submitted):
        """Event emitted when a command is submitted."""
        def __init__(self, command: str, tool_name: str, expanded_params: List[str], input: Input, is_manual_shell: bool = False):
            super().__init__(input, command)
            self.tool_name = tool_name
            self.expanded_params = expanded_params
            self.is_manual_shell = is_manual_shell

    class CloseTabRequest(events.Event):
        """Request to close the active tab."""
        pass

    class KillJobRequest(events.Event):
        """Request to kill the job in the active tab."""
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.resolved_vars: Dict[str, Any] = {}
        self.shell_locked: bool = False
        self.history: List[str] = []
        self.history_index: int = -1
        self.cwd: str = os.getcwd()
        self.branch: str = self._get_git_branch()

    def _get_git_branch(self) -> str:
        try:
            return subprocess.check_output(
                ["git", "branch", "--show-current"], 
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            return ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="palette_header"):
            yield Label("Tool Mode (press ! for shell)", id="mode_status")
            yield Static("", expand=True)
            yield Label("", id="lock_icon")
            yield Label("? for shortcuts", id="shortcuts_hint")
        
        yield Rule(classes="minimal-sep")
        yield Input(value="> ", id="command_input")
        with Horizontal(id="pwd_container"):
            yield Label("pwd:", classes="pwd_label")
            yield Label("~", id="pwd_line")
        yield Rule(classes="minimal-sep")
        
        with Horizontal(id="metrics_grid"):
            with Vertical(classes="metric_col"):
                yield Label("workspace", classes="metric_label")
                yield Label("CyGuide", id="metric_cwd", classes="metric_value")
            with Vertical(classes="metric_col"):
                yield Label("branch", classes="metric_label")
                yield Label("-", id="metric_branch", classes="metric_value")
            with Vertical(classes="metric_col"):
                yield Label("sandbox", classes="metric_label")
                yield Label("no sandbox", id="metric_sandbox", classes="metric_value")
            with Vertical(classes="metric_col"):
                yield Label("/model", classes="metric_label")
                yield Label("CyGuide Engine", id="metric_model", classes="metric_value")
            with Vertical(classes="metric_col"):
                yield Label("quota", classes="metric_label")
                yield Label("100% available", id="metric_quota", classes="metric_value")

        yield Label("", id="context_line", classes="hidden")
        yield Label("", id="status_line", classes="hidden")

    def show_status(self, message: str, severity: str = "info") -> None:
        """Removed as per user request for absolute minimalism."""
        pass

    def update_context(self, resolved_vars: Dict[str, Any], is_registered_tool: bool = True, cwd: str = ""):
        """Update the prompt metrics showing path and git branch."""
        self.resolved_vars = resolved_vars
        self.cwd = cwd
        self.branch = self._get_git_branch()
        
        # Update metrics
        short_path = cwd.replace(os.path.expanduser("~"), "~")
        self.query_one("#pwd_line", Label).update(short_path)
        self.query_one("#metric_branch", Label).update(self.branch or "-")
        
        # Update lock icon
        lock_label = self.query_one("#lock_icon", Label)
        if self.shell_locked:
            lock_label.update("🔒 ")
        else:
            lock_label.update("")

        # Update mode status based on current input and shell_locked
        self._update_mode_label()

    def _update_mode_label(self):
        mode_label = self.query_one("#mode_status", Label)
        cmd_input = self.query_one("#command_input", Input)
        
        if self.shell_locked:
            mode_label.update("Shell Locked (ctrl+l to unlock)")
            mode_label.set_class(True, "shell-mode")
        elif cmd_input.value.startswith("!"):
            mode_label.update("Shell Mode (press ! to revert)")
            mode_label.set_class(True, "shell-mode")
        else:
            mode_label.update("Tool Mode (press ! for shell)")
            mode_label.set_class(False, "shell-mode")

    def on_key(self, event: events.Key) -> None:
        """Handle Up/Down arrows, '!' shortcut, Tab completion, and Tab management shortcuts."""
        cmd_input = self.query_one("#command_input", Input)
        
        # Intercept shortcuts that Input normally consumes
        if event.key == "ctrl+w":
            event.stop()
            event.prevent_default()
            self.post_message(self.CloseTabRequest())
            return
        elif event.key == "ctrl+k":
            event.stop()
            event.prevent_default()
            self.post_message(self.KillJobRequest())
            return

        # '!' shortcut: Toggle prefix
            if not cmd_input.has_focus:
                event.stop()
                event.prevent_default()
                cmd_input.focus()
            return

        # Tab completion in Locked mode
        if event.key == "tab" and self.shell_locked:
            event.stop()
            event.prevent_default()
            self._handle_tab_completion(cmd_input)
            return

        if event.key == "up":
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                cmd_input.value = self.history[-(self.history_index + 1)]
                cmd_input.cursor_position = len(cmd_input.value)
        elif event.key == "down":
            if self.history_index > 0:
                self.history_index -= 1
                cmd_input.value = self.history[-(self.history_index + 1)]
                cmd_input.cursor_position = len(cmd_input.value)
            elif self.history_index == 0:
                self.history_index = -1
                mode_label = self.query_one("#mode_status", Label)
                cmd_input.value = "! " if mode_label.has_class("shell-mode") else "> "
                cmd_input.cursor_position = 2

    def _handle_tab_completion(self, cmd_input: Input) -> None:
        """Simple filename completion for the current CWD."""
        if not self.cwd or not os.path.isdir(self.cwd):
            return
            
        val = cmd_input.value
        pos = cmd_input.cursor_position
        
        # Strip prefix for completion logic
        clean_val = val.lstrip(">! ")
        prefix_len = len(val) - len(clean_val)
        
        # Find the word being typed
        before_cursor = val[:pos]
        parts = before_cursor.split()
        if not parts:
            return
            
        last_word = parts[-1]
        
        try:
            # List files in CWD
            files = os.listdir(self.cwd)
            matches = [f for f in files if f.startswith(last_word)]
            
            if len(matches) == 1:
                # Complete the word
                completion = matches[0][len(last_word):]
                cmd_input.value = before_cursor + completion + val[pos:]
                cmd_input.cursor_position = pos + len(completion)
            elif len(matches) > 1:
                # Find common prefix
                common = os.path.commonprefix(matches)
                if len(common) > len(last_word):
                    completion = common[len(last_word):]
                    cmd_input.value = before_cursor + completion + val[pos:]
                    cmd_input.cursor_position = pos + len(completion)
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Ensure the prefix (> or !) is never deleted and handle pattern-based toggles."""
        val = event.value
        
        # 1. Pattern-based mode toggle (ONLY if it's the only character after prefix)
        if val == "> !":
            event.input.value = "! "
            event.input.cursor_position = 2
            self._update_mode_label()
            return
        elif val == "! !":
            event.input.value = "> "
            event.input.cursor_position = 2
            self._update_mode_label()
            return

        # 2. Prefix protection
        if not (val.startswith(">") or val.startswith("!")):
            # User deleted prefix, restore default
            event.input.value = "> " + val.lstrip()
            event.input.cursor_position = len(event.input.value)
        
        self._update_mode_label()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Intercept input and bubble a custom event."""
        event.stop()
        raw_cmd = event.value.strip()
        if not raw_cmd:
            return

        # Record History
        if not self.history or self.history[-1] != raw_cmd:
            self.history.append(raw_cmd)
        self.history_index = -1

        # Determine mode from prefix
        is_manual_shell = raw_cmd.startswith("!")
        if self.shell_locked:
            is_manual_shell = True
            
        # Strip prefix
        clean_cmd = raw_cmd[1:].strip()
        if not clean_cmd:
            event.input.value = "! " if is_manual_shell and not self.shell_locked else "> "
            return

        parts = clean_cmd.split()
        if not parts: return
        tool_name = parts[0]
        params_str = " ".join(parts[1:])

        # Clear input and restore the active prefix (sticky mode)
        event.input.value = "! " if is_manual_shell and not self.shell_locked else "> "
        if self.shell_locked:
            event.input.value = "! "

        # The screen will handle the rejection if tool_name is not registered and ! wasn't used
        self.post_message(self.Submitted(clean_cmd, tool_name, [params_str], event.input, is_manual_shell))
